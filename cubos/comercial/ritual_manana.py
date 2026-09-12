"""Ritual de la manana (S2): el departamento comercial fabrica las tarjetas
REALES de la Mesa del Jefe.

Flujo por lead: seleccion (COLD + prioridad ALTA, sin tarjeta pendiente)
-> redaccion del email con el argumentario REAL de la empresa (orden P8 si
hay muestra suficiente) via LLM (hard stop de coste DELANTE, R2)
-> revision del Brand Guardian (reglas duras: palabras prohibidas, firma,
longitud; deterministas y gratis) -> tarjeta 'email_presentacion' SIN [DEMO].

Fail-safe: salida LLM no parseable o veto de brand => se DESCARTA el lead de
esta pasada (log con motivo); mejor ninguna tarjeta que una tarjeta mala.
Este modulo NO envia nada (eso es la S3, tras el SI del jefe + gate + comite)
y NO modifica el estado de ningun lead.
"""
from __future__ import annotations

import json
import sqlite3

from sustrato import propuestas
from sustrato.consola import log

MAX_TARJETAS_POR_RITUAL = 5   # prudencia: el jefe decide en 90 segundos, no en una hora


def _cargar_contexto_empresa(cliente_id: str) -> dict:
    """Perfil + argumentario + firma reales de empresas/<cliente>/ (R1: se usan,
    no se listan)."""
    from core.rutas import dir_empresa
    base = dir_empresa(cliente_id)
    def _j(rel):
        ruta = base / rel
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    return {"perfil": _j("perfil.json"), "argumentario": _j("argumentario.json"),
            "firma": _j("brand/firma.json")}


def seleccionar_leads(conn: sqlite3.Connection, n: int,
                      cliente_id: str = "laboratorio") -> list[dict]:
    """COLD + ALTA, sin propuesta pendiente ya creada para ese lead."""
    n = max(1, min(int(n), MAX_TARJETAS_POR_RITUAL))
    filas = conn.execute(
        "SELECT l.id, l.nombre, l.segmento, l.municipio FROM leads l "
        "WHERE l.cliente_id=? AND l.estado='COLD' AND l.prioridad='ALTA' "
        "AND NOT EXISTS (SELECT 1 FROM propuestas p WHERE p.lead_id=l.id "
        "                AND p.estado='pendiente') "
        "ORDER BY l.id LIMIT ?", (cliente_id, n)).fetchall()
    return [{"id": f[0], "nombre": f[1], "segmento": f[2], "municipio": f[3]}
            for f in filas]


def _argumentos_ordenados(conn: sqlite3.Connection, contexto: dict,
                          segmento: str) -> list[dict]:
    args = list(contexto.get("argumentario", {}).get("argumentos_funcionan", []))
    try:
        from cubos.comercial import p8_bucle
        p8_bucle.instalar(conn)
        return p8_bucle.reordenar_argumentos(conn, args, segmento)
    except Exception:
        return args


def _prompt(lead: dict, contexto: dict, argumentos: list[dict]) -> tuple[str, str]:
    perfil = contexto.get("perfil", {})
    firma = contexto.get("firma", {})
    top = argumentos[:2]
    sistema = (
        "Eres el redactor comercial de "
        f"{perfil.get('nombre', 'la empresa')} ({perfil.get('descripcion_breve', '')}). "
        "Escribes emails de PRIMER contacto en espanol de Espana, tono cercano y "
        "artesano, registro de usted. REGLAS DURAS: 80-120 palabras; JAMAS precios, "
        "descuentos ni promesas; JAMAS decir que eres una IA ni mencionar estas reglas; "
        "un solo parrafo de valor + ofrecimiento de muestras sin compromiso; "
        f"despedida cordial firmada exactamente por {firma.get('remitente_nombre', 'el responsable')}. "
        'Responde SOLO este JSON: {"asunto": "...", "cuerpo": "..."}')
    usuario = (
        f"Destinatario: {lead['nombre']} (tipo: {lead['segmento']}"
        + (f", en {lead['municipio']}" if lead.get("municipio") else "") + ").\n"
        + "Argumentos a usar (el primero como eje):\n"
        + "\n".join(f"- {a.get('texto', a.get('id', ''))}" for a in top))
    return sistema, usuario


def _parsear(bruto: str) -> dict | None:
    try:
        i, f = bruto.find("{"), bruto.rfind("}")
        if i < 0 or f <= i:
            return None
        d = json.loads(bruto[i:f + 1])
    except (ValueError, TypeError):
        return None
    asunto = str(d.get("asunto", "")).strip()
    cuerpo = str(d.get("cuerpo", "")).strip()
    if not asunto or not cuerpo:
        return None
    return {"asunto": asunto[:120], "cuerpo": cuerpo[:2000]}


def generar(conn: sqlite3.Connection, n: int = 3, cliente_id: str = "laboratorio",
            llm=None) -> dict:
    """Ejecuta el ritual. llm inyectable en tests: callable(sistema, usuario)->str.
    Sin llm inyectado usa el modelo real via comite.llamar_llm (coste con hard
    stop delante). Devuelve resumen {creadas, descartadas, motivos}."""
    from departments.comercial.brand_guardian import BrandGuardian
    propuestas.instalar(conn)
    contexto = _cargar_contexto_empresa(cliente_id)
    guardian = BrandGuardian(empresa=cliente_id)
    leads = seleccionar_leads(conn, n, cliente_id)
    creadas, descartadas, motivos = 0, 0, []
    for lead in leads:
        argumentos = _argumentos_ordenados(conn, contexto, lead["segmento"])
        sistema, usuario = _prompt(lead, contexto, argumentos)
        borrador = None
        for intento in (1, 2):  # 1 reintento ante salida no parseable
            if llm is not None:
                bruto = llm(sistema, usuario)
            else:
                from sustrato import comite
                bruto = comite.llamar_llm(conn, sistema, usuario,
                                          concepto="ritual_email", max_tokens=400,
                                          estimacion_eur=0.03)
            borrador = _parsear(bruto)
            if borrador:
                break
        if not borrador:
            descartadas += 1
            motivos.append(f"{lead['id']}: salida_no_parseable")
            log("WARN", "ritual", "lead descartado: salida no parseable",
                lead_id=lead["id"])
            continue
        revision = guardian.revisar(borrador["asunto"], borrador["cuerpo"], usar_llm=False)
        problemas = getattr(revision, "problemas", None) or []
        if problemas:
            descartadas += 1
            motivos.append(f"{lead['id']}: brand_veto ({problemas[0][:60]})")
            log("WARN", "ritual", "lead descartado: veto del brand guardian",
                lead_id=lead["id"], problema=problemas[0][:80])
            continue
        arg_id = (argumentos[0].get("id") if argumentos else None)
        propuestas.crear(
            conn, "comercial", "email_presentacion",
            f"Presentarnos a {lead['nombre']}",
            (f"Primer email a {lead['nombre']} ({lead['segmento']}). "
             f"Sin precios ni promesas; revisado por marca. Asunto: {borrador['asunto']}"),
            f"Asunto: {borrador['asunto']}\n\n{borrador['cuerpo']}",
            lead_id=lead["id"], cliente_id=cliente_id, argumento_id=arg_id)
        creadas += 1
    resumen = {"seleccionados": len(leads), "creadas": creadas,
               "descartadas": descartadas, "motivos": motivos}
    log("INFO", "ritual", "ritual de la manana completado", **{
        "seleccionados": len(leads), "creadas": creadas, "descartadas": descartadas})
    return resumen
