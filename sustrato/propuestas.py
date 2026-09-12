"""Propuestas: la bandeja de decisiones del jefe (Mesa del Jefe).

Cada departamento crea PROPUESTAS (email a aprobar, llamada sugerida con
guion, compromiso a confirmar, contenido). El jefe decide SI o NO desde la
Mesa. Todo queda en el registro y publica eventos al bus. La decision es
irreversible una vez tomada (auditable); ejecutar lo aprobado es un paso
POSTERIOR y separado (gate + comite + ejecutor), jamas automatico aqui.
"""
from __future__ import annotations

import sqlite3

from sustrato import bus
from sustrato.consola import log, ts_iso8601z

TIPOS = ("email_presentacion", "llamada_sugerida", "confirmar_compromiso", "contenido")
ESTADOS = ("pendiente", "aprobada", "rechazada", "ejecutada", "fallida")

_DDL = """
CREATE TABLE IF NOT EXISTS propuestas (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  cliente_id   TEXT NOT NULL,
  cubo         TEXT NOT NULL,
  tipo         TEXT NOT NULL CHECK (tipo IN
    ('email_presentacion','llamada_sugerida','confirmar_compromiso','contenido')),
  titulo       TEXT NOT NULL,
  resumen      TEXT NOT NULL,
  cuerpo       TEXT NOT NULL,
  lead_id      TEXT,
  estado       TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN
    ('pendiente','aprobada','rechazada','ejecutada','fallida')),
  ts_creacion  TEXT NOT NULL,
  ts_decision  TEXT,
  decidido_por TEXT,
  resultado    TEXT
);
"""


class PropuestaYaDecidida(RuntimeError):
    pass


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    try:  # migracion aditiva (canonico 0.3): enlaza tarjeta con argumento para P8
        conn.execute("ALTER TABLE propuestas ADD COLUMN argumento_id TEXT")
    except sqlite3.OperationalError:
        pass  # ya existe
    conn.commit()


def crear(conn: sqlite3.Connection, cubo: str, tipo: str, titulo: str, resumen: str,
          cuerpo: str, lead_id: str | None = None, cliente_id: str = "laboratorio",
          argumento_id: str | None = None) -> int:
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconocido: {tipo}")
    with conn:
        cur = conn.execute(
            "INSERT INTO propuestas (cliente_id, cubo, tipo, titulo, resumen, cuerpo, "
            "lead_id, ts_creacion, argumento_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (cliente_id, cubo, tipo, titulo, resumen, cuerpo, lead_id, ts_iso8601z(),
             argumento_id))
        pid = int(cur.lastrowid)
        bus.publicar_en_tx(conn, f"kaizen.{cubo}.propuesta_creada.v1", cubo,
                           {"propuesta_id": pid, "tipo": tipo, "lead_id": lead_id})
    return pid


def pendientes(conn: sqlite3.Connection, cliente_id: str = "laboratorio") -> list[dict]:
    filas = conn.execute(
        "SELECT id, cubo, tipo, titulo, resumen, cuerpo, lead_id, ts_creacion "
        "FROM propuestas WHERE estado='pendiente' AND cliente_id=? ORDER BY id",
        (cliente_id,)).fetchall()
    claves = ("id", "cubo", "tipo", "titulo", "resumen", "cuerpo", "lead_id", "ts_creacion")
    return [dict(zip(claves, f)) for f in filas]


def decidir(conn: sqlite3.Connection, propuesta_id: int, aprobar: bool,
            quien: str = "jefe") -> str:
    """SI o NO del jefe. Irreversible. Aprobar NO ejecuta nada: deja la
    propuesta en cola de ejecucion (paso posterior con gate + comite)."""
    with bus.transaccion(conn):   # BEGIN IMMEDIATE: check-then-act atomico
        fila = conn.execute("SELECT estado, cubo, tipo, lead_id FROM propuestas WHERE id=?",
                            (propuesta_id,)).fetchone()
        if fila is None:
            raise KeyError(f"propuesta inexistente: {propuesta_id}")
        estado, cubo, tipo, lead_id = fila
        if estado != "pendiente":
            raise PropuestaYaDecidida(f"la propuesta {propuesta_id} ya esta '{estado}'")
        nuevo = "aprobada" if aprobar else "rechazada"
        cur = conn.execute(
            "UPDATE propuestas SET estado=?, ts_decision=?, decidido_por=? "
            "WHERE id=? AND estado='pendiente'",
            (nuevo, ts_iso8601z(), quien, propuesta_id))
        if cur.rowcount == 0:
            # decidida por otro proceso entre el SELECT y el UPDATE
            raise PropuestaYaDecidida(f"la propuesta {propuesta_id} ya esta decidida")
        bus.publicar_en_tx(conn, f"kaizen.{cubo}.propuesta_decidida.v1", "mesa_jefe",
                           {"propuesta_id": propuesta_id, "decision": nuevo,
                            "tipo": tipo, "lead_id": lead_id, "por": quien})
    log("INFO", "propuestas", "decision del jefe", propuesta_id=propuesta_id,
        decision=nuevo, por=quien)
    return nuevo


def resumen_ayer(conn: sqlite3.Connection, cliente_id: str = "laboratorio") -> dict:
    """Cifras simples para el saludo de la Mesa. Sin datos -> ceros honestos
    de tablas que existen; None si ni siquiera hay tablas."""
    try:
        decididas = conn.execute(
            "SELECT COUNT(*) FROM propuestas WHERE cliente_id=? AND "
            "substr(COALESCE(ts_decision,''),1,10)=date('now','-1 day')",
            (cliente_id,)).fetchone()[0]
        transiciones = conn.execute(
            "SELECT COUNT(*) FROM transiciones_pipeline WHERE substr(ts,1,10)=date('now','-1 day')"
        ).fetchone()[0]
        pend = conn.execute(
            "SELECT COUNT(*) FROM propuestas WHERE estado='pendiente' AND cliente_id=?",
            (cliente_id,)).fetchone()[0]
        return {"decisiones_ayer": int(decididas), "movimientos_ayer": int(transiciones),
                "pendientes_hoy": int(pend)}
    except sqlite3.Error:
        return {"decisiones_ayer": None, "movimientos_ayer": None, "pendientes_hoy": None}
