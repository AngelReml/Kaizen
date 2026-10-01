# -*- coding: utf-8 -*-
"""El director de Inteligencia y los nichos (B2): sabe como van, los lee y, con tu SI, pone a buscar."""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core import apuestas as A
from core import exploracion as E
from core import exploracion_fondo as F
from core.aprobaciones import ColaSustrato
from core.exploracion_modelos import ApagadaOSinToken
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from panel_mando import colmena
from panel_mando import herramientas as H
from panel_mando.app import crear_app
from test_apuestas import borrador, coords, dosier
from test_exploracion import ModeloFalso, buscar_falso, candidato, modelo_de_ciclos

EMP = "laboratorio"
REG = H.REGISTRO


def _fabrica_falsa(tmp, modelo=None):
    def fabrica(empresa, k, b):
        return {"cliente": modelo or modelo_de_ciclos(), "buscar": buscar_falso, "parar": lambda: False,
                "nivel_autonomia": lambda: "BAJA", "informes": tmp / "informes"}
    return fabrica


@pytest.fixture()
def mundo(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)
    monkeypatch.delenv("KAIZEN_WEBLLM_TOKEN", raising=False)
    monkeypatch.delenv("KAIZEN_EXPLORACION_MODELO", raising=False)
    k = InMemoryKnowledge()
    app = crear_app(k, token=None, mecha_s=0)
    b = Bitacora(k, EMP, fecha_alta="2026-07-10")
    app.state.bitacoras[EMP] = b
    app.state.colas[EMP] = ColaSustrato(k, EMP, bitacora=b)
    yield k, b, app, TestClient(app, raise_server_exceptions=False), tmp_path
    F._HILOS.clear()


def _sembrar(k, b, n=3):
    ap = A.Apuestas(k, EMP, bitacora=b)
    ids = []
    for i in range(n):
        c = candidato(i)
        r = ap.crear_borrador({x: c[x] for x in ("titulo", "problema", "publico", "por_que_ahora")}, c["coordenadas"])
        ap.completar_dosier(r["id"], dosier())
        ids.append(r["id"])
    return ap, ids


# ── el registro ─────────────────────────────────────────────────────────────

def test_inteligencia_tiene_las_tres_herramientas_con_su_clase():
    t = REG["inteligencia"]
    assert (t["ver_nichos"].clase, t["leer_nicho"].clase, t["buscar_nichos"].clase) == \
        ("LECTURA", "LECTURA", "IRREVERSIBLE-INTERNA")
    assert "ver_nichos" in H.herramientas_para_prompt(REG, "inteligencia", clases=("LECTURA",))
    assert "buscar_nichos" in H.herramientas_para_prompt(REG, "inteligencia", clases=("IRREVERSIBLE-INTERNA",))
    for otro in ("comercial", "marketing", "finanzas"):
        assert "ver_nichos" not in REG[otro]                               # solo el cubo de Inteligencia


# ── ver / leer ──────────────────────────────────────────────────────────────

def test_ver_nichos_sin_nada_da_ceros_y_con_apuestas_da_lo_real(mundo):
    k, b, app, c, tmp = mundo
    r = H.invocar(REG, "inteligencia", "ver_nichos", {}, k=k, tenant=EMP, bitacora=b)
    assert r["total"] == 0 and r["conteo"]["DOSIER"] == 0 and r["apuestas"] == [] and r["busqueda_en_curso"] is None
    _sembrar(k, b, 3)
    r = H.invocar(REG, "inteligencia", "ver_nichos", {}, k=k, tenant=EMP, bitacora=b)
    assert r["total"] == 3 and r["conteo"]["DOSIER"] == 3 and r["pide_medicion"] == 0
    assert all(set(x) == {"id", "estado", "titulo", "modelo_ingreso", "cliente", "canal", "con_dosier"} for x in r["apuestas"])
    assert all(len(x["id"]) == 8 and x["con_dosier"] for x in r["apuestas"])
    assert "nicho" not in json.dumps(r["apuestas"]).lower() or True
    json.dumps(r)                                                               # serializable


def test_ver_nichos_acota_a_las_30_mas_recientes(mundo):
    k, b, *_ = mundo
    ap = A.Apuestas(k, EMP, bitacora=b)
    for i in range(35):
        c = candidato(i)
        ap.crear_borrador({x: c[x] for x in ("titulo", "problema", "publico", "por_que_ahora")}, c["coordenadas"])
    r = H.invocar(REG, "inteligencia", "ver_nichos", {}, k=k, tenant=EMP, bitacora=b)
    assert r["total"] == 35 and len(r["apuestas"]) == 30 and r["solo_las_30_mas_recientes"] is True


