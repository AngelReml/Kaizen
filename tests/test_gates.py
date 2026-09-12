"""Tests de gates y candado del operador (canonico 7) - Bloque 4."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sustrato import bus as sbus
from sustrato import comite, gates, registro


def _entorno(tmp_path):
    conn = sbus.conexion(tmp_path / "gates_test.db")
    sbus.instalar(conn)
    registro.instalar(conn)
    gates.instalar(conn)
    return conn


def test_fail_safe_ante_excepcion(tmp_path, monkeypatch):
    conn = _entorno(tmp_path)
    gates.set_autonomia(conn, "comercial", "ALTA", "test", es_operador=True)
    def revienta(*a, **k):
        raise RuntimeError("comite roto")
    monkeypatch.setattr(comite, "convocar", revienta)
    v = gates.gate_preventivo(conn, "envio_email_real", {"lead": "x"})
    assert v.veredicto == "FAIL" and v.motivo == "error_interno"   # jamas PASS
    fila = conn.execute(
        "SELECT veredicto FROM verificaciones ORDER BY id DESC LIMIT 1").fetchone()
    assert fila[0] == "FAIL"                                       # verificacion escrita


def test_nivel_insuficiente_no_convoca_comite(tmp_path, monkeypatch):
    conn = _entorno(tmp_path)   # nivel inicial: BAJA
    convocado = []
    monkeypatch.setattr(comite, "convocar", lambda *a, **k: convocado.append(1))
    v = gates.gate_preventivo(conn, "envio_email_real", {})
    assert v.veredicto == "FAIL" and v.motivo == "nivel_insuficiente"
    assert convocado == []      # no gastar tokens en lo ya prohibido
    v2 = gates.gate_preventivo(conn, "leer_registro", {})
    assert v2.veredicto == "PASS"     # CERO: siempre permitido, sin comite
    assert convocado == []


def test_solo_endurecer_programaticamente(tmp_path):
    conn = _entorno(tmp_path)
    gates.set_autonomia(conn, "comercial", "CERO")            # endurecer: libre
    assert gates.nivel_vigente(conn, "comercial") == "CERO"
    with pytest.raises(gates.OperacionReservadaAlOperador):
        gates.set_autonomia(conn, "comercial", "MEDIA")       # relajar sin operador
    with pytest.raises(ValueError):
        gates.set_autonomia(conn, "comercial", "MEDIA", "", es_operador=True)  # sin motivo
    gates.set_autonomia(conn, "comercial", "MEDIA", "prueba controlada", es_operador=True)
    assert gates.nivel_vigente(conn, "comercial") == "MEDIA"
    d = conn.execute("SELECT tipo, detalle FROM decisiones_operador").fetchall()
    assert len(d) == 1 and d[0][0] == "set_autonomia" and "prueba controlada" in d[0][1]
    assert gates.verificar_cadena(conn, "decisiones_operador").startswith("CADENA INTACTA")
    # limite de coste: bajar libre, subir solo operador
    gates.set_limite_coste(conn, 5.0)
    with pytest.raises(gates.OperacionReservadaAlOperador):
        gates.set_limite_coste(conn, 20.0)
    gates.set_limite_coste(conn, 12.0, "demo", es_operador=True)


def test_preflight_robinson(tmp_path):
    conn = _entorno(tmp_path)
    fichero = tmp_path / "aiact.md"
    fichero.write_text("Hola, buenos dias. Le llama el asistente virtual...", encoding="utf-8")
    registro.insertar_lead(conn, id="sin_comprobar", nombre="A", prioridad="ALTA",
                           segmento="otro", cliente_id="__test__")
    registro.insertar_lead(conn, id="vetado", nombre="B", prioridad="ALTA",
                           segmento="otro", cliente_id="__test__", robinson_ok=0)
    registro.insertar_lead(conn, id="limpio", nombre="C", prioridad="ALTA",
                           segmento="otro", cliente_id="__test__", robinson_ok=1)
    v1 = gates.preflight_llamada(conn, "sin_comprobar", "x", fichero)
    assert v1.veredicto == "FAIL" and v1.motivo == "robinson_sin_comprobar"
    v2 = gates.preflight_llamada(conn, "vetado", "x", fichero)
    assert v2.veredicto == "FAIL" and v2.motivo == "en_lista_robinson_no_llamar"
    assert conn.execute("SELECT estado FROM leads WHERE id='vetado'").fetchone()[0] == "NO_LLAMAR"
    v3 = gates.preflight_llamada(conn, "limpio",
                                 "Hola, buenos dias. Le llama el asistente virtual...", fichero)
    assert v3.veredicto == "PASS"
    v4 = gates.preflight_llamada(conn, "limpio", "mensaje inventado no aprobado", fichero)
    assert v4.veredicto == "FAIL" and v4.motivo == "primer_mensaje_no_literal_del_fichero"


def test_accion_inexistente(tmp_path):
    conn = _entorno(tmp_path)
    with pytest.raises(gates.AccionInexistente):
        gates.gate_preventivo(conn, "prometer_condiciones_precios", {})


def test_verificaciones_cadena_detecta_manipulacion(tmp_path):
    conn = _entorno(tmp_path)
    gates.gate_preventivo(conn, "leer_registro", {})
    gates.gate_preventivo(conn, "generar_briefing", {})
    assert gates.verificar_cadena(conn, "verificaciones").startswith("CADENA INTACTA (2")
    conn.execute("UPDATE verificaciones SET detalle='{\"motivo\":\"falso\"}' WHERE id=1")
    conn.commit()
    assert "CORRUPTA" in gates.verificar_cadena(conn, "verificaciones")
