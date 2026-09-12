"""Panel del Director (canonico seccion 8) — verificacion visible (P3).

Solo LECTURA: ninguna funcion de este modulo escribe en tablas de negocio.
Regla de honestidad: si un dato no existe se muestra SIN DATOS, jamas un
cero fingido ni un placeholder inventado.

Bloque 2: version minima CLI (pipeline + compromisos).
Bloque 5: version completa (verificaciones, coste, P8 top-5) + HTML estatico.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sustrato import config, coste
from sustrato.consola import safe_print, ts_iso8601z

_RAIZ = Path(__file__).resolve().parent.parent
RUTA_HTML = Path(__file__).resolve().parent / "director.html"
ESTADOS_ORDEN = ("COLD", "CONTACTADO", "INTERESADO", "COMPROMETIDO", "CLIENTE",
                 "NO_LLAMAR", "DESCARTADO")


def _hay_tabla(conn: sqlite3.Connection, nombre: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nombre,)).fetchone() is not None


def _ts_local_madrid(ts_z: str) -> str:
    """ISO8601Z -> hora local Europe/Madrid para presentacion. Si la base de
    zonas horarias no esta disponible (Windows sin tzdata), se muestra UTC
    etiquetado: honesto, nunca una conversion inventada."""
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(ts_z.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts_z[:16].replace("T", " ") + " UTC"


# -- lecturas (todas devuelven None si el dato NO existe) ---------------------
def datos_pipeline(conn: sqlite3.Connection) -> dict | None:
    if not _hay_tabla(conn, "leads"):
        return None
    filas = conn.execute("SELECT estado, COUNT(*) FROM leads GROUP BY estado").fetchall()
    if not filas:
        return None
    conteo = {e: 0 for e in ESTADOS_ORDEN}
    conteo.update({e: n for e, n in filas})
    return conteo


def compromisos_pendientes(conn: sqlite3.Connection) -> list | None:
    if not _hay_tabla(conn, "compromisos"):
        return None
    return conn.execute(
        "SELECT c.id, c.lead_id, l.nombre, c.tipo, c.descripcion, c.fecha_limite "
        "FROM compromisos c LEFT JOIN leads l ON l.id = c.lead_id "
        "WHERE c.estado='pendiente' ORDER BY c.fecha_limite").fetchall()


def ultimas_verificaciones(conn: sqlite3.Connection, n: int = 10) -> list | None:
    if not _hay_tabla(conn, "verificaciones"):
        return None
    return conn.execute(
        "SELECT ts, accion, veredicto, confianza FROM verificaciones "
        "ORDER BY id DESC LIMIT ?", (n,)).fetchall()


def coste_del_dia(conn: sqlite3.Connection) -> tuple | None:
    if not _hay_tabla(conn, "costes"):
        return None
    return (coste.comprobar_limite(conn), config.limite_coste_diario_eur())


def ranking_p8_top(conn: sqlite3.Connection, n: int = 5) -> list | None:
    if not _hay_tabla(conn, "resultado_argumento"):
        return None
    try:
        from cubos.comercial import p8_bucle
    except ImportError:
        return None
    filas = [f for f in p8_bucle.ranking(conn) if f["n"] >= p8_bucle.MINIMO_MUESTRAL]
    return filas[:n]


# -- salida CLI ---------------------------------------------------------------
def _linea(texto: str = "") -> None:
    safe_print(texto)


def render_cli(conn: sqlite3.Connection) -> None:
    _linea("PANEL DEL DIRECTOR - KAIZEN (solo lectura)")
    _linea(f"generado: {_ts_local_madrid(ts_iso8601z())} (Europe/Madrid)")
    _linea()
    _linea("== PIPELINE POR ESTADO ==")
    pipe = datos_pipeline(conn)
    if pipe is None:
        _linea("SIN DATOS")
    else:
        for e in ESTADOS_ORDEN:
            _linea(f"  {e:<13} {pipe.get(e, 0)}")
    _linea()
    _linea("== COMPROMISOS PENDIENTES (por fecha limite) ==")
    comps = compromisos_pendientes(conn)
    if comps is None:
        _linea("SIN DATOS")
    elif not comps:
        _linea("  (ninguno pendiente)")
    else:
        for cid, lead_id, nombre, tipo, desc, fecha in comps:
            _linea(f"  [{fecha[:10]}] #{cid} {nombre or lead_id} - {tipo}: {desc[:60]}")
    _linea()
    _linea("== ULTIMAS 10 VERIFICACIONES ==")
    vers = ultimas_verificaciones(conn)
    if vers is None:
        _linea("SIN DATOS")
    elif not vers:
        _linea("  (ninguna verificacion registrada)")
    else:
        for ts, accion, veredicto, conf in vers:
            c = "SIN DATOS" if conf is None else f"{conf:.2f}"
            _linea(f"  {_ts_local_madrid(ts)}  {accion:<22} {veredicto:<9} confianza={c}")
    _linea()
    _linea("== COSTE DEL DIA ==")
    cd = coste_del_dia(conn)
    if cd is None:
        _linea("SIN DATOS")
    else:
        gastado, limite = cd
        _linea(f"  gastado hoy: {gastado:.2f} EUR de {limite:.2f} EUR de limite")
    _linea()
    _linea("== RANKING P8 (top 5, n >= minimo muestral) ==")
    rk = ranking_p8_top(conn)
    if rk is None:
        _linea("SIN DATOS")
    elif not rk:
        _linea("  (sin pares argumento-segmento con muestra suficiente)")
    else:
        for f in rk:
            _linea(f"  {f['ranking']}. {f['argumento_id']} [{f['segmento']}] "
                   f"n={f['n']} tasa_avance={f['tasa_avance']:.2f}")


# -- salida HTML estatica (Bloque 5) ------------------------------------------
def _esc(t) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(conn: sqlite3.Connection, ruta: Path | None = None) -> Path:
    """Genera panel/director.html entero en cada ejecucion. Sin JS, sin CDN.
    Colores fijados: fondo #F5F1E8, tinta #1A1A1A, acento #C09244."""
    destino = Path(ruta) if ruta is not None else RUTA_HTML
    pipe = datos_pipeline(conn)
    comps = compromisos_pendientes(conn)
    cd = coste_del_dia(conn)
    rk = ranking_p8_top(conn)
    vers50 = None
    if _hay_tabla(conn, "verificaciones"):
        vers50 = conn.execute(
            "SELECT ts, tipo, cubo, accion, veredicto, confianza FROM verificaciones "
            "ORDER BY id DESC LIMIT 50").fetchall()

    def seccion_pipeline() -> str:
        if pipe is None:
            return "<p class='sindatos'>SIN DATOS</p>"
        filas = "".join(f"<tr><td>{e}</td><td>{pipe.get(e, 0)}</td></tr>" for e in ESTADOS_ORDEN)
        return f"<table><tr><th>Estado</th><th>Leads</th></tr>{filas}</table>"

    def seccion_compromisos() -> str:
        if comps is None:
            return "<p class='sindatos'>SIN DATOS</p>"
        if not comps:
            return "<p>(ninguno pendiente)</p>"
        filas = "".join(
            f"<tr><td>{_esc(f[5][:10])}</td><td>{_esc(f[2] or f[1])}</td>"
            f"<td>{_esc(f[3])}</td><td>{_esc(f[4][:80])}</td></tr>" for f in comps)
        return ("<table><tr><th>Fecha limite</th><th>Lead</th><th>Tipo</th>"
                f"<th>Descripcion</th></tr>{filas}</table>")

    def seccion_coste() -> str:
        if cd is None:
            return "<p class='sindatos'>SIN DATOS</p>"
        return f"<p>Gastado hoy: <b>{cd[0]:.2f} EUR</b> de {cd[1]:.2f} EUR de limite.</p>"

    def seccion_p8() -> str:
        if rk is None:
            return "<p class='sindatos'>SIN DATOS</p>"
        if not rk:
            return "<p>(sin pares argumento-segmento con muestra suficiente)</p>"
        filas = "".join(
            f"<tr><td>{f['ranking']}</td><td>{_esc(f['argumento_id'])}</td>"
            f"<td>{_esc(f['segmento'])}</td><td>{f['n']}</td>"
            f"<td>{f['tasa_avance']:.2f}</td></tr>" for f in rk)
        return ("<table><tr><th>#</th><th>Argumento</th><th>Segmento</th><th>n</th>"
                f"<th>Tasa avance</th></tr>{filas}</table>")

    def seccion_verificaciones() -> str:
        if vers50 is None:
            return "<p class='sindatos'>SIN DATOS</p>"
        if not vers50:
            return "<p>(ninguna verificacion registrada)</p>"
        filas = "".join(
            f"<tr><td>{_esc(_ts_local_madrid(f[0]))}</td><td>{_esc(f[1])}</td>"
            f"<td>{_esc(f[2])}</td><td>{_esc(f[3])}</td><td>{_esc(f[4])}</td>"
            f"<td>{'SIN DATOS' if f[5] is None else f'{f[5]:.2f}'}</td></tr>" for f in vers50)
        return ("<table><tr><th>Cuando (Madrid)</th><th>Tipo</th><th>Cubo</th>"
                f"<th>Accion</th><th>Veredicto</th><th>Confianza</th></tr>{filas}</table>")

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Panel del Director - Kaizen</title>
<style>
body {{ background: #F5F1E8; color: #1A1A1A; font-family: Georgia, serif;
       max-width: 960px; margin: 2rem auto; padding: 0 1rem; }}
h1 {{ border-bottom: 3px solid #C09244; padding-bottom: .3rem; }}
h2 {{ color: #C09244; margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #1A1A1A; padding: .35rem .6rem; text-align: left; }}
th {{ background: #C09244; color: #F5F1E8; }}
.sindatos {{ color: #1A1A1A; font-style: italic; }}
footer {{ margin-top: 2rem; font-size: .85rem; color: #555; }}
</style></head><body>
<h1>Panel del Director - Kaizen</h1>
<p>Generado: {_esc(_ts_local_madrid(ts_iso8601z()))} (Europe/Madrid) - solo lectura</p>
<h2>Pipeline por estado</h2>{seccion_pipeline()}
<h2>Compromisos pendientes</h2>{seccion_compromisos()}
<h2>Coste del dia</h2>{seccion_coste()}
<h2>Ranking P8 (top 5)</h2>{seccion_p8()}
<h2>Ultimas 50 verificaciones</h2>{seccion_verificaciones()}
<footer>Kaizen - panel estatico regenerado entero en cada ejecucion; sin JS, sin CDN,
sin servidor web. Si un dato no existe se muestra SIN DATOS.</footer>
</body></html>
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
