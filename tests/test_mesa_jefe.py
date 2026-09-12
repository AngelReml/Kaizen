"""Tests de propuestas + Mesa del Jefe (S1 del plan 30-agosto)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from sustrato import bus as sbus
from sustrato import propuestas


def _conn(tmp_path):
    conn = sbus.conexion(tmp_path / "mesa.db")
    sbus.instalar(conn)
    propuestas.instalar(conn)
    return conn


def test_crear_y_pendientes(tmp_path):
    conn = _conn(tmp_path)
    pid = propuestas.crear(conn, "comercial", "email_presentacion",
                           "Presentarnos a Cafe X", "Email corto de presentacion.",
                           "Hola...", lead_id="cafe_x")
    tarjetas = propuestas.pendientes(conn)
    assert len(tarjetas) == 1 and tarjetas[0]["id"] == pid
    ev = conn.execute("SELECT topic FROM bus_eventos ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert ev == "kaizen.comercial.propuesta_creada.v1"


def test_decidir_es_irreversible_y_publica(tmp_path):
    conn = _conn(tmp_path)
    pid = propuestas.crear(conn, "comercial", "llamada_sugerida", "Llama tu al Hotel Z",
                           "Guion de 30 segundos.", "Guion...", lead_id="hotel_z")
    assert propuestas.decidir(conn, pid, True, quien="alejandro") == "aprobada"
    with pytest.raises(propuestas.PropuestaYaDecidida):
        propuestas.decidir(conn, pid, False)
    ev = conn.execute("SELECT topic, payload FROM bus_eventos ORDER BY id DESC LIMIT 1").fetchone()
    assert ev[0] == "kaizen.comercial.propuesta_decidida.v1" and '"aprobada"' in ev[1]
    assert propuestas.pendientes(conn) == []       # ya no esta en la Mesa


def test_mesa_api_y_pin(tmp_path, monkeypatch):
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "mesa_api.db"))
    monkeypatch.setenv("MESA_PIN", "246810")
    import mesa_jefe
    with TestClient(mesa_jefe.app) as c:
        assert c.get("/api/tarjetas").status_code == 401          # sin PIN, fuera
        r = c.get("/api/tarjetas?pin=246810")
        assert r.status_code == 200
        conn = sbus.conexion(); sbus.instalar(conn); propuestas.instalar(conn)
        pid = propuestas.crear(conn, "comercial", "email_presentacion", "T", "R", "C")
        r2 = c.post("/api/decidir?pin=246810", json={"id": pid, "aprobar": False})
        assert r2.status_code == 200 and r2.json()["estado"] == "rechazada"
        r3 = c.post("/api/decidir?pin=246810", json={"id": pid, "aprobar": True})
        assert r3.status_code == 409                              # irreversible
        assert c.get("/?pin=246810").status_code == 200
