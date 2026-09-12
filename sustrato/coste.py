"""Contador de costes del sustrato (canonico seccion 9).

Tabla costes en data/kaizen.db + API unica: registrar / comprobar_limite /
autorizar. Hard stop: quien vaya a llamar a una API de pago llama ANTES a
autorizar(estimacion_eur); si gastado + estimacion > limite se lanza
LimiteCosteSuperado y NO se llama. Al 80% del limite: WARN.

Envoltura del contador existente (no duplicar, canonico 9): el repo ya
acumula gasto del dia en .kaizen_cost.json (USD, escrito por
core/cost_tracker.py). comprobar_limite() SUMA ese gasto legado convertido
a EUR con el tipo ya fijado en el repo (EUR_PER_USD = 0.92,
core/cost_tracker.py) para que el freno vea el gasto real combinado.
Dinero: REAL en euros con 4 decimales en calculo, 2 en presentacion.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sustrato import bus, config
from sustrato.consola import log, ts_iso8601z

_RAIZ = Path(__file__).resolve().parent.parent
RUTA_LEGADO_DEFECTO = _RAIZ / ".kaizen_cost.json"
EUR_PER_USD = 0.92  # mismo tipo fijado que core/cost_tracker.py

_DDL = """
CREATE TABLE IF NOT EXISTS costes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  proveedor TEXT NOT NULL,
  concepto TEXT NOT NULL,
  unidades REAL NOT NULL,
  coste_eur REAL NOT NULL,
  cubo TEXT NOT NULL DEFAULT 'comercial',
  estado TEXT NOT NULL DEFAULT 'liquidado'
);
CREATE INDEX IF NOT EXISTS ix_costes_dia ON costes(ts);
"""

PROVEEDORES = ("anthropic", "openrouter", "elevenlabs", "twilio", "otro")
_aviso_80_emitido_hoy: str | None = None


class LimiteCosteSuperado(RuntimeError):
    pass


@dataclass
class Reserva:
    """Importe apartado del presupuesto ANTES de gastar. Se liquida con el coste
    real (`liquidar`) o se devuelve al presupuesto (`liberar`) si no se gasto."""
    id: int
    estimacion_eur: float
    gastado_previo_eur: float


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    # Migracion aditiva para BDs anteriores a la columna `estado` (G-10). Las
    # filas viejas son gasto ya consumado: 'liquidado'.
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(costes)").fetchall()}
    if "estado" not in columnas:
        conn.execute("ALTER TABLE costes ADD COLUMN estado TEXT NOT NULL DEFAULT 'liquidado'")
    conn.commit()


def registrar(conn: sqlite3.Connection, proveedor: str, concepto: str, unidades: float,
              coste_eur: float, cubo: str = "comercial") -> int:
    if proveedor not in PROVEEDORES:
        proveedor = "otro"
    with conn:
        cur = conn.execute(
            "INSERT INTO costes (ts, proveedor, concepto, unidades, coste_eur, cubo) "
            "VALUES (?,?,?,?,?,?)",
            (ts_iso8601z(), proveedor, concepto, round(float(unidades), 4),
             round(float(coste_eur), 4), cubo))
    _avisar_80_si_procede(conn)
    return int(cur.lastrowid)


def _gasto_legado_hoy_eur(ruta_legado: Path) -> float:
    """Puente con .kaizen_cost.json (USD) del contador existente."""
    try:
        datos = json.loads(Path(ruta_legado).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0.0
    if datos.get("date") != ts_iso8601z()[:10]:
        return 0.0
    try:
        return round(float(datos.get("usd", 0.0)) * EUR_PER_USD, 4)
    except (TypeError, ValueError):
        return 0.0


def comprobar_limite(conn: sqlite3.Connection,
                     ruta_legado: Path | None = None) -> float:
    """Gastado hoy en EUR (tabla costes + contador legado del mismo dia)."""
    hoy = ts_iso8601z()[:10]
    fila = conn.execute(
        "SELECT COALESCE(SUM(coste_eur), 0.0) FROM costes WHERE substr(ts,1,10)=?",
        (hoy,)).fetchone()
    propio = round(float(fila[0]), 4)
    legado = _gasto_legado_hoy_eur(ruta_legado or RUTA_LEGADO_DEFECTO)
    return round(propio + legado, 4)


def limite_vigente(conn: sqlite3.Connection) -> float:
    """Limite diario vigente: valor fijado por CLI de operador (config_valores,
    con decision hasheada) si existe; si no, .env/defecto (canonico 7.4 y 9)."""
    try:
        fila = conn.execute(
            "SELECT valor FROM config_valores WHERE clave='LIMITE_COSTE_DIARIO_EUR'"
        ).fetchone()
        if fila is not None:
            return float(fila[0])
    except sqlite3.Error:
        pass
    return config.limite_coste_diario_eur()


def _avisar_80_si_procede(conn: sqlite3.Connection,
                          ruta_legado: Path | None = None) -> None:
    global _aviso_80_emitido_hoy
    hoy = ts_iso8601z()[:10]
    limite = limite_vigente(conn)
    gastado = comprobar_limite(conn, ruta_legado)
    if limite > 0 and gastado >= 0.8 * limite and _aviso_80_emitido_hoy != hoy:
        _aviso_80_emitido_hoy = hoy
        log("WARN", "coste", "gasto diario al 80% o mas del limite",
            gastado_eur=f"{gastado:.2f}", limite_eur=f"{limite:.2f}")


def _comprobar(conn: sqlite3.Connection, estimacion_eur: float,
               ruta_legado: Path | None) -> float:
    """Hard stop. Devuelve el gastado si cabe; lanza si no. NO reserva."""
    limite = limite_vigente(conn)
    gastado = comprobar_limite(conn, ruta_legado)
    if gastado + float(estimacion_eur) > limite:
        log("ERROR", "coste", "hard stop: la estimacion supera el limite diario",
            gastado_eur=f"{gastado:.2f}", estimacion_eur=f"{float(estimacion_eur):.2f}",
            limite_eur=f"{limite:.2f}")
        raise LimiteCosteSuperado(
            f"gastado {gastado:.2f} EUR + estimacion {float(estimacion_eur):.2f} EUR "
            f"> limite diario {limite:.2f} EUR")
    return gastado


def autorizar(conn: sqlite3.Connection, estimacion_eur: float,
              ruta_legado: Path | None = None) -> float:
    """Hard stop SIN reserva. Devuelve gastado hoy si autoriza.

    OJO: comprobar y gastar son dos pasos, asi que dos procesos pueden autorizar
    los dos y rebasar el techo entre ambos. Para codigo nuevo usa `reservar()`,
    que aparta el importe en la misma transaccion en que comprueba.
    Se mantiene por compatibilidad y para comprobaciones de solo lectura.
    """
    with bus.transaccion(conn):
        gastado = _comprobar(conn, estimacion_eur, ruta_legado)
    _avisar_80_si_procede(conn, ruta_legado)
    return gastado


def reservar(conn: sqlite3.Connection, estimacion_eur: float,
             ruta_legado: Path | None = None, *, proveedor: str = "otro",
             concepto: str = "reserva", cubo: str = "comercial") -> Reserva:
    """Hard stop CON reserva atomica: comprobar el techo y apartar el importe
    ocurren dentro del mismo BEGIN IMMEDIATE, asi que dos procesos concurrentes
    no pueden autorizarse el mismo hueco (auditoria 2026-08-02, G-10).

    La reserva cuenta como gasto desde ya. Al terminar hay que cerrarla:
      - `liquidar(conn, reserva, coste_real_eur)` si la llamada se hizo, o
      - `liberar(conn, reserva)` si no llego a hacerse.
    """
    if proveedor not in PROVEEDORES:
        proveedor = "otro"
    est = round(float(estimacion_eur), 4)
    with bus.transaccion(conn):          # BEGIN IMMEDIATE: comprobar + apartar, atomico
        gastado = _comprobar(conn, est, ruta_legado)
        cur = conn.execute(
            "INSERT INTO costes (ts, proveedor, concepto, unidades, coste_eur, cubo, estado) "
            "VALUES (?,?,?,?,?,?,'reservado')",
            (ts_iso8601z(), proveedor, concepto, 0.0, est, cubo))
        reserva_id = int(cur.lastrowid)
    _avisar_80_si_procede(conn, ruta_legado)
    return Reserva(id=reserva_id, estimacion_eur=est, gastado_previo_eur=gastado)


def liquidar(conn: sqlite3.Connection, reserva: Reserva, coste_eur: float,
             unidades: float = 0.0, proveedor: str | None = None,
             concepto: str | None = None) -> float:
    """Cierra la reserva con el coste REAL. Devuelve la diferencia aplicada
    (positiva si la llamada costo mas de lo estimado)."""
    real = round(float(coste_eur), 4)
    # NO se sobreescribe `ts`: es el instante de la reserva y ancla el gasto al
    # dia correcto para comprobar_limite() (atribucion por dia, canonico 9). Antes
    # liquidar() lo reescribia con el instante de liquidacion, asi que una reserva
    # hecha el dia D pero liquidada el dia D+1 se contaba en el limite de D+1 en
    # vez de D.
    sets = ["coste_eur=?", "unidades=?", "estado='liquidado'"]
    params: list = [real, round(float(unidades), 4)]
    if proveedor is not None:
        sets.append("proveedor=?")
        params.append(proveedor if proveedor in PROVEEDORES else "otro")
    if concepto is not None:
        sets.append("concepto=?")
        params.append(concepto)
    with bus.transaccion(conn):
        conn.execute(f"UPDATE costes SET {', '.join(sets)} WHERE id=? AND estado='reservado'",
                     (*params, reserva.id))
    desviacion = round(real - reserva.estimacion_eur, 4)
    if desviacion > 0:
        log("WARN", "coste", "el gasto real supero la estimacion reservada",
            reserva=reserva.id, estimado_eur=f"{reserva.estimacion_eur:.4f}",
            real_eur=f"{real:.4f}")
    _avisar_80_si_procede(conn)
    return desviacion


def liberar(conn: sqlite3.Connection, reserva: Reserva) -> None:
    """Devuelve el importe al presupuesto: la llamada no se hizo."""
    with bus.transaccion(conn):
        conn.execute("DELETE FROM costes WHERE id=? AND estado='reservado'", (reserva.id,))


def reservas_abiertas(conn: sqlite3.Connection) -> list[dict]:
    """Reservas sin liquidar: normalmente vacio. Si crece, alguien no esta
    cerrando sus reservas y el presupuesto aparecera mas gastado de lo real."""
    return [{"id": f[0], "ts": f[1], "concepto": f[2], "eur": f[3]}
            for f in conn.execute(
                "SELECT id, ts, concepto, coste_eur FROM costes WHERE estado='reservado' "
                "ORDER BY id").fetchall()]