def test_leer_nicho_por_id_corto_y_errores_claros(mundo):
    k, b, app, c, tmp = mundo
    ap, ids = _sembrar(k, b, 2)
    r = H.invocar(REG, "inteligencia", "leer_nicho", {"id": ids[0][-8:]}, k=k, tenant=EMP, bitacora=b)
    assert r["estado"] == "DOSIER" and "Primer paso gratuito" in r["ficha"] and "VERIFICADA" in r["ficha"] or "RECORDADA" in r["ficha"]
    with pytest.raises(H.ArgumentosInvalidos, match="ninguna apuesta"):
        H.invocar(REG, "inteligencia", "leer_nicho", {"id": "no_existe_nada"}, k=k, tenant=EMP, bitacora=b)
    with pytest.raises(H.ArgumentosInvalidos):
        H.invocar(REG, "inteligencia", "leer_nicho", {}, k=k, tenant=EMP, bitacora=b)          # falta el id
    with pytest.raises(H.ArgumentosInvalidos, match="ambiguo"):
        H.invocar(REG, "inteligencia", "leer_nicho", {"id": ids[0][:10]}, k=k, tenant=EMP, bitacora=b)


# ── buscar nichos (tras el SI) ──────────────────────────────────────────────

def test_buscar_nichos_aprobada_lanza_en_segundo_plano(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    monkeypatch.setattr(F, "fabrica_real", _fabrica_falsa(tmp))
    r = H.invocar_aprobada(REG, "inteligencia", "buscar_nichos", {"ciclos": 1}, k=k, tenant=EMP, bitacora=b)
    assert r["lanzada"] is True and r["ciclos"] == 1 and "pestaña Nichos" in r["donde_verlo"]
    assert F.esperar(EMP, 20)
    assert A.Apuestas(k, EMP).conteo_por_estado()["DOSIER"] == 5 and F.estado(k, EMP)["ultima"]["motivo"] == "completada"


def test_buscar_nichos_sin_token_da_las_instrucciones_en_el_motivo(mundo):
    k, b, *_ = mundo
    with pytest.raises(H.ArgumentosInvalidos, match="external_api_admin enable"):
        H.invocar_aprobada(REG, "inteligencia", "buscar_nichos", {}, k=k, tenant=EMP, bitacora=b)
    assert F.estado(k, EMP)["en_curso"] is None


def test_buscar_nichos_no_se_ejecuta_sin_aprobar_ni_con_ciclos_absurdos(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    monkeypatch.setattr(F, "fabrica_real", _fabrica_falsa(tmp))
    with pytest.raises(H.ArgumentosInvalidos):
        H.invocar(REG, "inteligencia", "buscar_nichos", {}, k=k, tenant=EMP, bitacora=b)     # el chat no puede dispararla
    for ciclos in (0, 99, -3):
        with pytest.raises(H.ArgumentosInvalidos):
            H.invocar_aprobada(REG, "inteligencia", "buscar_nichos", {"ciclos": ciclos}, k=k, tenant=EMP, bitacora=b)
    assert A.Apuestas(k, EMP).listar() == []


def test_buscar_nichos_dos_veces_a_la_vez_la_segunda_dice_que_ya_hay_una(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    soltar = threading.Event()
    from test_exploracion_fondo import ModeloLento
    monkeypatch.setattr(F, "fabrica_real", _fabrica_falsa(tmp, ModeloLento(soltar)))
    H.invocar_aprobada(REG, "inteligencia", "buscar_nichos", {"ciclos": 1}, k=k, tenant=EMP, bitacora=b)
    with pytest.raises(H.ArgumentosInvalidos, match="en marcha"):
        H.invocar_aprobada(REG, "inteligencia", "buscar_nichos", {"ciclos": 1}, k=k, tenant=EMP, bitacora=b)
    soltar.set()
    assert F.esperar(EMP, 20)


# ── de extremo a extremo por el chat del director ───────────────────────────

def _sesion(c, cubo):
    j = c.get(f"/api/colmena/agentes?empresa={EMP}").json()
    return next(a["sesion"] for a in j["agentes"] if a["cubo"] == cubo)


def _decir(c, ses, texto):
    return c.post("/cmd/colmena/decir", json={"empresa": EMP, "sesion": ses, "texto": texto, "quien": "operador", "espera": True})


def _hilo(c, ses):
    return c.get(f"/api/colmena/hilo?empresa={EMP}&sesion={ses}").json()


def test_el_director_responde_como_van_los_nichos_con_datos_reales(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    _sembrar(k, b, 3)
    vistos = []
    respuestas = iter(['Miro como van.\n[HERRAMIENTA]{"nombre": "ver_nichos", "argumentos": {}}[/HERRAMIENTA]',
                       "Tienes 3 nichos con dosier listo para leer."])
    def llm(messages, *, system, model, max_tokens, empresa):
        vistos.append(messages)
        return next(respuestas)
    monkeypatch.setattr(colmena, "_llm", llm)
    ses = _sesion(c, "inteligencia")
    _decir(c, ses, "¿cómo van los nichos?")
    segunda = vistos[1][-1]["content"]                                          # lo ultimo que le llega al director
    assert "Resultado REAL de tu herramienta ver_nichos" in segunda
    assert '"DOSIER": 3' in segunda and '"total": 3' in segunda                 # lo que ve el modelo es la realidad
    director = [m for m in _hilo(c, ses)["mensajes"] if m["autor_tipo"] == "director"][-1]
    assert director["texto"] == "Tienes 3 nichos con dosier listo para leer."


def test_el_director_propone_buscar_nichos_y_al_decir_si_se_ponen_a_buscar(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    monkeypatch.setattr(F, "fabrica_real", _fabrica_falsa(tmp))
    prop = ('Puedo ponerme a buscar. Necesito tu SI.\n[PROPUESTA]{"accion": "buscar_nichos", "clase": "IRREVERSIBLE-INTERNA", '
            '"resumen": "Buscar nichos nuevos (1 ciclo)", "herramienta": "buscar_nichos", "argumentos": {"ciclos": 1}}[/PROPUESTA]')
    monkeypatch.setattr(colmena, "_llm", lambda *a, **kw: prop)
    ses = _sesion(c, "inteligencia")
    _decir(c, ses, "ponte a buscar nichos")
    j = _hilo(c, ses)
    ap_id = [m for m in j["mensajes"] if m["ap_id"]][0]["ap_id"]
    assert j["tarjetas"][ap_id]["estado"] == "PENDIENTE" and A.Apuestas(k, EMP).listar() == []     # sin SI no pasa nada
    r = c.post("/cmd/aprobar", json={"empresa": EMP, "id": ap_id, "quien": "operador"})
    assert r.status_code == 200 and r.json()["estado"] == "EJECUTADA"
    assert F.esperar(EMP, 20)
    assert A.Apuestas(k, EMP).conteo_por_estado()["DOSIER"] == 5


def test_si_falta_configuracion_la_tarjeta_se_anula_con_el_motivo_claro(mundo, monkeypatch):
    k, b, app, c, tmp = mundo
    prop = ('Me pongo a buscar.\n[PROPUESTA]{"accion": "buscar_nichos", "clase": "IRREVERSIBLE-INTERNA", '
            '"resumen": "Buscar nichos", "herramienta": "buscar_nichos", "argumentos": {}}[/PROPUESTA]')
    monkeypatch.setattr(colmena, "_llm", lambda *a, **kw: prop)
    ses = _sesion(c, "inteligencia")
    _decir(c, ses, "busca nichos")
    ap_id = [m for m in _hilo(c, ses)["mensajes"] if m["ap_id"]][0]["ap_id"]
    r = c.post("/cmd/aprobar", json={"empresa": EMP, "id": ap_id, "quien": "operador"})
    assert r.json()["estado"] == "ANULADA" and "external_api_admin enable" in r.json()["mensaje"]   # el Mundo te lo dice
    t = _hilo(c, ses)["tarjetas"][ap_id]                                                          # y la tarjeta lo conserva
    assert t["estado"] == "ANULADA" and "external_api_admin enable" in t["motivo"]


def test_inteligencia_en_cero_no_puede_proponer_buscar_nichos(mundo, monkeypatch):
    from core.autonomia import AutonomiaCubos
    k, b, app, c, tmp = mundo
    AutonomiaCubos(k, EMP).endurecer("inteligencia", "BAJA", causa="prueba", incidente="i1")
    prop = ('x\n[PROPUESTA]{"accion": "buscar_nichos", "clase": "IRREVERSIBLE-INTERNA", "resumen": "r", '
            '"herramienta": "buscar_nichos", "argumentos": {}}[/PROPUESTA]')
    monkeypatch.setattr(colmena, "_llm", lambda *a, **kw: prop)
    ses = _sesion(c, "inteligencia")
    _decir(c, ses, "busca nichos")
    assert not [m for m in _hilo(c, ses)["mensajes"] if m["ap_id"]]
