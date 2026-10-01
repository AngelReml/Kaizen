# -*- coding: utf-8 -*-
"""POST /cmd/ajustes/autonomia: subir/bajar el nivel de un cubo, solo el operador (F5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core.aprobaciones import ColaSustrato
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from panel_mando.app import crear_app

EMP = "laboratorio"
CLAVE = "clave-de-prueba-autonomia"


@pytest.fixture()
def montaje(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)

    def hacer(token=None):
        k = InMemoryKnowledge()
        app = crear_app(k, token=token, mecha_s=0)
        b = Bitacora(k, EMP, fecha_alta="2026-07-10")
        app.state.bitacoras[EMP] = b
        app.state.colas[EMP] = ColaSustrato(k, EMP, bitacora=b)
        return k, b, TestClient(app, raise_server_exceptions=False)
    return hacer


def _nivel_mundo(c, cubo):
    return {x["cubo"]: x["autonomia"]
            for x in c.get("/api/mundo/estado", params={"empresa": EMP}).json()["cubos"]}[cubo]


def _cambios(k):
    return [e["payload"] for e in k.all(EMP, "evento").values()
            if e["tipo"] == "plataforma.autonomia.cambiada"]


def _post(c, **cuerpo):
    return c.post("/cmd/ajustes/autonomia", json={"empresa": EMP, "quien": "operador", **cuerpo})


def test_subir_con_motivo_devuelve_ficha_y_se_sella(montaje):
    k, b, c = montaje()
    assert _nivel_mundo(c, "qa") == "CERO"
    r = _post(c, cubo="qa", nivel="BAJA", motivo="ya revisa bien")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["resultado"]["de"], j["resultado"]["a"], j["resultado"]["aplicado"]) == ("CERO", "BAJA", True)
    assert "rendimiento" in j["ficha"]                       # ficha delante (None = sin medir)
    assert _nivel_mundo(c, "qa") == "BAJA"
    ev = _cambios(k)[-1]
    assert (ev["actor"], ev["cubo"], ev["causa"], ev["veredicto"]) == \
        ("operador", "qa", "decision_del_operador", "aplicado")
    import hashlib
    assert ev["motivo_sha256"] == hashlib.sha256(b"ya revisa bien").hexdigest()
    assert "ya revisa bien" not in str(ev)            # el texto libre no va a la bitacora ni al feed
    assert b.verificar()["integra"] is True


def test_subir_sin_motivo_se_rechaza_pero_bajar_no_lo_exige(montaje):
    k, _, c = montaje()
    r = _post(c, cubo="qa", nivel="BAJA")
    assert r.status_code == 409 and "motivo" in r.text
    assert _nivel_mundo(c, "qa") == "CERO" and _cambios(k) == []
    assert _post(c, cubo="comercial", nivel="CERO").status_code == 200       # endurecer: sin motivo
    assert _nivel_mundo(c, "comercial") == "CERO"


def test_alta_esta_bloqueada_incluso_para_el_operador_y_el_intento_queda_sellado(montaje):
    k, b, c = montaje()
    r = _post(c, cubo="comercial", nivel="ALTA", motivo="quiero")
    assert r.status_code == 409 and "bloqueado" in r.text
    assert _nivel_mundo(c, "comercial") == "BAJA"
    ev = _cambios(k)[-1]
    assert ev["veredicto"] == "rechazado" and ev["motivo"] == "nivel_bloqueado"
    assert b.verificar()["integra"] is True


@pytest.mark.parametrize("cuerpo", [
    {"cubo": "no_existe", "nivel": "BAJA", "motivo": "x"},
    {"cubo": "qa", "nivel": "TOTAL", "motivo": "x"},
    {"cubo": "qa", "nivel": "", "motivo": "x"},
    {"cubo": "", "nivel": "BAJA", "motivo": "x"},
    {"empresa": "otra_que_no_existe", "cubo": "qa", "nivel": "BAJA", "motivo": "x"},
])
def test_entradas_invalidas_se_rechazan_sin_tocar_nada(montaje, cuerpo):
    k, _, c = montaje()
    r = c.post("/cmd/ajustes/autonomia", json={"empresa": EMP, "quien": "operador", **cuerpo})
    assert r.status_code == 409
    assert _cambios(k) == [] and _nivel_mundo(c, "qa") == "CERO"


def test_sin_identidad_se_rechaza(montaje):
    k, _, c = montaje()
    r = c.post("/cmd/ajustes/autonomia",
               json={"empresa": EMP, "cubo": "qa", "nivel": "BAJA", "motivo": "x"})
    assert r.status_code == 409 and _cambios(k) == []


def test_con_clave_exige_autenticacion(montaje):
    k, _, c = montaje(token=CLAVE)
    cuerpo = {"empresa": EMP, "cubo": "qa", "nivel": "BAJA", "motivo": "x", "quien": "operador"}
    sin = c.post("/cmd/ajustes/autonomia", json=cuerpo)
    assert sin.status_code in (401, 403) and _cambios(k) == []
    con = c.post("/cmd/ajustes/autonomia", json=cuerpo, headers={"X-Token": CLAVE})
    assert con.status_code == 200 and _cambios(k)[-1]["cubo"] == "qa"


def test_subir_un_nivel_tras_una_bajada_automatica_restaura_el_control_al_operador(montaje):
    from core.autonomia import AutonomiaCubos
    k, _, c = montaje()
    AutonomiaCubos(k, EMP).endurecer("marketing", "BAJA", causa="racha_de_denegadas", incidente="i")
    assert _nivel_mundo(c, "marketing") == "CERO"
    assert _post(c, cubo="marketing", nivel="BAJA", motivo="revisado").status_code == 200
    assert _nivel_mundo(c, "marketing") == "BAJA"
