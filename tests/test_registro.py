"""Tests del registro P9 (canonico seccion 5) - Bloque 2. BD temporal siempre."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sustrato import bus as sbus
from sustrato import registro


def _reg_tmp(tmp_path):
    conn = sbus.conexion(tmp_path / "registro_test.db")
    sbus.instalar(conn)
    registro.instalar(conn)
    registro.insertar_lead(conn, id="l1", nombre="Cafe Test", segmento="cafeteria_especialidad",
                           prioridad="ALTA", cliente_id="__test__")
    return conn


def test_transicion_legal(tmp_path):
    conn = _reg_tmp(tmp_path)
    registro.transicionar(conn, "l1", "CONTACTADO", "primer intento")
    estado = conn.execute("SELECT estado FROM leads WHERE id='l1'").fetchone()[0]
    assert estado == "CONTACTADO"
    fila = conn.execute("SELECT de, a, motivo FROM transiciones_pipeline WHERE lead_id='l1'").fetchone()
    assert fila == ("COLD", "CONTACTADO", "primer intento")


def test_transicion_ilegal_lanza(tmp_path):
    conn = _reg_tmp(tmp_path)
    with pytest.raises(registro.TransicionIlegal):
        registro.transicionar(conn, "l1", "CLIENTE", "salto ilegal COLD->CLIENTE")
    # y NO dejo rastro: ni transicion ni cambio de estado ni evento
    assert conn.execute("SELECT COUNT(*) FROM transiciones_pipeline").fetchone()[0] == 0
    assert conn.execute("SELECT estado FROM leads WHERE id='l1'").fetchone()[0] == "COLD"
    assert conn.execute("SELECT COUNT(*) FROM bus_eventos").fetchone()[0] == 0


def test_transicion_publica_evento_misma_tx(tmp_path, monkeypatch):
    conn = _reg_tmp(tmp_path)
    # 1) exito: evento publicado con payload correcto
    registro.transicionar(conn, "l1", "CONTACTADO", "ok")
    ev = conn.execute(
        "SELECT topic, payload FROM bus_eventos ORDER BY id DESC LIMIT 1").fetchone()
    assert ev[0] == "kaizen.comercial.lead_actualizado.v1"
    assert '"lead_id":"l1"' in ev[1] and '"a":"CONTACTADO"' in ev[1]
    # 2) atomicidad: si la publicacion revienta, TODO se revierte (misma tx)
    def revienta(*a, **k):
        raise RuntimeError("fallo inyectado en publicacion")
    monkeypatch.setattr(registro.bus, "publicar_en_tx", revienta)
    with pytest.raises(RuntimeError):
        registro.transicionar(conn, "l1", "INTERESADO", "debe revertirse")
    assert conn.execute("SELECT estado FROM leads WHERE id='l1'").fetchone()[0] == "CONTACTADO"
    assert conn.execute(
        "SELECT COUNT(*) FROM transiciones_pipeline WHERE a='INTERESADO'").fetchone()[0] == 0


def test_no_llamar_es_terminal_salvo_operador(tmp_path):
    conn = _reg_tmp(tmp_path)
    registro.transicionar(conn, "l1", "NO_LLAMAR", "lista robinson")
    with pytest.raises(registro.TransicionIlegal):
        registro.transicionar(conn, "l1", "COLD", "reactivacion sin permiso")
    registro.transicionar(conn, "l1", "COLD", "orden operador", _forzar_operador=True)
    assert conn.execute("SELECT estado FROM leads WHERE id='l1'").fetchone()[0] == "COLD"


def test_interaccion_y_compromiso_publican_eventos(tmp_path):
    conn = _reg_tmp(tmp_path)
    iid = registro.insertar_interaccion(conn, "l1", "llamada_manual", "interes",
                                        cliente_id="__test__")
    cid = registro.crear_compromiso(conn, "l1", "envio_muestras", "muestra surtido",
                                    "2026-07-10T12:00:00.000Z", interaccion_origen=iid)
    topics = [f[0] for f in conn.execute("SELECT topic FROM bus_eventos ORDER BY id").fetchall()]
    assert "kaizen.comercial.interaccion_registrada.v1" in topics
    assert "kaizen.comercial.compromiso_creado.v1" in topics
    assert cid > 0
