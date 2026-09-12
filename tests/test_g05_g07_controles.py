"""Regresion de tres controles del panel y del gate (auditoria 2026-08-02).

G-05  el CSRF existia, se testeaba... y estaba APAGADO por defecto (la variable
      que lo activaba no estaba ni en el .env). Ahora es activo por defecto.
G-06  las sesiones no caducaban en el servidor: la cookie llevaba max_age, pero
      eso lo respeta el navegador. Un sid robado valia mientras viviera el proceso.
G-07  la "matriz cerrada" de acciones se mutaba en caliente dentro del gate.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from panel_mando.app import crear_app
from sustrato import bus, gates, registro

CLAVE = "clave-g05"


@pytest.fixture
def _sin_var_csrf(monkeypatch):
    """Sin la variable puesta: se prueba el DEFECTO, que es lo que fallaba."""
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)


def _cliente(**kw):
    app = crear_app(InMemoryKnowledge(), token=CLAVE, mecha_s=0, **kw)
    return app, TestClient(app, raise_server_exceptions=False)


def _login(c):
    c.post("/login", data={"token": CLAVE}, follow_redirects=False)
    return c.cookies.get("kz_csrf")


# ─────────────────────────────────────────── G-05 · CSRF activo por defecto
def test_g05_csrf_activo_sin_configurar_nada(_sin_var_csrf):
    """Sin KAIZEN_CSRF_ESTRICTO en el entorno, un POST de navegador sin token
    debe ser rechazado. Antes pasaba: el defecto era 'apagado'."""
    _, c = _cliente()
    _login(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"})
    assert r.status_code == 403


def test_g05_con_token_csrf_pasa(_sin_var_csrf):
    _, c = _cliente()
    csrf = _login(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-CSRF": csrf})
    assert r.status_code == 200


def test_g05_la_api_con_x_token_sigue_exenta(_sin_var_csrf):
    """Un cliente server-to-server no usa cookie: no hay riesgo CSRF."""
    _, c = _cliente()
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-Token": CLAVE})
    assert r.status_code == 200


def test_g05_se_puede_desactivar_explicitamente(monkeypatch):
    """Sigue habiendo interruptor, pero ahora para APAGAR, no para encender."""
    monkeypatch.setenv("KAIZEN_CSRF_ESTRICTO", "false")
    _, c = _cliente()
    _login(c)
    assert c.post("/cmd/parar_todo", json={"quien": "operador"}).status_code == 200


def test_g05_el_js_del_panel_manda_la_cabecera(_sin_var_csrf):
    """El comentario del codigo decia que el JS reenviaba el CSRF; no lo hacia,
    asi que activar el CSRF habria roto el propio boton PARAR TODO."""
    _, c = _cliente()
    _login(c)
    html = c.get("/").text
    assert "X-CSRF" in html, "el JS del panel no manda el token CSRF"
    assert "kz_csrf" in html, "el JS no lee la cookie del token"


# ─────────────────────────────────────────── G-06 · caducidad de sesion
def test_g06_la_sesion_caduca_en_el_servidor(_sin_var_csrf, monkeypatch):
    """Aunque el navegador conserve la cookie, el servidor deja de aceptarla."""
    import panel_mando.app as app_mod

    monkeypatch.setattr(app_mod, "SESION_TTL_S", 1)
    _, c = _cliente()
    _login(c)
    assert c.get("/latido").status_code == 200

    # la cookie sigue en el cliente; lo que expira es el registro del servidor
    time.sleep(1.1)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-CSRF": "x"})
    assert r.status_code in (401, 403)


def test_g06_las_sesiones_caducadas_se_purgan(_sin_var_csrf, monkeypatch):
    """Antes `st.sesiones` era un set que solo crecia."""
    import panel_mando.app as app_mod

    monkeypatch.setattr(app_mod, "SESION_TTL_S", 1)
    app, c = _cliente()
    for _ in range(5):
        c.post("/login", data={"token": CLAVE}, follow_redirects=False)
    assert len(app.state.sesiones) == 5

    time.sleep(1.1)
    c.post("/login", data={"token": CLAVE}, follow_redirects=False)   # dispara la purga
    assert len(app.state.sesiones) == 1
    assert len(app.state.csrf) == 1                                   # el CSRF va con ella


def test_g06_logout_revoca_en_el_servidor(_sin_var_csrf):
    """Sin /logout no habia forma de revocar una sesion sin reiniciar el proceso."""
    app, c = _cliente()
    csrf = _login(c)
    sid = c.cookies.get("kz_sesion")
    assert sid in app.state.sesiones

    c.get("/logout", follow_redirects=False)
    assert sid not in app.state.sesiones
    assert sid not in app.state.csrf

    c.cookies.set("kz_sesion", sid)                 # aunque el atacante conserve el sid
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-CSRF": csrf})
    assert r.status_code in (401, 403)


# ─────────────────────────────────────────── G-07 · matriz no mutable
def test_g07_el_gate_no_muta_la_matriz_global(tmp_path):
    antes = dict(gates.MATRIZ_ACCIONES)
    conn = bus.conexion(tmp_path / "g7.db")
    bus.instalar(conn); registro.instalar(conn); gates.instalar(conn)

    # accion declarada irreversible en cubos/comercial/manifest.json
    gates.gate_preventivo(conn, "contacto_saliente_ia", {"lead": "x"})
    gates.gate_preventivo(conn, "accion_que_no_existe_en_ningun_sitio", {})

    assert gates.MATRIZ_ACCIONES == antes, "el gate mutó la matriz cerrada"


def test_g07_la_matriz_efectiva_incluye_los_manifests():
    efectiva = gates.matriz_efectiva()
    for accion in ("envio_email_real", "contacto_saliente_ia", "compromiso_ante_cliente"):
        assert efectiva[accion] == ("ALTA", True)
    assert set(gates.MATRIZ_ACCIONES).issubset(efectiva)


def test_g07_un_manifest_no_puede_rebajar_una_fila_de_la_matriz_base():
    """La matriz base (canonico 7.2) manda: `setdefault`, no `update`."""
    efectiva = gates.matriz_efectiva()
    for accion, valor in gates.MATRIZ_ACCIONES.items():
        assert efectiva[accion] == valor


def test_g07_la_matriz_efectiva_es_un_valor_nuevo_cada_vez():
    a = gates.matriz_efectiva()
    a["inventada"] = ("CERO", False)
    assert "inventada" not in gates.matriz_efectiva()
