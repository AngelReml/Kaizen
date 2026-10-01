# -*- coding: utf-8 -*-
"""Gatillos de endurecimiento automatico (core/autonomia.vigilar, docs/AUTONOMIA_v0.md G1)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core.aprobaciones import ColaSustrato
from core.autonomia import AutonomiaCubos, incidente_de_racha, vigilar
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre
from panel_mando.app import crear_app

T = "t1"
DEFECTOS = {"comercial": "BAJA", "legal": "BAJA", "qa": "CERO"}


@pytest.fixture()
def mundo():
    k = InMemoryKnowledge()
    b = Bitacora(k, T, fecha_alta="2026-07-10")
    return k, b, ColaSustrato(k, T, bitacora=b)


def _decidir(cola, cubo, veredicto):
    n = cola.solicitar(cubo=cubo, accion="a", clase="REVERSIBLE")
    if veredicto == "DENEGADA":
        cola.denegar(n["id"], por="angel")
    else:
        cola.aprobar(n["id"], por="angel")
    return n["id"]


def _eventos(k):
    return [e["payload"] for e in k.all(T, "evento").values()
            if e["tipo"] == "plataforma.autonomia.cambiada"]


# ── racha de denegadas ───────────────────────────────────────────────────────

def test_tres_denegadas_seguidas_bajan_solo_ese_cubo_y_se_sella(mundo):
    k, b, cola = mundo
    for _ in range(3):
        _decidir(cola, "comercial", "DENEGADA")
    _decidir(cola, "legal", "DENEGADA")                       # otro cubo: no cuenta
    r = vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS)
    assert [(x["cubo"], x["de"], x["a"]) for x in r] == [("comercial", "BAJA", "CERO")]
    ev = _eventos(k)
    assert ev[-1]["causa"] == "racha_de_denegadas" and ev[-1]["cubo"] == "comercial"
    assert b.verificar()["integra"] is True


def test_dos_denegadas_o_racha_cortada_por_un_si_no_bajan(mundo):
    k, b, cola = mundo
    _decidir(cola, "comercial", "DENEGADA")
    _decidir(cola, "comercial", "DENEGADA")
    _decidir(cola, "comercial", "APROBADA")
    _decidir(cola, "comercial", "DENEGADA")
    _decidir(cola, "comercial", "DENEGADA")
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []
    assert _eventos(k) == []


def test_idempotente_y_la_racha_larga_no_baja_dos_veces(mundo):
    k, b, cola = mundo
    for _ in range(5):
        _decidir(cola, "comercial", "DENEGADA")
    assert len(vigilar(k, T, cola=cola, bitacora=b, defectos={"comercial": "MEDIA"})) == 1
    assert vigilar(k, T, cola=cola, bitacora=b, defectos={"comercial": "MEDIA"}) == []
    assert AutonomiaCubos(k, T).nivel("comercial", "MEDIA") == "BAJA"


def test_tras_restaurar_hacen_falta_tres_denegadas_nuevas(mundo):
    k, b, cola = mundo
    for _ in range(3):
        _decidir(cola, "comercial", "DENEGADA")
    vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS)                # BAJA -> CERO
    aut = AutonomiaCubos(k, T, bitacora=b)
    aut.fijar("comercial", "BAJA", "BAJA", por="angel", motivo="vuelve")
    assert aut.nivel("comercial", "BAJA") == "BAJA"
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []   # las viejas no cuentan
    for _ in range(3):
        _decidir(cola, "comercial", "DENEGADA")
    assert len(vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS)) == 1


def test_caducadas_y_revocadas_no_cuentan_ni_cortan(mundo):
    k, b, cola = mundo
    ids = [_decidir(cola, "comercial", "DENEGADA") for _ in range(2)]
    cad = cola.solicitar(cubo="comercial", accion="a", clase="REVERSIBLE")
    cola.barrer_caducadas(ahora=datetime.now(timezone.utc) + timedelta(hours=100))   # CADUCADA
    assert cola._get(cad["id"])["estado"] == "CADUCADA"
    rev = cola.solicitar(cubo="comercial", accion="a", clase="IRREVERSIBLE-EXTERNA")
    cola.aprobar(rev["id"], por="angel"); cola.revocar(rev["id"], por="angel")
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []       # solo 2 denegadas
    _decidir(cola, "comercial", "DENEGADA")
    assert len(vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS)) == 1
    assert ids


def test_incidente_de_racha_funcion_pura():
    def n(i, est, seg):
        t = (datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(seconds=seg)).isoformat()
        return {"id": i, "cubo": "c", "estado": est, "decidida_en": t}
    tarj = [n("a", "DENEGADA", 1), n("b", "DENEGADA", 2), n("c", "DENEGADA", 3), n("d", "DENEGADA", 4)]
    assert incidente_de_racha(tarj, "c", None) == "racha:c"        # 3.ª de la racha, estable
    assert incidente_de_racha(tarj[:2], "c", None) is None
    assert incidente_de_racha(tarj, "c", tarj[2]["decidida_en"]) is None   # solo posteriores
    assert incidente_de_racha(tarj, "otro", None) is None
    assert incidente_de_racha([{"id": "x", "cubo": "c", "estado": "PENDIENTE"}], "c", None) is None


def test_nunca_baja_de_cero(mundo):
    k, b, cola = mundo
    for _ in range(3):
        _decidir(cola, "qa", "DENEGADA")
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []
    assert AutonomiaCubos(k, T).nivel("qa", "CERO") == "CERO"


# ── sello roto ───────────────────────────────────────────────────────────────

def _romper_sello(k, b):
    b.publicar(Sobre(tenant_id=T, tipo="comercial.lead.descubierto", payload={"lead_ref": "l1"},
                     origen="t"))
    b.publicar(Sobre(tenant_id=T, tipo="operacion.pedido.confirmado", payload={}, origen="t"))
    clave = sorted(k.all(T, "evento"))[0]
    ev = k.get(T, "evento", clave)
    ev["payload"] = {"manipulado": True}
    k.add(T, "evento", clave, ev)
    assert b.verificar()["integra"] is False


def test_sello_roto_baja_todos_los_cubos_una_sola_vez(mundo):
    k, b, cola = mundo
    _romper_sello(k, b)
    r = vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS)
    assert sorted((x["cubo"], x["a"]) for x in r) == [("comercial", "CERO"), ("legal", "CERO")]
    assert all(e["causa"] == "sello_roto" for e in _eventos(k))
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []      # mismo incidente
    aut = AutonomiaCubos(k, T, bitacora=b)
    aut.fijar("comercial", "BAJA", "BAJA", por="angel", motivo="revisado")
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []      # sigue siendo el mismo


def test_sello_integro_no_toca_nada(mundo):
    k, b, cola = mundo
    b.publicar(Sobre(tenant_id=T, tipo="comercial.lead.descubierto", payload={}, origen="t"))
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS) == []


# ── freno ────────────────────────────────────────────────────────────────────

def test_el_freno_evita_verificar_en_cada_pulso(mundo):
    k, b, cola = mundo
    ultima = {}
    assert vigilar(k, T, cola=cola, bitacora=b, defectos=DEFECTOS, ultima=ultima, cada_s=30) == []
    for _ in range(3):
        _decidir(cola, "comercial", "DENEGADA")
    # dentro de la ventana: no mira (y ni siquiera evalua `defectos`)
    llamado = []
    assert vigilar(k, T, cola=cola, bitacora=b, ultima=ultima, cada_s=30,
                   defectos=lambda: llamado.append(1) or DEFECTOS) == []
    assert llamado == []
    ultima[T] -= 31                                                        # pasa la ventana
    assert len(vigilar(k, T, cola=cola, bitacora=b, ultima=ultima, cada_s=30,
                       defectos=lambda: llamado.append(1) or DEFECTOS)) == 1
    assert llamado == [1]


# ── de extremo a extremo por el panel ────────────────────────────────────────

def test_por_el_panel_tres_noes_bajan_el_nivel_y_el_mundo_lo_muestra(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)
    k = InMemoryKnowledge()
    app = crear_app(k, token=None, mecha_s=0)
    emp = "laboratorio"
    b = Bitacora(k, emp, fecha_alta="2026-07-10")
    app.state.bitacoras[emp] = b
    app.state.colas[emp] = cola = ColaSustrato(k, emp, bitacora=b)
    c = TestClient(app, raise_server_exceptions=False)

    def nivel(cubo):
        return {x["cubo"]: x["autonomia"]
                for x in c.get("/api/mundo/estado", params={"empresa": emp}).json()["cubos"]}[cubo]

    assert nivel("marketing") == "BAJA"
    for _ in range(3):
        n = cola.solicitar(cubo="marketing", accion="a", clase="REVERSIBLE")
        r = c.post("/cmd/denegar", json={"empresa": emp, "id": n["id"], "quien": "operador"})
        assert r.status_code == 200
    app.state.vigilancia.clear()                              # el freno no es lo que se prueba
    r = c.post("/cmd/tic", json={})
    assert r.status_code == 200 and r.json()["quemadas"] == []   # la respuesta de la API no cambia
    assert nivel("marketing") == "CERO"
    assert nivel("comercial") == "BAJA"
    assert b.verificar()["integra"] is True
