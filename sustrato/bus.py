"""Bus de eventos del sustrato sobre SQLite (canonico seccion 4).

Semantica FIJADA: entrega at-least-once por polling; idempotencia es
obligacion del consumidor; orden garantizado por id dentro de un topic;
un evento envenenado no bloquea el bus. Cadena de hash por evento (4.4).

La BD es data/kaizen.db en modo WAL. Este modulo NO toca el bus existente
(core/bus.py, core/bus_sqlite.py): conviven; el puente llega en Bloque 2
via el adaptador del cubo Comercial.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sustrato import hashchain
from sustrato.consola import log, ts_iso8601z

_RAIZ = Path(__file__).resolve().parent.parent
def ruta_db_defecto():
    """R-TENANT: la base del sustrato es DATO, vive en la raiz de datos."""
    from core.rutas import dir_data
    return dir_data() / "kaizen.db"

# kaizen.<cubo>.<evento_en_pasado>.v<entero> (canonico 4.2, inmutable)
_RE_TOPIC = re.compile(r"^kaizen\.[a-z_]+\.[a-z_]+\.v[0-9]+$")

_DDL = """
CREATE TABLE IF NOT EXISTS bus_eventos (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT    NOT NULL,
  topic       TEXT    NOT NULL,
  version     INTEGER NOT NULL DEFAULT 1,
  productor   TEXT    NOT NULL,
  payload     TEXT    NOT NULL CHECK (json_valid(payload)),
  hash_prev   TEXT    NOT NULL,
  hash        TEXT    NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_bus_topic_id ON bus_eventos(topic, id);

CREATE TABLE IF NOT EXISTS bus_consumos (
  evento_id   INTEGER NOT NULL REFERENCES bus_eventos(id),
  consumidor  TEXT    NOT NULL,
  ts          TEXT    NOT NULL,
  resultado   TEXT    NOT NULL CHECK (resultado IN ('OK','ERROR')),
  intentos    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (evento_id, consumidor)
);
CREATE INDEX IF NOT EXISTS ix_consumos_consumidor ON bus_consumos(consumidor, evento_id);
"""

# Reintentos de un evento en ERROR antes de considerarlo envenenado y dejarlo en
# la cola de muertos (visible via envenenados(), nunca borrado en silencio).
MAX_INTENTOS_DEFECTO = 3


class TopicInvalido(ValueError):
    pass


def conexion(db_path: Path | None = None) -> sqlite3.Connection:
    """data/kaizen.db por defecto; KAIZEN_DB_PATH lo redirige (tests/entornos
    cuyo sistema de ficheros no soporta SQLite, p.ej. montajes de red)."""
    if db_path is None:
        db_path = os.environ.get("KAIZEN_DB_PATH") or ruta_db_defecto()
    ruta = Path(db_path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    # Migracion aditiva para BDs creadas antes de la columna `intentos` (G-09).
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(bus_consumos)").fetchall()}
    if "intentos" not in columnas:
        conn.execute("ALTER TABLE bus_consumos ADD COLUMN intentos INTEGER NOT NULL DEFAULT 0")
    conn.commit()


@contextmanager
def transaccion(conn: sqlite3.Connection):
    """Transaccion de ESCRITURA con el lock tomado desde el principio.

    `BEGIN IMMEDIATE` es obligatorio en todo par leer-calcular-escribir sobre una
    cadena de hash: con el BEGIN diferido de sqlite3, el SELECT del hash anterior
    corre FUERA del lock y dos procesos concurrentes leen el mismo `hash_prev`;
    ambos insertan y la cadena queda rota para siempre (auditoria 2026-08-02, G-08).

    Reentrante: si el llamante ya tiene una transaccion abierta, no anida (un
    `with conn:` anidado haria commit de la transaccion exterior a medias).
    """
    if conn.in_transaction:
        yield conn                      # el llamante es dueno de la transaccion
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def payload_canonico(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def publicar_en_tx(conn: sqlite3.Connection, topic: str, productor: str, payload: dict,
                   version: int = 1) -> int:
    """Inserta el evento SIN abrir transaccion propia: el llamante es dueno de
    la transaccion (p.ej. registro.transicionar, canonico seccion 5: misma tx).

    IMPORTANTE: esa transaccion debe haberse abierto con `transaccion(conn)`
    (BEGIN IMMEDIATE). Si no, el calculo de `hash_prev` no esta protegido (G-08).
    """
    if not _RE_TOPIC.match(topic):
        raise TopicInvalido(
            f"topic '{topic}' no cumple kaizen.<cubo>.<evento_pasado>.v<n> (canonico 4.2)")
    cuerpo = payload_canonico(payload)
    ts = ts_iso8601z()
    fila = conn.execute(
        "SELECT hash FROM bus_eventos ORDER BY id DESC LIMIT 1").fetchone()
    hash_prev = fila[0] if fila else hashchain.GENESIS
    hash_ = hashchain.calcular(hash_prev, topic, cuerpo, ts)
    cur = conn.execute(
        "INSERT INTO bus_eventos (ts, topic, version, productor, payload, hash_prev, hash) "
        "VALUES (?,?,?,?,?,?,?)",
        (ts, topic, version, productor, cuerpo, hash_prev, hash_))
    return int(cur.lastrowid)


def publicar(conn: sqlite3.Connection, topic: str, productor: str, payload: dict,
             version: int = 1) -> int:
    """Inserta el evento con su hash encadenado, todo en una transaccion."""
    with transaccion(conn):             # BEGIN IMMEDIATE: la cadena no se rompe
        return publicar_en_tx(conn, topic, productor, payload, version)


def _ultimo_procesado(conn: sqlite3.Connection, consumidor: str) -> int:
    fila = conn.execute(
        "SELECT COALESCE(MAX(evento_id), 0) FROM bus_consumos WHERE consumidor=?",
        (consumidor,)).fetchone()
    return int(fila[0])


def _reintentables(conn: sqlite3.Connection, consumidor: str, max_intentos: int) -> list[int]:
    """Ids en ERROR que aun no han agotado los intentos. Por debajo de la marca de
    agua, asi que sin esto el poll no volveria a verlos NUNCA (G-09)."""
    return [int(f[0]) for f in conn.execute(
        "SELECT evento_id FROM bus_consumos WHERE consumidor=? AND resultado='ERROR' "
        "AND intentos < ? ORDER BY evento_id", (consumidor, max_intentos)).fetchall()]


def envenenados(conn: sqlite3.Connection, consumidor: str | None = None,
                max_intentos: int = MAX_INTENTOS_DEFECTO) -> list[dict]:
    """Cola de muertos: eventos que agotaron los intentos y ya no se reentregan.

    No se borran ni se ocultan; se listan para que el operador decida (canonico
    4.3: un evento envenenado no bloquea el bus, pero tampoco desaparece).
    """
    sql = ("SELECT c.evento_id, c.consumidor, c.intentos, c.ts, e.topic "
           "FROM bus_consumos c JOIN bus_eventos e ON e.id = c.evento_id "
           "WHERE c.resultado='ERROR' AND c.intentos >= ?")
    params: list = [max_intentos]
    if consumidor is not None:
        sql += " AND c.consumidor=?"
        params.append(consumidor)
    return [{"evento_id": f[0], "consumidor": f[1], "intentos": f[2], "ts": f[3],
             "topic": f[4]}
            for f in conn.execute(sql + " ORDER BY c.evento_id", params).fetchall()]


def _registrar_consumo(conn: sqlite3.Connection, evento_id: int, consumidor: str,
                       resultado: str) -> None:
    """`intentos` solo suma en ERROR: es el contador de reintentos agotados. Un OK
    lo deja como esta (el evento ya no se volvera a entregar de todos modos)."""
    with transaccion(conn):
        conn.execute(
            "INSERT INTO bus_consumos (evento_id, consumidor, ts, resultado, intentos) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(evento_id, consumidor) DO UPDATE SET ts=excluded.ts, "
            "resultado=excluded.resultado, "
            "intentos=bus_consumos.intentos + (CASE WHEN excluded.resultado='ERROR' "
            "THEN 1 ELSE 0 END)",
            (evento_id, consumidor, ts_iso8601z(), resultado,
             1 if resultado == "ERROR" else 0))


def _entregar(conn: sqlite3.Connection, consumidor: str, handler, fila) -> bool:
    evento_id, ts, topic, version, productor, payload = fila
    evento = {"id": evento_id, "ts": ts, "topic": topic, "version": version,
              "productor": productor, "payload": json.loads(payload)}
    try:
        handler(evento)
    except Exception as exc:  # envenenado: registrar y CONTINUAR (canonico 4.3)
        _registrar_consumo(conn, evento_id, consumidor, "ERROR")
        log("ERROR", "bus", "handler lanzo excepcion; el poll continua",
            evento_id=evento_id, consumidor=consumidor, topic=topic,
            error=type(exc).__name__)
        return False
    _registrar_consumo(conn, evento_id, consumidor, "OK")
    return True


def consumir(conn: sqlite3.Connection, consumidor: str, topics: list[str],
             handler, limite: int = 100,
             max_intentos: int = MAX_INTENTOS_DEFECTO) -> tuple[int, int]:
    """Un poll (canonico 4.3): orden por id, handler idempotente. Devuelve (ok, error).

    Entrega dos conjuntos, siempre en orden de id:
      - los eventos nuevos (id > marca de agua), y
      - los que fallaron antes y no han agotado `max_intentos`.

    El segundo conjunto es lo que hace verdad el at-least-once. Antes la marca de
    agua era MAX(evento_id) de TODOS los consumos, incluidos los ERROR: si el
    evento 5 fallaba y el 6 iba bien, el 5 quedaba por debajo de la marca y no se
    reentregaba jamas (auditoria 2026-08-02, G-09).

    Agotados los intentos, el evento pasa a la cola de muertos: deja de
    reentregarse (no bloquea el bus) pero queda visible en `envenenados()`.
    """
    ultimo = _ultimo_procesado(conn, consumidor)
    reintentables = _reintentables(conn, consumidor, max_intentos)
    marcas = ",".join("?" for _ in topics)
    sql = (f"SELECT id, ts, topic, version, productor, payload FROM bus_eventos "
           f"WHERE topic IN ({marcas}) AND id > ?")
    params: list = [*topics, ultimo]
    if reintentables:
        sql += f" OR (id IN ({','.join('?' for _ in reintentables)}) AND topic IN ({marcas}))"
        params += [*reintentables, *topics]
    filas = conn.execute(sql + " ORDER BY id LIMIT ?", (*params, limite)).fetchall()
    ok = err = 0
    for fila in filas:
        if _entregar(conn, consumidor, handler, fila):
            ok += 1
        else:
            err += 1
    return ok, err


def reintentar(conn: sqlite3.Connection, evento_id: int, consumidor: str, handler=None):
    """Reintento MANUAL de un consumo en ERROR (canonico 4.3).

    Con handler: reentrega ahora (at-least-once explicito) y actualiza el
    registro. Sin handler (CLI): borra la marca ERROR para que el proximo
    poll del consumidor pueda reentregarlo solo si su ultimo id procesado
    es menor; se avisa de esa limitacion por log.
    """
    fila = conn.execute(
        "SELECT resultado FROM bus_consumos WHERE evento_id=? AND consumidor=?",
        (evento_id, consumidor)).fetchone()
    if fila is None:
        return "SIN_REGISTRO"
    if fila[0] == "OK":
        return "YA_OK"
    if handler is not None:
        datos = conn.execute(
            "SELECT id, ts, topic, version, productor, payload FROM bus_eventos WHERE id=?",
            (evento_id,)).fetchone()
        return "OK" if _entregar(conn, consumidor, handler, datos) else "ERROR"
    with conn:
        conn.execute("DELETE FROM bus_consumos WHERE evento_id=? AND consumidor=?",
                     (evento_id, consumidor))
    log("WARN", "bus", "marca ERROR retirada via CLI; reentrega efectiva solo si el "
        "ultimo id procesado del consumidor es menor que el evento",
        evento_id=evento_id, consumidor=consumidor)
    return "MARCA_RETIRADA"


def verificar_cadena(conn: sqlite3.Connection) -> str:
    filas = conn.execute(
        "SELECT id, topic, payload, ts, hash_prev, hash FROM bus_eventos ORDER BY id").fetchall()
    intacta, n, corrupto = hashchain.verificar(filas)
    if intacta:
        return f"CADENA INTACTA ({n} eventos)"
    return f"CADENA CORRUPTA: primer id corrupto = {corrupto} (verificados {n})"


def metrica_diaria(conn: sqlite3.Connection) -> str:
    """Linea INFO | bus | metrica_diaria | eventos=N max_lag_s=X (canonico 4.5)."""
    hoy = ts_iso8601z()[:10]
    eventos = conn.execute(
        "SELECT COUNT(*) FROM bus_eventos WHERE substr(ts,1,10)=?", (hoy,)).fetchone()[0]
    fila = conn.execute(
        "SELECT MAX((julianday(c.ts) - julianday(e.ts)) * 86400.0) "
        "FROM bus_consumos c JOIN bus_eventos e ON e.id = c.evento_id "
        "WHERE substr(c.ts,1,10)=?", (hoy,)).fetchone()
    max_lag = 0.0 if fila[0] is None else max(0.0, float(fila[0]))
    return log("INFO", "bus", "metrica_diaria", eventos=eventos, max_lag_s=f"{max_lag:.1f}")
