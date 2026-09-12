"""Tests del bucle P8 (canonico seccion 6) - Bloque 3. BD temporal; datos
sinteticos SIEMPRE con cliente_id='__test__'."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sustrato import bus as sbus
from sustrato import registro
from cubos.comercial import p8_bucle


def _entorno(tmp_path):
    conn = sbus.conexion(tmp_path / "p8_test.db")
    sbus.instalar(conn)
    registro.instalar(conn)
    p8_bucle.instalar(conn)
    registro.insertar_lead(conn, id="cafe", nombre="Cafe", segmento="cafeteria_especialidad",
                           prioridad="ALTA", cliente_id="__test__")
    registro.insertar_lead(conn, id="hotel", nombre="Hotel", segmento="hotel_boutique",
                           prioridad="MEDIA", cliente_id="__test__")
    return conn


def test_mapeo_resultado(tmp_path):
    conn = _entorno(tmp_path)
    casos = {"interes": "avanza", "compromiso": "avanza", "pedido": "avanza",
             "neutro": "neutro", "no_contesta": "neutro", "ocupado": "neutro",
             "numero_invalido": "neutro", "rechazo": "rechaza"}
    for res_interaccion in casos:
        registro.insertar_interaccion(conn, "cafe", "llamada_manual", res_interaccion,
                                      cliente_id="__test__", argumento_id="arg_x")
    filas = conn.execute(
        "SELECT resultado, COUNT(*) FROM resultado_argumento GROUP BY resultado").fetchall()
    assert dict(filas) == {"avanza": 3, "neutro": 4, "rechaza": 1}
    # interaccion SIN argumento_id: no genera fila P8
    antes = conn.execute("SELECT COUNT(*) FROM resultado_argumento").fetchone()[0]
    registro.insertar_interaccion(conn, "cafe", "email", "interes", cliente_id="__test__")
    assert conn.execute("SELECT COUNT(*) FROM resultado_argumento").fetchone()[0] == antes


def _cargar(conn, lead, arg, avanza, rechaza):
    for _ in range(avanza):
        registro.insertar_interaccion(conn, lead, "llamada_manual", "interes",
                                      cliente_id="__test__", argumento_id=arg)
    for _ in range(rechaza):
        registro.insertar_interaccion(conn, lead, "llamada_manual", "rechazo",
                                      cliente_id="__test__", argumento_id=arg)


def test_candado_minimo_muestral(tmp_path):
    conn = _entorno(tmp_path)
    _cargar(conn, "cafe", "arg_a", avanza=5, rechaza=4)      # n=9: NO rankea
    filas = p8_bucle.ranking(conn)
    assert len(filas) == 1 and filas[0]["ranking"] is None
    assert filas[0]["nota"] == "SIN DATOS SUFICIENTES (n=9)"
    _cargar(conn, "cafe", "arg_a", avanza=1, rechaza=0)      # n=10: SI rankea
    filas = p8_bucle.ranking(conn)
    assert filas[0]["ranking"] == 1 and filas[0]["n"] == 10
    assert abs(filas[0]["tasa_avance"] - 0.6) < 1e-9


def test_no_puede_borrar_argumentos(tmp_path):
    """La API del modulo no expone borrado/edicion/desactivacion (introspeccion)."""
    publicas = [n for n in dir(p8_bucle) if not n.startswith("_")
                and callable(getattr(p8_bucle, n))]
    prohibidas = ("borrar", "eliminar", "delete", "remove", "editar", "edit",
                  "desactivar", "disable", "alta", "baja", "crear_argumento",
                  "update", "actualizar_argumento", "prohibido")
    for nombre in publicas:
        for p in prohibidas:
            assert p not in nombre.lower(), f"funcion sospechosa: {nombre}"
    # y reordenar devuelve exactamente los mismos elementos (ni quita ni edita)
    conn = _entorno(tmp_path)
    args = [{"id": "arg_1", "texto": "t1"}, {"id": "arg_2", "texto": "t2"}]
    out = p8_bucle.reordenar_argumentos(conn, args, "cafeteria_especialidad")
    assert sorted(a["id"] for a in out) == ["arg_1", "arg_2"]
    assert all(a in args for a in out)


def test_ranking_por_segmento(tmp_path):
    conn = _entorno(tmp_path)
    _cargar(conn, "cafe", "arg_a", avanza=8, rechaza=2)    # cafeteria: 0.80
    _cargar(conn, "cafe", "arg_b", avanza=3, rechaza=7)    # cafeteria: 0.30
    _cargar(conn, "hotel", "arg_a", avanza=2, rechaza=8)   # hotel: 0.20
    todas = p8_bucle.ranking(conn)
    assert [(f["argumento_id"], f["segmento"], f["ranking"]) for f in todas] == [
        ("arg_a", "cafeteria_especialidad", 1),
        ("arg_b", "cafeteria_especialidad", 2),
        ("arg_a", "hotel_boutique", 3)]
    solo_cafe = p8_bucle.ranking(conn, "cafeteria_especialidad")
    assert [(f["argumento_id"], f["ranking"]) for f in solo_cafe] == [("arg_a", 1), ("arg_b", 2)]
    # reordenacion de briefing para hotel: arg_a rankeado primero, resto orden original
    args = [{"id": "arg_z"}, {"id": "arg_a"}]
    out = p8_bucle.reordenar_argumentos(conn, args, "hotel_boutique")
    assert [a["id"] for a in out] == ["arg_a", "arg_z"]
