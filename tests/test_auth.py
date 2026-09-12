"""Tests de autenticación del panel (Block D)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from api.server import app


def test_abierto_sin_token_configurado():
    os.environ.pop("KAIZEN_TOKEN", None)
    with TestClient(app) as client:
        assert client.post("/emit").status_code == 200


def test_exige_token_si_configurado():
    os.environ["KAIZEN_TOKEN"] = "secreto"
    try:
        with TestClient(app) as client:
            assert client.post("/emit").status_code == 401                      # sin token
            r = client.post("/emit", headers={"Authorization": "Bearer secreto"})
            assert r.status_code == 200                                          # con token correcto
            assert client.post("/emit", headers={"Authorization": "Bearer mal"}).status_code == 401
    finally:
        os.environ.pop("KAIZEN_TOKEN", None)


def test_ws_rechaza_sin_token():
    os.environ["KAIZEN_TOKEN"] = "secreto"
    try:
        with TestClient(app) as client:
            import websockets.exceptions  # noqa: F401
            try:
                with client.websocket_connect("/ws"):
                    pass
                rechazado = False
            except Exception:
                rechazado = True
            assert rechazado
            # con token sí conecta
            with client.websocket_connect("/ws?token=secreto") as ws:
                assert ws.receive_text()
    finally:
        os.environ.pop("KAIZEN_TOKEN", None)


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
