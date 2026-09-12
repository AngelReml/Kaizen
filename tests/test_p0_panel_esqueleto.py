"""D10 P0 — esqueleto: rio SSE con cursor+replay, latido, paridad, paginas base.
Puerta P0: todo evento emitido visible en el rio; paridad RUE↔renderer verde;
reconexion sin perdida (cursor); latido presente en stream y en endpoint."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre, cargar_rue
from panel_mando import nucleo as N
from panel_mando.app import crear_app


def _app_con_datos():
    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    for i in range(3):
        b.publicar(Sobre(tenant_id="laboratorio", tipo="plataforma.diario.entrada",
                         payload={"n": i}, origen="plataforma.panel"))
    app = crear_app(k, mecha_s=0)
    return app, k, b


def _ids_sse(texto: str) -> list[int]:
    return [int(l.split(": ")[1]) for l in texto.splitlines() if l.startswith("id: ")]


def test_latido_vivo():
    app, _, _ = _app_con_datos()
    c = TestClient(app)
    j = c.get("/latido").json()
    assert j["vivo"] is True and j["parado"] is False and j["ts"]


def test_rio_replay_cursor_y_reconexion_sin_perdida():
    app, _, b = _app_con_datos()
    c = TestClient(app)
    r1 = c.get("/rio/laboratorio?desde=-1&ciclos=1")
    ids1 = _ids_sse(r1.text)
    assert ids1 == [0, 1, 2] and ": latido" in r1.text
    b.publicar(Sobre(tenant_id="laboratorio", tipo="plataforma.diario.entrada",
                     payload={"n": 99}, origen="plataforma.panel"))
    r2 = c.get(f"/rio/laboratorio?desde={ids1[-1]}&ciclos=1")
    assert _ids_sse(r2.text) == [3]                  # reconexion: solo lo nuevo, nada perdido


def test_paridad_rue_renderers_verde():
    app, _, _ = _app_con_datos()
    c = TestClient(app)
    j = c.get("/api/paridad").json()
    assert j["cubiertos"] == j["total"] > 60          # L2: todo tipo cubierto
    for tipo in cargar_rue()["tipos"]:
        frase = N.render({"tipo": tipo, "payload": {}})
        assert isinstance(frase, str) and frase       # generico cubre siempre


def test_paginas_base_cargan_y_llevan_latido():
    app, _, _ = _app_con_datos()
    c = TestClient(app)
    for ruta in ("/", "/sala", "/sala/tecnico"):
        r = c.get(ruta)
        assert r.status_code == 200 and 'id="latido"' in r.text
        assert "PARAR TODO" in r.text                 # cabecera siempre
