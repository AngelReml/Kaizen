"""F7 — R-19: CSRF por sesion + identidad desde la sesion (no del cuerpo).

El mecanismo existe y se testea siempre; el enforcement es opt-in (KAIZEN_CSRF_ESTRICTO)
para no romper el uso local. El despliegue persistente (F5) lo activa.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from panel_mando.app import crear_app

CLAVE = "clave-csrf"


def _app(tmp_path, estricto):
    import os
    os.environ["KAIZEN_CSRF_ESTRICTO"] = "true" if estricto else "false"
    k = InMemoryKnowledge()
    app = crear_app(k, token=CLAVE, mecha_s=0)
    c = TestClient(app, raise_server_exceptions=False)
    return app, c


def _login(c):
    c.post("/login", data={"token": CLAVE}, follow_redirects=False)
    return c.cookies.get("kz_csrf")


def test_csrf_estricto_bloquea_sin_token(tmp_path, monkeypatch):
    _, c = _app(tmp_path, estricto=True)
    _login(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"})   # sin X-CSRF
    assert r.status_code == 403
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)


def test_csrf_estricto_pasa_con_token(tmp_path, monkeypatch):
    _, c = _app(tmp_path, estricto=True)
    csrf = _login(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-CSRF": csrf})
    assert r.status_code == 200 and r.json()["estado"] == "TODO_PARADO"
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)


def test_csrf_estricto_exime_api_x_token(tmp_path, monkeypatch):
    _, c = _app(tmp_path, estricto=True)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"}, headers={"X-Token": CLAVE})
    assert r.status_code == 200                       # API server-to-server exenta
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)


def test_sin_estricto_no_rompe_flujo_local(tmp_path, monkeypatch):
    _, c = _app(tmp_path, estricto=False)
    _login(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador"})
    assert r.status_code == 200                       # default off: como siempre
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)


def test_api_csrf_devuelve_token_de_la_sesion(tmp_path, monkeypatch):
    _, c = _app(tmp_path, estricto=False)
    csrf_cookie = _login(c)
    j = c.get("/api/csrf").json()
    assert j["csrf"] and j["csrf"] == csrf_cookie
    monkeypatch.delenv("KAIZEN_CSRF_ESTRICTO", raising=False)
