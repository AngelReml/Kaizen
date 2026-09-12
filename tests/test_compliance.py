"""Tests de hooks de compliance (canonico 10.2) - Bloque 5."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sustrato import bus as sbus
from sustrato import gates, registro

V2 = ("Hola, buenos dias. Le llama el asistente virtual de Ivan Carbonell, del obrador "
      "Reposteria Laboratorio, en Cieza - soy un sistema automatizado que habla con la voz "
      "de Ivan, con su autorizacion.")


def _entorno(tmp_path):
    conn = sbus.conexion(tmp_path / "compliance_test.db")
    sbus.instalar(conn); registro.instalar(conn); gates.instalar(conn)
    registro.insertar_lead(conn, id="ok", nombre="Lead OK", prioridad="ALTA",
                           segmento="otro", cliente_id="__test__", robinson_ok=1)
    registro.insertar_lead(conn, id="null", nombre="Lead NULL", prioridad="ALTA",
                           segmento="otro", cliente_id="__test__")
    fichero = tmp_path / "aiact_primeros_mensajes.md"
    fichero.write_text("# Variantes aprobadas\n\n1. " + V2 + "\n", encoding="utf-8")
    return conn, fichero


def test_primer_mensaje_debe_ser_literal_del_fichero(tmp_path):
    conn, fichero = _entorno(tmp_path)
    v = gates.preflight_llamada(conn, "ok", V2, fichero)
    assert v.veredicto == "PASS"
    v2 = gates.preflight_llamada(conn, "ok", "Hola, soy Ivan.", fichero)  # no literal
    assert v2.veredicto == "FAIL" and v2.motivo == "primer_mensaje_no_literal_del_fichero"
    v3 = gates.preflight_llamada(conn, "ok", V2, tmp_path / "no_existe.md")
    assert v3.veredicto == "FAIL" and v3.motivo == "fichero_aiact_ausente"
    v4 = gates.preflight_llamada(conn, "ok", None, fichero)
    assert v4.veredicto == "FAIL" and v4.motivo == "primer_mensaje_no_configurado"


def test_robinson_null_bloquea(tmp_path):
    conn, fichero = _entorno(tmp_path)
    v = gates.preflight_llamada(conn, "null", V2, fichero)
    assert v.veredicto == "FAIL" and v.motivo == "robinson_sin_comprobar"
    fila = conn.execute(
        "SELECT veredicto FROM verificaciones WHERE accion='preflight_llamada' "
        "ORDER BY id DESC LIMIT 1").fetchone()
    assert fila[0] == "FAIL"   # el bloqueo queda verificado y hasheado


def test_variante_aprobada_pasa_preflight(tmp_path):
    """E2E contra el fichero AI Act del TENANT (R-TENANT: ya no hay un fichero
    de runtime unico en el repo; cada tenant tiene el suyo en su ficha)."""
    conn, _ = _entorno(tmp_path)
    aprobada = gates.variantes_aprobadas(gates.ruta_aiact_voz("laboratorio"))[0]
    v = gates.preflight_llamada(conn, "ok", aprobada, empresa="laboratorio")
    assert v.veredicto == "PASS" and v.motivo == "robinson_ok_y_aiact_literal"
    v2 = gates.preflight_llamada(conn, "ok", "Hola, soy un comercial, un placer.",
                                 empresa="laboratorio")
    assert v2.veredicto == "FAIL" and v2.motivo == "primer_mensaje_no_literal_del_fichero"


def test_preflight_sin_tenant_falla_cerrado(tmp_path):
    """Un preflight de cumplimiento sin declarar POR QUIEN se llama no es valido."""
    conn, _ = _entorno(tmp_path)
    v = gates.preflight_llamada(conn, "ok", "lo que sea")
    assert v.veredicto == "FAIL" and v.motivo == "tenant_no_declarado"
