"""Regresion de los dos fallos del bus del sustrato (auditoria 2026-08-02).

G-08  la cadena de hash se rompia con escrituras concurrentes: el SELECT del
      hash anterior corria fuera del lock (BEGIN diferido de sqlite3).
G-09  el at-least-once era falso: la marca de agua era MAX(evento_id) de TODOS
      los consumos, ERROR incluidos, asi que un evento fallido por debajo de la
      marca no se reentregaba jamas.

Estos tests reproducen el fallo concreto, no solo el camino feliz.
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sustrato import bus

TOPIC = "kaizen.comercial.lead_actualizado.v1"


def _bd(tmp_path, nombre="bus_g.db"):
    conn = bus.conexion(tmp_path / nombre)
    bus.instalar(conn)
    return conn


# ─────────────────────────────────────────── G-08 · cadena bajo concurrencia
def test_g08_publicaciones_concurrentes_no_rompen_la_cadena(tmp_path):
    """4 conexiones distintas publicando a la vez: la cadena aguanta."""
    ruta = tmp_path / "concurrente.db"
    bus.instalar(bus.conexion(ruta))
    hilos, por_hilo = 4, 10
    fallos: list[str] = []
    barrera = threading.Barrier(hilos)

    def escritor(i: int) -> None:
        conn = bus.conexion(ruta)
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            barrera.wait()                     # maximiza el solape real
            for j in range(por_hilo):
                bus.publicar(conn, TOPIC, f"h{i}", {"i": i, "j": j})
        except Exception as exc:               # noqa: BLE001
            fallos.append(f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()

    hs = [threading.Thread(target=escritor, args=(i,)) for i in range(hilos)]
    for h in hs:
        h.start()
    for h in hs:
        h.join()

    assert fallos == []
    conn = bus.conexion(ruta)
    assert conn.execute("SELECT COUNT(*) FROM bus_eventos").fetchone()[0] == hilos * por_hilo
    assert bus.verificar_cadena(conn).startswith("CADENA INTACTA")


def test_g08_la_transaccion_es_reentrante(tmp_path):
    """Un llamante dueno de la transaccion (registro.transicionar) no debe
    provocar 'cannot start a transaction within a transaction'."""
    conn = _bd(tmp_path)
    with bus.transaccion(conn):
        bus.publicar_en_tx(conn, TOPIC, "externo", {"a": 1})
        with bus.transaccion(conn):            # anidada: no abre otra
            bus.publicar_en_tx(conn, TOPIC, "interno", {"a": 2})
    assert conn.execute("SELECT COUNT(*) FROM bus_eventos").fetchone()[0] == 2
    assert bus.verificar_cadena(conn).startswith("CADENA INTACTA")


def test_g08_la_transaccion_revierte_si_el_bloque_lanza(tmp_path):
    conn = _bd(tmp_path)
    bus.publicar(conn, TOPIC, "p", {"n": 1})
    with pytest.raises(RuntimeError):
        with bus.transaccion(conn):
            bus.publicar_en_tx(conn, TOPIC, "p", {"n": 2})
            raise RuntimeError("algo peto a mitad")
    assert conn.execute("SELECT COUNT(*) FROM bus_eventos").fetchone()[0] == 1
    assert bus.verificar_cadena(conn).startswith("CADENA INTACTA")


# ─────────────────────────────────────────── G-09 · reentrega de fallidos
def _consumidor(fallan: set):
    vistos: list[int] = []

    def handler(evento):
        n = evento["payload"]["n"]
        vistos.append(n)
        if n in fallan:
            raise RuntimeError("handler roto")

    return handler, vistos


def test_g09_un_evento_fallido_se_reentrega_en_el_siguiente_poll(tmp_path):
    """El fallo original: el 2 falla, el 3 va bien y sube la marca de agua;
    sin el arreglo el 2 no volvia a entregarse nunca."""
    conn = _bd(tmp_path)
    for n in (1, 2, 3):
        bus.publicar(conn, TOPIC, "p", {"n": n})

    fallan = {2}
    handler, vistos = _consumidor(fallan)

    assert bus.consumir(conn, "c", [TOPIC], handler) == (2, 1)
    assert vistos == [1, 2, 3]

    vistos.clear()
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 1)
    assert vistos == [2]                       # <- vuelve, pese a estar bajo la marca

    fallan.clear()                             # el handler se arregla
    vistos.clear()
    assert bus.consumir(conn, "c", [TOPIC], handler) == (1, 0)
    assert vistos == [2]

    vistos.clear()
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 0)
    assert vistos == []                        # ya no queda nada pendiente


def test_g09_al_agotar_intentos_pasa_a_la_cola_de_muertos(tmp_path):
    """No bloquea el bus (canonico 4.3) pero tampoco desaparece en silencio."""
    conn = _bd(tmp_path)
    for n in (1, 2):
        bus.publicar(conn, TOPIC, "p", {"n": n})
    handler, vistos = _consumidor({2})

    for _ in range(bus.MAX_INTENTOS_DEFECTO + 2):
        bus.consumir(conn, "c", [TOPIC], handler)

    envenenados = bus.envenenados(conn, "c")
    assert [e["evento_id"] for e in envenenados] == [2]
    assert envenenados[0]["intentos"] == bus.MAX_INTENTOS_DEFECTO
    assert envenenados[0]["topic"] == TOPIC

    vistos.clear()
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 0)
    assert vistos == []                        # agotado: ya no se reentrega


def test_g09_los_eventos_correctos_no_se_repiten(tmp_path):
    conn = _bd(tmp_path)
    for n in (1, 2, 3):
        bus.publicar(conn, TOPIC, "p", {"n": n})
    handler, vistos = _consumidor(set())
    assert bus.consumir(conn, "c", [TOPIC], handler) == (3, 0)
    vistos.clear()
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 0)
    assert vistos == []


def test_g09_migracion_aditiva_sobre_bd_sin_la_columna(tmp_path):
    """instalar() debe poder actualizar una BD creada antes de `intentos`."""
    ruta = tmp_path / "vieja.db"
    conn = bus.conexion(ruta)
    conn.executescript("""
        CREATE TABLE bus_eventos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, topic TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 1, productor TEXT NOT NULL,
          payload TEXT NOT NULL, hash_prev TEXT NOT NULL, hash TEXT NOT NULL UNIQUE);
        CREATE TABLE bus_consumos (
          evento_id INTEGER NOT NULL, consumidor TEXT NOT NULL, ts TEXT NOT NULL,
          resultado TEXT NOT NULL CHECK (resultado IN ('OK','ERROR')),
          PRIMARY KEY (evento_id, consumidor));
    """)
    conn.commit()
    bus.instalar(conn)                          # no debe reventar
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(bus_consumos)").fetchall()}
    assert "intentos" in columnas
    bus.publicar(conn, TOPIC, "p", {"n": 1})
    handler, vistos = _consumidor({1})
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 1)
    assert bus.consumir(conn, "c", [TOPIC], handler) == (0, 1)   # se reintenta
