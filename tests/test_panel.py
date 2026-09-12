"""Tests del panel (FastAPI + WebSocket). Requiere fastapi/httpx. Runnable con python o pytest."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os

from fastapi.testclient import TestClient

from api.server import app

# Autosuficiencia (correccion D25): api.server carga .env al importarse y
# KAIZEN_TOKEN entra al entorno; en la suite completa test_auth.py lo
# limpiaba y este fichero dependia de ese orden. El pop va DESPUES del
# import (load_dotenv ya corrio). Tests del modo abierto-bajo-pytest.
os.environ.pop("KAIZEN_TOKEN", None)


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200 and r.json()["ok"] is True


def test_index_sirve_html():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200 and "KAIZEN" in r.text


def test_ws_replay_al_conectar():
    """Al conectar, el WebSocket reenvía el historial del bus (incl. el arranque)."""
    import json
    with TestClient(app) as client:
        # garantiza que hay al menos un evento en el historial
        client.post(f"/emit?marker={uuid.uuid4().hex}")
        with client.websocket_connect("/ws") as ws:
            ev = json.loads(ws.receive_text())
            assert "type" in ev and "company" in ev


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)


# -----------------------------------------------------------------------------
#  Panel del Director del SUSTRATO (canonico seccion 8) - Bloque 5.
#  Seccion aditiva: no toca los tests del panel FastAPI de arriba.
# -----------------------------------------------------------------------------
from sustrato import bus as _sbus  # noqa: E402
from panel import director as _director  # noqa: E402


def test_sin_datos_no_finge(tmp_path=None):
    """Sin tablas instaladas, el panel muestra SIN DATOS: jamas cero fingido."""
    import tempfile
    base = Path(tmp_path) if tmp_path is not None else Path(tempfile.mkdtemp())
    conn = _sbus.conexion(base / "panel_vacio.db")   # BD vacia: ni una tabla
    assert _director.datos_pipeline(conn) is None
    assert _director.compromisos_pendientes(conn) is None
    assert _director.ultimas_verificaciones(conn) is None
    assert _director.coste_del_dia(conn) is None
    assert _director.ranking_p8_top(conn) is None
    destino = base / "director_vacio.html"
    _director.render_html(conn, destino)
    html = destino.read_text(encoding="utf-8")
    assert html.count("SIN DATOS") >= 5               # una por seccion
    assert ">0<" not in html                          # ningun cero inventado


def test_html_se_genera(tmp_path=None):
    import tempfile
    base = Path(tmp_path) if tmp_path is not None else Path(tempfile.mkdtemp())
    from sustrato import coste as _coste
    from sustrato import gates as _gates
    from sustrato import registro as _registro
    conn = _sbus.conexion(base / "panel_datos.db")
    _sbus.instalar(conn); _registro.instalar(conn); _gates.instalar(conn); _coste.instalar(conn)
    _registro.insertar_lead(conn, id="l1", nombre="Cafe & Te", prioridad="ALTA",
                            segmento="cafeteria_especialidad", cliente_id="__test__")
    _registro.transicionar(conn, "l1", "CONTACTADO", "test")
    _registro.crear_compromiso(conn, "l1", "callback", "volver a llamar <script>",
                               "2026-07-09T10:00:00.000Z")
    _gates.gate_preventivo(conn, "leer_registro", {})
    destino = base / "director.html"
    ruta = _director.render_html(conn, destino)
    assert ruta.exists()
    html = ruta.read_text(encoding="utf-8")
    assert "#F5F1E8" in html and "#1A1A1A" in html and "#C09244" in html  # colores fijados
    assert "<script" not in html.lower().replace("&lt;script", "")        # sin JS y escapado
    assert "http" not in html.split("</style>")[1][:2000] or "cdn" not in html.lower()
    assert "Cafe &amp; Te" in html                                        # escapado correcto
    assert "CONTACTADO" in html and "callback" in html and "PASS" in html
    # regeneracion entera: segunda llamada reescribe sin duplicar
    _director.render_html(conn, destino)
    assert ruta.read_text(encoding="utf-8").count("<h1") == 1
