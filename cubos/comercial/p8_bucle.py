"""Bucle de datos vertical P8 (canonico seccion 6): el argumentario aprende
del resultado real. Sin magia: agregacion + orden, con candados.

CANDADOS (no negociables):
- Minimo muestral: un par (argumento, segmento) NO entra en ranking hasta
  avanza + rechaza >= 10; por debajo se muestra SIN DATOS SUFICIENTES (n=X).
- Este modulo NO expone NINGUNA funcion de alta, baja, edicion o
  desactivacion de argumentos, ni toca la lista de prohibidos del Brand
  Guardian: eso es accion exclusiva del operador (verificado por test de
  introspeccion). Solo REORDENA la presentacion en briefings.
"""
from __future__ import annotations

import sqlite3

MINIMO_MUESTRAL = 10

_DDL = """
CREATE TABLE IF NOT EXISTS resultado_argumento (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  argumento_id   TEXT NOT NULL,
  segmento       TEXT NOT NULL,
  interaccion_id INTEGER NOT NULL UNIQUE REFERENCES interacciones(id),
  resultado      TEXT NOT NULL CHECK (resultado IN ('avanza','neutro','rechaza')),
  ts             TEXT NOT NULL
);
"""


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def agregados(conn: sqlite3.Connection, segmento: str | None = None) -> list[dict]:
    """Agrega resultados por (argumento_id, segmento). Los 'neutro' no cuentan
    en el denominador (canonico 6.2)."""
    filtro = " WHERE segmento = ?" if segmento else ""
    args = (segmento,) if segmento else ()
    filas = conn.execute(
        "SELECT argumento_id, segmento, "
        "SUM(CASE WHEN resultado='avanza' THEN 1 ELSE 0 END) AS avanza, "
        "SUM(CASE WHEN resultado='rechaza' THEN 1 ELSE 0 END) AS rechaza, "
        "SUM(CASE WHEN resultado='neutro' THEN 1 ELSE 0 END) AS neutro "
        f"FROM resultado_argumento{filtro} GROUP BY argumento_id, segmento",
        args).fetchall()
    out = []
    for argumento_id, seg, avanza, rechaza, neutro in filas:
        n = int(avanza) + int(rechaza)
        out.append({"argumento_id": argumento_id, "segmento": seg,
                    "avanza": int(avanza), "rechaza": int(rechaza),
                    "neutro": int(neutro), "n": n,
                    "tasa_avance": (int(avanza) / n) if n > 0 else None,
                    "suficiente": n >= MINIMO_MUESTRAL})
    return out


def ranking(conn: sqlite3.Connection, segmento: str | None = None) -> list[dict]:
    """Pares con muestra suficiente, ordenados por tasa_avance desc, con campo
    'ranking' 1..N; despues los insuficientes marcados SIN DATOS SUFICIENTES."""
    todos = agregados(conn, segmento)
    aptos = sorted((f for f in todos if f["suficiente"]),
                   key=lambda f: (-f["tasa_avance"], -f["n"], f["argumento_id"]))
    for i, f in enumerate(aptos, start=1):
        f["ranking"] = i
    insuficientes = sorted((f for f in todos if not f["suficiente"]),
                           key=lambda f: (-f["n"], f["argumento_id"]))
    for f in insuficientes:
        f["ranking"] = None
        f["nota"] = f"SIN DATOS SUFICIENTES (n={f['n']})"
    return aptos + insuficientes


def reordenar_argumentos(conn: sqlite3.Connection, argumentos: list[dict],
                         segmento: str) -> list[dict]:
    """REORDENA la presentacion de argumentos para briefings de un segmento:
    primero los rankeados (por tasa), despues el resto en su orden original.
    PROHIBIDO eliminar/editar: devuelve exactamente los mismos elementos."""
    rk = {f["argumento_id"]: f["ranking"] for f in ranking(conn, segmento)
          if f.get("ranking") is not None}
    orden_original = {a.get("id"): i for i, a in enumerate(argumentos)}
    return sorted(argumentos,
                  key=lambda a: (rk.get(a.get("id"), 10**6),
                                 orden_original[a.get("id")]))


def tabla_cli(conn: sqlite3.Connection, segmento: str | None = None) -> str:
    lineas = ["argumento | segmento | n | tasa_avance | ranking"]
    filas = ranking(conn, segmento)
    if not filas:
        lineas.append("(sin resultados registrados)")
    for f in filas:
        tasa = "SIN DATOS" if f["tasa_avance"] is None else f"{f['tasa_avance']:.2f}"
        rk = f["nota"] if f.get("ranking") is None else str(f["ranking"])
        lineas.append(f"{f['argumento_id']} | {f['segmento']} | {f['n']} | {tasa} | {rk}")
    return "\n".join(lineas)
