"""Verificacion forense diaria (canonico 7.6, fase limitada).

kaizen forense diario comprueba: (a) compromisos vencidos sin cerrar ->
evento kaizen.comercial.compromiso_vencido.v1; (b) integridad de las TRES
cadenas de hash (bus_eventos, verificaciones, decisiones_operador);
(c) coste del dia vs limite; (d) D11 E1.4 — AVISOS de watchdog: flags de
peligro abiertos en el entorno/.env y divergencia knowledge<->registro P9
(la BD vacia del 2026-08-02 y el sandbox abierto un mes se detectan aqui).
Escribe UNA fila tipo='forense' con el resumen.

Retencion: este modulo NO borra transcripts ni grabaciones ni dato alguno
(canonico 10.2): cualquier borrado es del operador.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from sustrato import bus, coste, gates
from sustrato.consola import log, ts_iso8601z

# Flags que, abiertos, significan que el sistema puede tocar el mundo real.
# El forense no los cierra (relajar/endurecer no es suyo): los CANTA cada dia.
FLAGS_PELIGRO = ("KAIZEN_ENVIO_HABILITADO", "SDR_VOICE_ENABLED",
                 "KAIZEN_AUTO_APPROVE", "KAIZEN_ALLOW_NO_TOKEN")

_RAIZ = Path(__file__).resolve().parent.parent
def ruta_knowledge_g1():
    """Lectura de DATOS, no de codigo: vive en la raiz de datos (R-TENANT)."""
    from core.rutas import dir_state
    return dir_state() / "knowledge.json"
_RUTA_ENV = _RAIZ / ".env"


def _valor_flag(nombre: str) -> str:
    """Valor efectivo de un flag: entorno primero; si no esta, el .env del repo.
    Solo LECTURA (el forense observa, jamas muta)."""
    v = os.environ.get(nombre)
    if v is not None:
        return v.strip().lower()
    try:
        for linea in _RUTA_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            if linea.strip().startswith(f"{nombre}="):
                return linea.split("=", 1)[1].strip().lower()
    except OSError:
        pass
    return ""


def avisos_watchdog(conn: sqlite3.Connection,
                    ruta_knowledge: Path | None = None) -> list[str]:
    """D11 E1.4: lista de avisos del dia. No altera el veredicto PASS/FAIL de las
    cadenas (un flag abierto puede ser legitimo en produccion con orden del
    operador) — pero nunca mas sera silencioso."""
    avisos: list[str] = []
    for flag in FLAGS_PELIGRO:
        if _valor_flag(flag) == "true":
            avisos.append(f"FLAG ABIERTO: {flag}=true — el sistema puede tocar el "
                          "mundo real; si no hay orden vigente del operador, cerrar")
    ruta = Path(ruta_knowledge) if ruta_knowledge is not None else ruta_knowledge_g1()
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return avisos                       # sin knowledge legible: nada que comparar
    try:
        filas = dict(conn.execute(
            "SELECT cliente_id, COUNT(*) FROM leads GROUP BY cliente_id").fetchall())
    except sqlite3.Error:
        filas = {}
    for empresa, nodo in datos.items():
        if not isinstance(nodo, dict):
            continue
        en_knowledge = len(nodo.get("lead") or {})
        if not en_knowledge:
            continue
        en_registro = int(filas.get(empresa, 0))
        if en_registro < en_knowledge:
            avisos.append(
                f"DIVERGENCIA: {empresa} tiene {en_knowledge} leads en knowledge y "
                f"{en_registro} en el registro P9 — ejecutar 'kaizen registro sync'")
    return avisos


def diario(conn: sqlite3.Connection,
           ruta_knowledge: Path | None = None) -> dict:
    ahora = ts_iso8601z()
    # (a) compromisos vencidos sin cerrar -> evento (no muta estado: forense observa)
    vencidos = conn.execute(
        "SELECT id, lead_id, tipo, fecha_limite FROM compromisos "
        "WHERE estado='pendiente' AND fecha_limite < ? ORDER BY fecha_limite",
        (ahora,)).fetchall()
    for cid, lead_id, tipo, fecha in vencidos:
        bus.publicar(conn, "kaizen.comercial.compromiso_vencido.v1", "forense",
                     {"compromiso_id": cid, "lead_id": lead_id, "tipo": tipo,
                      "fecha_limite": fecha})
    # (b) integridad de las tres cadenas
    cadenas = {
        "bus_eventos": bus.verificar_cadena(conn),
        "verificaciones": gates.verificar_cadena(conn, "verificaciones"),
        "decisiones_operador": gates.verificar_cadena(conn, "decisiones_operador"),
    }
    # (c) coste del dia vs limite
    gastado = coste.comprobar_limite(conn)
    limite = coste.limite_vigente(conn)
    # (d) watchdog D11 E1.4: flags de peligro + divergencia de almacenes
    avisos = avisos_watchdog(conn, ruta_knowledge)
    resumen = {
        "compromisos_vencidos_notificados": len(vencidos),
        "cadenas": cadenas,
        "coste_dia_eur": round(gastado, 4),
        "limite_dia_eur": round(limite, 2),
        "coste_dentro_de_limite": gastado <= limite,
        "avisos": avisos,
    }
    todo_intacto = all(v.startswith("CADENA INTACTA") for v in cadenas.values())
    veredicto = "PASS" if (todo_intacto and gastado <= limite) else "FAIL"
    gates.registrar_verificacion(conn, "forense", "comercial", "forense_diario",
                                 veredicto, None, resumen)
    log("INFO", "forense", "verificacion forense diaria", veredicto=veredicto,
        vencidos=len(vencidos), coste_eur=f"{gastado:.2f}", avisos=len(avisos))
    return {"veredicto": veredicto, **resumen}
