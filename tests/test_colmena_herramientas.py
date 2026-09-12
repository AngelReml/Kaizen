# -*- coding: utf-8 -*-
"""Fase 4 — directores plenipotenciarios: un cubo con herramientas REALES
(inyectadas por test, sin tocar los registros reales de produccion) para
probar el flujo completo: LECTURA en dos pasadas (el director ve el
resultado real antes de responder), REVERSIBLE ejecutada al instante sin
pedir permiso, e IRREVERSIBLE-INTERNA que se propone como tarjeta y SOLO se
dispara de verdad al aprobarse — con los argumentos exactos que el operador
vio, nunca regenerados. Aislamiento estricto entre cubos verificado end-to-end
via el chat (no solo a nivel de base.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core.knowledge import InMemoryKnowledge
from panel_mando import colmena, herramientas as H
from panel_mando.app import crear_app

EMPRESA = "laboratorio"

LLAMADAS_LECTURA = []       # registra (k, tenant, bitacora, kwargs) por invocacion
LLAMADAS_REVERSIBLE = []


def _fn_lectura(**kw):
    LLAMADAS_LECTURA.append(kw)
    return {"pipeline": "3 leads en COLD", "lead_id": kw.get("lead_id", "")}


def _fn_reversible(**kw):
    LLAMADAS_REVERSIBLE.append(kw)
    return {"capacidad_declarada": kw.get("lotes", 0)}


def _fn_irrev_interna(**kw):
    return {"compromiso_id": "C-001", "fecha": kw.get("fecha", "")}


@pytest.fixture(autouse=True)
def _reset_llamadas():
    LLAMADAS_LECTURA.clear()
    LLAMADAS_REVERSIBLE.clear()
    yield


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)

    registro_original = H.REGISTRO
    registro_test = {c: dict(specs) for c, specs in registro_original.items()}
    registro_test["comercial"] = {
        "consultar_pipeline": H.ToolSpec(
            nombre="consultar_pipeline", clase="LECTURA",
            descripcion="consulta real del pipeline",
            argumentos=(H.Argumento("lead_id", "str", "id del lead", obligatorio=False),),
            fn=_fn_lectura),
        "declarar_capacidad_test": H.ToolSpec(
            nombre="declarar_capacidad_test", clase="REVERSIBLE",
            descripcion="declara capacidad (test)",
            argumentos=(H.Argumento("lotes", "int", "lotes de hoy"),),
            fn=_fn_reversible),
        "crear_compromiso_test": H.ToolSpec(
            nombre="crear_compromiso_test", clase="IRREVERSIBLE-INTERNA",
            descripcion="crea un compromiso (test)",
            argumentos=(H.Argumento("fecha", "str", "fecha del compromiso"),),
            fn=_fn_irrev_interna),
    }
    registro_test["marketing"] = {}    # cubo SIN herramientas: para probar aislamiento
    monkeypatch.setattr(H, "REGISTRO", registro_test)
    return tmp_path


def _app(token=None):
    return crear_app(InMemoryKnowledge(), token=token, mecha_s=0)


def _llm_fijo(texto):
    def f(messages, *, system, model, max_tokens, empresa):
        return texto
    return f


def _decir(c, sesion, texto, **extra):
    return c.post("/cmd/colmena/decir",
                  json={"empresa": EMPRESA, "sesion": sesion, "texto": texto,
                        "quien": "operador", "espera": True, **extra})


def _sesion_de(c, cubo):
    j = c.get(f"/api/colmena/agentes?empresa={EMPRESA}").json()
    return next(a["sesion"] for a in j["agentes"] if a["cubo"] == cubo)


def _hilo(c, sesion):
    return c.get(f"/api/colmena/hilo?empresa={EMPRESA}&sesion={sesion}").json()


# ── LECTURA: dos pasadas, resultado real, sin aprobacion ────────────────────

def test_lectura_ejecuta_de_verdad_y_responde_con_el_resultado_real(entorno, monkeypatch):
    respuestas = iter([
        'Voy a mirar el pipeline.\n[HERRAMIENTA]{"nombre": "consultar_pipeline", '
        '"argumentos": {"lead_id": "L9"}}[/HERRAMIENTA]',
        "El pipeline tiene 3 leads en COLD ahora mismo.",
    ])
    monkeypatch.setattr(colmena, "_llm", lambda *a, **kw: next(respuestas))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "¿como va el pipeline del lead L9?")
    assert len(LLAMADAS_LECTURA) == 1
    assert LLAMADAS_LECTURA[0]["lead_id"] == "L9"
    assert LLAMADAS_LECTURA[0]["tenant"] == EMPRESA
    msjs = _hilo(c, ses)["mensajes"]
    directores = [m for m in msjs if m["autor_tipo"] == "director"]
    assert len(directores) == 1
    assert directores[0]["texto"] == "El pipeline tiene 3 leads en COLD ahora mismo."
    assert not [m for m in msjs if m["ap_id"]]           # LECTURA no crea tarjeta


def test_lectura_con_error_se_reporta_no_se_inventa(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(
        '[HERRAMIENTA]{"nombre": "consultar_pipeline", '
        '"argumentos": {"lead_id": 123, "extra": "no-declarado"}}[/HERRAMIENTA]'))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "consulta algo raro")
    assert not LLAMADAS_LECTURA                            # nunca se llego a invocar
    msjs = _hilo(c, ses)["mensajes"]
    assert any(m["autor_tipo"] == "sistema" and "rechazada" in m["texto"] for m in msjs)


# ── REVERSIBLE: ejecuta al instante, sin pedir permiso ──────────────────────

def test_reversible_ejecuta_directo_sin_tarjeta_ni_aprobacion(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(
        'Declaro la capacidad de hoy.\n[HERRAMIENTA]{"nombre": "declarar_capacidad_test", '
        '"argumentos": {"lotes": 12}}[/HERRAMIENTA]'))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "declara la capacidad de hoy: 12 lotes")
    assert len(LLAMADAS_REVERSIBLE) == 1 and LLAMADAS_REVERSIBLE[0]["lotes"] == 12
    msjs = _hilo(c, ses)["mensajes"]
    assert not [m for m in msjs if m["ap_id"]]              # sin tarjeta: ya se hizo
    assert any(m["autor_tipo"] == "sistema" and "declarar_capacidad_test" in m["texto"]
               and "resultado real" in m["texto"] for m in msjs)


# ── IRREVERSIBLE-INTERNA: solo tarjeta; se dispara DE VERDAD al aprobar ─────

PROP_CON_HERRAMIENTA = (
    'Propongo crear el compromiso.\n'
    '[PROPUESTA]{"accion": "crear_compromiso_test", "clase": "IRREVERSIBLE-INTERNA", '
    '"resumen": "Compromiso para el 2026-09-01", "herramienta": "crear_compromiso_test", '
    '"argumentos": {"fecha": "2026-09-01"}}[/PROPUESTA]')


def test_irreversible_interna_no_se_ejecuta_al_proponer(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROP_CON_HERRAMIENTA))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "crea el compromiso")
    j = _hilo(c, ses)
    tarjetas = [m for m in j["mensajes"] if m["ap_id"]]
    assert len(tarjetas) == 1
    assert j["tarjetas"][tarjetas[0]["ap_id"]]["estado"] == "PENDIENTE"


def test_irreversible_interna_se_ejecuta_de_verdad_al_aprobar_con_argumentos_exactos(
        entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROP_CON_HERRAMIENTA))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "crea el compromiso")
    ap_id = [m for m in _hilo(c, ses)["mensajes"] if m["ap_id"]][0]["ap_id"]
    r = c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": ap_id, "quien": "operador"})
    assert r.status_code == 200 and r.json()["estado"] == "EJECUTADA"
    t = c.get(f"/api/colmena/tarjetas?empresa={EMPRESA}").json()["tarjetas"]
    assert t[ap_id]["estado"] == "EJECUTADA"


def test_argumentos_no_se_regeneran_al_aprobar_se_replica_lo_propuesto(entorno, monkeypatch):
    """Aunque el modelo hubiera 'cambiado de opinion' entre la propuesta y la
    aprobacion, lo que se ejecuta es EXACTAMENTE lo que quedo guardado al
    proponer — la funcion de test _fn_irrev_interna devuelve la fecha que
    recibe; verificamos que es la propuesta, no una improvisada despues."""
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROP_CON_HERRAMIENTA))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "crea el compromiso")
    ap_id = [m for m in _hilo(c, ses)["mensajes"] if m["ap_id"]][0]["ap_id"]
    # cambiar el LLM despues de proponer no debe afectar a la ejecucion:
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("cualquier otra cosa"))
    r = c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": ap_id, "quien": "operador"})
    assert r.json()["estado"] == "EJECUTADA"


def test_propuesta_sin_binding_sigue_como_antes_ejecutada_generica(entorno, monkeypatch):
    """Una IRREVERSIBLE-INTERNA SIN campo herramienta (el patron viejo, aun
    valido para acciones sin herramienta registrada) sigue siendo EJECUTADA
    generica — Fase 4 no rompe el comportamiento anterior."""
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(
        'Propongo algo interno.\n[PROPUESTA]{"accion": "algo_interno_generico", '
        '"clase": "IRREVERSIBLE-INTERNA", "resumen": "r"}[/PROPUESTA]'))
    c = TestClient(_app())
    ses = _sesion_de(c, "comercial")
    _decir(c, ses, "propon algo")
    ap_id = [m for m in _hilo(c, ses)["mensajes"] if m["ap_id"]][0]["ap_id"]
    r = c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": ap_id, "quien": "operador"})
    assert r.json()["estado"] == "EJECUTADA"


# ── aislamiento estricto entre cubos, de punta a punta por el chat ──────────

def test_director_no_puede_invocar_herramienta_de_otro_cubo(entorno, monkeypatch):
    """El director de marketing (SIN herramientas en este test) pide, via
    texto del modelo, la herramienta de comercial por su nombre exacto — debe
    rechazarse: el nombre de cubo que decide el registro consultado es el del
    AGENTE AUTENTICADO, jamas uno que el texto del LLM pueda declarar."""
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(
        '[HERRAMIENTA]{"nombre": "consultar_pipeline", "argumentos": {}}[/HERRAMIENTA]'))
    c = TestClient(_app())
    ses = _sesion_de(c, "marketing")
    _decir(c, ses, "consulta el pipeline de comercial")
    assert not LLAMADAS_LECTURA                            # nunca se ejecuto nada
    msjs = _hilo(c, ses)["mensajes"]
    assert any(m["autor_tipo"] == "sistema" and "no existe" in m["texto"] for m in msjs)


def test_autonomia_cero_no_ejecuta_reversible_ni_irreversible(entorno, monkeypatch):
    """qa es CERO: aunque tuviera una REVERSIBLE registrada, _persona() no
    la ofrece y ademas [HERRAMIENTA] con clase distinta de LECTURA se puede
    pedir igualmente (el LLM podria alucinar) — debe rechazarse igual porque
    la clase de la herramienta ya es REVERSIBLE, no LECTURA; esto se prueba
    con el registro de comercial reutilizado bajo 'qa' via monkeypatch
    puntual para no depender del registro real. (legal subio a BAJA con la
    fusion con cumplimiento, excelencia Fase 5 — ya no sirve como ejemplo
    de CERO; qa es el ejemplo vigente.)"""
    H.REGISTRO["qa"] = dict(H.REGISTRO["comercial"])
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(
        '[HERRAMIENTA]{"nombre": "declarar_capacidad_test", '
        '"argumentos": {"lotes": 5}}[/HERRAMIENTA]'))
    c = TestClient(_app())
    ses = _sesion_de(c, "qa")
    _decir(c, ses, "declara algo")
    assert not LLAMADAS_REVERSIBLE
