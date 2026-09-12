# -*- coding: utf-8 -*-
"""Colmena — chat de directores por cubo (panel_mando/colmena.py).

Cubre: alta de agentes con uid unico y sellado; turno individual con sello en
cadena; propuesta -> tarjeta en ColaSustrato y aprobacion por los endpoints
EXISTENTES del panel; rechazo por autonomia CERO, por accion no declarada y
por panico; sala con @menciones; CSRF heredado del prefijo /cmd/; login con
destino `ir` seguro. Ningun test llama al modelo real: _llm se sustituye."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core.knowledge import InMemoryKnowledge
from panel_mando import colmena
from panel_mando.app import crear_app
from sustrato import bus

EMPRESA = "laboratorio"


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """BD del sustrato en tmp (KAIZEN_DB_PATH) y presupuesto sin depender del
    fichero real de coste del repo. El import de claude_client carga el .env
    real (KAIZEN_TOKEN incluido): se retira para que crear_app() sin token sea
    de verdad local-abierto, como en el resto de la suite."""
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)
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


def _agentes(c):
    return c.get(f"/api/colmena/agentes?empresa={EMPRESA}").json()


def _sesion_de(j, cubo):
    return next(a["sesion"] for a in j["agentes"] if a["cubo"] == cubo)


def _hilo(c, sesion):
    return c.get(f"/api/colmena/hilo?empresa={EMPRESA}&sesion={sesion}").json()


# ── alta e identidad ─────────────────────────────────────────────────────────

def test_alta_10_agentes_uid_unico_sellado_e_idempotente(entorno):
    c = TestClient(_app())
    j = _agentes(c)
    assert len(j["agentes"]) == 10
    uids = [a["uid"] for a in j["agentes"]]
    assert len(set(uids)) == 10                       # unicos de verdad
    for a in j["agentes"]:
        assert a["uid"].startswith("KZ-" + a["cubo"].upper() + "-")
        assert a["role_id"] == "director_" + a["cubo"]
    assert j["sala"]["titulo"] == "Sala de Reunion"
    j2 = _agentes(c)                                  # idempotente: mismos uid
    assert [a["uid"] for a in j2["agentes"]] == uids
    conn = bus.conexion()
    try:
        n = conn.execute("SELECT COUNT(*) FROM bus_eventos WHERE topic="
                         "'kaizen.colmena.agente_registrado.v1'").fetchone()[0]
        assert n == 10                                # un alta sellada por agente
        assert bus.verificar_cadena(conn).startswith("CADENA INTACTA")
    finally:
        conn.close()


# ── turno individual ─────────────────────────────────────────────────────────

def test_turno_individual_responde_y_sella(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("Hola jefe. SIN DATOS de leads."))
    c = TestClient(_app())
    ses = _sesion_de(_agentes(c), "comercial")
    r = _decir(c, ses, "hola, ¿como va el pipeline?")
    assert r.status_code == 200 and r.json()["turnos"] == 1
    msjs = _hilo(c, ses)["mensajes"]
    assert [m["autor_tipo"] for m in msjs] == ["operador", "director"]
    assert msjs[1]["autor_id"] == "director_comercial"
    assert "SIN DATOS" in msjs[1]["texto"]
    assert all(m["evento_id"] for m in msjs)          # cada mensaje, sellado
    conn = bus.conexion()
    try:
        assert bus.verificar_cadena(conn).startswith("CADENA INTACTA")
    finally:
        conn.close()


# ── propuestas -> tarjetas ───────────────────────────────────────────────────

PROPONE_REV = ('Puedo preparar un borrador interno.\n'
               '[PROPUESTA]{"accion": "preparar_borrador_informe", '
               '"clase": "REVERSIBLE", "resumen": "Borrador interno del informe"}'
               '[/PROPUESTA]')


def test_propuesta_crea_tarjeta_y_se_aprueba_por_el_panel(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROPONE_REV))
    app = _app()
    c = TestClient(app)
    ses = _sesion_de(_agentes(c), "marketing")
    _decir(c, ses, "prepara el informe")
    j = _hilo(c, ses)
    tarjetas = [m for m in j["mensajes"] if m["ap_id"]]
    assert len(tarjetas) == 1
    ap_id = tarjetas[0]["ap_id"]
    assert j["tarjetas"][ap_id]["estado"] == "PENDIENTE"
    assert j["tarjetas"][ap_id]["cubo"] == "marketing"
    # El boton del chat llama al endpoint EXISTENTE del panel: un solo camino.
    r = c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": ap_id, "quien": "operador"})
    assert r.status_code == 200 and r.json()["estado"] == "EJECUTADA"
    t = c.get(f"/api/colmena/tarjetas?empresa={EMPRESA}").json()["tarjetas"]
    assert t[ap_id]["estado"] == "EJECUTADA"


def test_propuesta_con_autonomia_cero_se_rechaza(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROPONE_REV))
    c = TestClient(_app())
    # legal subio a BAJA con la fusion con cumplimiento (excelencia Fase 5);
    # qa sigue en CERO — es el ejemplo vigente.
    ses = _sesion_de(_agentes(c), "qa")               # qa: CERO
    _decir(c, ses, "propon algo")
    j = _hilo(c, ses)
    assert not [m for m in j["mensajes"] if m["ap_id"]]           # sin tarjeta
    assert any(m["autor_tipo"] == "sistema" and "rechazada" in m["texto"]
               for m in j["mensajes"])
    assert j["tarjetas"] == {}


def test_irrext_solo_si_esta_declarada_en_el_manifest(entorno, monkeypatch):
    no_declarada = ('X\n[PROPUESTA]{"accion": "enviar_regalos", '
                    '"clase": "IRREVERSIBLE-EXTERNA", "resumen": "r"}[/PROPUESTA]')
    declarada = ('X\n[PROPUESTA]{"accion": "envio_email_real", '
                 '"clase": "IRREVERSIBLE-EXTERNA", "resumen": "email al lead"}'
                 '[/PROPUESTA]')
    c = TestClient(_app())
    ses = _sesion_de(_agentes(c), "comercial")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(colmena, "_llm", _llm_fijo(no_declarada))
        _decir(c, ses, "manda regalos")
    j = _hilo(c, ses)
    assert not [m for m in j["mensajes"] if m["ap_id"]]
    assert any("no declarada" in m["texto"] for m in j["mensajes"]
               if m["autor_tipo"] == "sistema")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(colmena, "_llm", _llm_fijo(declarada))
        _decir(c, ses, "propon el email")
    j = _hilo(c, ses)
    tarjetas = [m for m in j["mensajes"] if m["ap_id"]]
    assert len(tarjetas) == 1
    assert j["tarjetas"][tarjetas[0]["ap_id"]]["clase"] == "IRREVERSIBLE-EXTERNA"


def test_panico_activo_no_admite_propuestas(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo(PROPONE_REV))
    c = TestClient(_app())
    ses = _sesion_de(_agentes(c), "marketing")
    c.post("/cmd/parar_todo", json={"quien": "operador", "motivo": "test"})
    _decir(c, ses, "propon algo")
    j = _hilo(c, ses)
    assert not [m for m in j["mensajes"] if m["ap_id"]]
    assert any("PARAR TODO" in m["texto"] for m in j["mensajes"]
               if m["autor_tipo"] == "sistema")
    c.post("/cmd/reanudar", json={"quien": "operador"})


# ── sala ─────────────────────────────────────────────────────────────────────

def test_sala_con_mencion_solo_responde_el_mencionado(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("Voy."))
    c = TestClient(_app())
    j = _agentes(c)
    sala = j["sala"]["sesion"]
    r = _decir(c, sala, "@comercial ¿como va tu semana?")
    assert r.json()["turnos"] == 1
    msjs = _hilo(c, sala)["mensajes"]
    directores = [m for m in msjs if m["autor_tipo"] == "director"]
    assert [m["autor_id"] for m in directores] == ["director_comercial"]


def test_sala_sin_mencion_abre_turno_a_los_10(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("Presente."))
    c = TestClient(_app())
    sala = _agentes(c)["sala"]["sesion"]
    r = _decir(c, sala, "buenos dias a todos")
    assert r.json()["turnos"] == 10
    msjs = _hilo(c, sala)["mensajes"]
    assert len([m for m in msjs if m["autor_tipo"] == "director"]) == 10


# ── seguridad ────────────────────────────────────────────────────────────────

def test_csrf_cubre_los_post_de_colmena(entorno, monkeypatch):
    """El prefijo /cmd/colmena/* hereda el middleware CSRF (R-19): navegador
    con cookie de sesion y sin X-CSRF -> 403; con X-CSRF -> pasa."""
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("ok"))
    c = TestClient(_app(token="secreta"))
    r = c.post("/login", data={"token": "secreta"}, follow_redirects=False)
    assert r.status_code == 303
    ses = _sesion_de(c.get(f"/api/colmena/agentes?empresa={EMPRESA}").json(),
                     "comercial")
    sin = c.post("/cmd/colmena/decir",
                 json={"empresa": EMPRESA, "sesion": ses, "texto": "hola"})
    assert sin.status_code == 403                     # cookie sin CSRF: fuera
    csrf = c.get("/api/csrf").json()["csrf"]
    con = c.post("/cmd/colmena/decir",
                 json={"empresa": EMPRESA, "sesion": ses, "texto": "hola",
                       "espera": True},
                 headers={"X-CSRF": csrf})
    assert con.status_code == 200


def test_sin_auth_no_hay_colmena(entorno):
    c = TestClient(_app(token="secreta"))
    assert c.get(f"/api/colmena/agentes?empresa={EMPRESA}").status_code == 401
    assert c.get("/chat", follow_redirects=False).status_code == 303   # -> /login


def test_login_ir_solo_rutas_internas(entorno):
    c = TestClient(_app(token="secreta"))
    r = c.get("/login?token=secreta&ir=/chat", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/chat"
    c2 = TestClient(_app(token="secreta"))
    r2 = c2.get("/login?token=secreta&ir=//evil.com/x", follow_redirects=False)
    assert r2.headers["location"] == "/"              # anti open-redirect
    c3 = TestClient(_app(token="secreta"))
    r3 = c3.get("/login?token=secreta&ir=https://evil.com", follow_redirects=False)
    assert r3.headers["location"] == "/"


def test_identidad_del_cuerpo_no_suplanta_con_sesion(entorno, monkeypatch):
    """Con sesion de navegador, quien = 'operador' SIEMPRE (R-19): un cuerpo
    con quien='atacante' no firma el mensaje."""
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("ok"))
    c = TestClient(_app(token="secreta"))
    c.post("/login", data={"token": "secreta"})
    csrf = c.get("/api/csrf").json()["csrf"]
    ses = _sesion_de(c.get(f"/api/colmena/agentes?empresa={EMPRESA}").json(),
                     "comercial")
    c.post("/cmd/colmena/decir",
           json={"empresa": EMPRESA, "sesion": ses, "texto": "hola",
                 "quien": "atacante", "espera": True},
           headers={"X-CSRF": csrf})
    msjs = _hilo(c, ses)["mensajes"]
    assert msjs[0]["autor_id"] == "operador"


# ── rio SSE ──────────────────────────────────────────────────────────────────

def test_rio_entrega_mensajes_y_meta(entorno, monkeypatch):
    monkeypatch.setattr(colmena, "_llm", _llm_fijo("Al dia."))
    c = TestClient(_app())
    ses = _sesion_de(_agentes(c), "ops")
    _decir(c, ses, "¿estado?")
    r = c.get(f"/api/colmena/rio?empresa={EMPRESA}&desde=-1&ciclos=1")
    assert r.status_code == 200
    assert "event: meta" in r.text and ": latido" in r.text
    assert "Al dia." in r.text                        # el mensaje viaja por el rio
