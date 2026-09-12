"""Generador de briefing pre-call (Módulo 5 del sistema nervioso).

Proyecta un `LeadDoc` a contexto consumible:
- markdown legible para Iván
- `dynamic_variables` (dict[str, str]) para ElevenLabs CAI

Determinista, sin LLM. Trabaja sobre un lead ya cargado en memoria.
Ver `docs/BRIEFING.md`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from core.lead_schema import LeadDoc, Compromiso, Interaccion


TZ_ES = ZoneInfo("Europe/Madrid")


def _parsear_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ciudad_desde_direccion(direccion: str) -> str:
    """Heurística simple: último fragmento separado por coma sin números."""
    if not direccion:
        return ""
    partes = [p.strip() for p in direccion.split(",") if p.strip()]
    if not partes:
        return ""
    # Buscamos el último fragmento que sea principalmente letras (no código postal)
    for p in reversed(partes):
        sin_digitos = "".join(c for c in p if not c.isdigit()).strip()
        if len(sin_digitos) >= 3:
            return sin_digitos
    return partes[-1]


def _razon_llamada(lead: LeadDoc) -> str:
    """Deriva por qué se está llamando AHORA a este lead."""
    estado = (lead.estado_pipeline or "").lower()
    intentos = lead.reintentos.intentos_realizados if lead.reintentos else 0

    # Si tiene compromiso pendiente, esa es la razón
    pendientes = [c for c in (lead.compromisos or []) if not c.cumplido]
    if pendientes:
        callback = next((c for c in pendientes if c.tipo == "callback"), None)
        if callback:
            return "callback_pactado"
        muestra = next((c for c in pendientes if c.tipo == "muestra"), None)
        if muestra:
            return "seguimiento_muestra"

    if estado in ("cold", ""):
        return "primer_contacto"
    if estado == "queued":
        if intentos == 0:
            return "primer_contacto"
        return "reintento_no_answer" if intentos >= 1 else "reintento"
    if estado == "no_answer":
        return "reintento_no_answer"
    if estado == "contacted":
        return "seguimiento_decisor"
    if estado == "engaged":
        return "cierre_muestra"
    if estado == "sample_sent":
        return "seguimiento_post_muestra"
    if estado == "trial":
        return "cierre_cliente"
    if estado == "customer":
        return "fidelizacion"
    return "reintento"


def _resumen_compromisos(pendientes: list[Compromiso]) -> str:
    if not pendientes:
        return ""
    bits = []
    for c in sorted(pendientes, key=lambda x: x.fecha_objetivo or ""):
        when = c.fecha_objetivo or "sin fecha"
        if when != "sin fecha":
            d = _parsear_ts(when)
            if d:
                d_es = d.astimezone(TZ_ES)
                when = d_es.strftime("%Y-%m-%d %H:%M Madrid")
        tol = f" (±{c.tolerancia_min}min)" if c.tolerancia_min else ""
        bits.append(f"{c.tipo} — {when}{tol}")
    return "; ".join(bits)


def _decisor_conocido(lead: LeadDoc) -> str:
    """Busca menciones explícitas en últimos resúmenes."""
    if not lead.interacciones:
        return ""
    for inter in reversed(lead.interacciones):
        resumen = (inter.resumen_llm or "").lower()
        for keyword in ("encargado", "dueño", "duena", "gerente", "responsable",
                        "propietario", "jefe", "director"):
            if keyword in resumen:
                return keyword
    return ""


class GeneradorBriefing:
    """Determinista. `empresa_meta` opcional con perfil de la empresa."""

    def __init__(self, empresa_meta: Optional[dict] = None,
                 clock: Optional[callable] = None) -> None:
        self.empresa = empresa_meta or {}
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def generar_dynamic_variables(self, lead: LeadDoc) -> dict[str, str]:
        """Variables string para inyectar en ElevenLabs CAI dynamic_variables."""
        pendientes = [c for c in (lead.compromisos or []) if not c.cumplido]
        ultima = lead.interacciones[-1] if lead.interacciones else None
        intentos = lead.reintentos.intentos_realizados if lead.reintentos else 0

        dias_atras = ""
        if ultima:
            ts = _parsear_ts(ultima.ts)
            if ts:
                delta = (self.clock() - ts).total_seconds() / 86400
                dias_atras = f"{int(delta)}"

        # Nombre del negocio (el schema actual no tiene campo dedicado para
        # nombre de la persona contacto — ver docs/TODO.md). Como fallback, si
        # el caller guardó algo en metadatos_extra.nombre_contacto, lo usamos.
        extra = getattr(lead, "metadatos_extra", {}) or {}
        nombre_persona = str(extra.get("nombre_contacto", "")).strip()
        negocio = (lead.nombre or "").strip()
        nombre_lead = nombre_persona or negocio

        # Ubicación puede ser None o Ubicacion vacía
        direccion = ""
        if lead.ubicacion is not None:
            direccion = getattr(lead.ubicacion, "direccion", "") or ""

        return {
            "nombre_lead": nombre_lead,
            "nombre_contacto": nombre_persona,
            "negocio": negocio,
            "categoria": (lead.categoria_icp or "").strip(),
            "ciudad": _ciudad_desde_direccion(direccion),
            "intentos_previos": str(intentos),
            "razon_llamada": _razon_llamada(lead),
            "compromisos_pendientes": _resumen_compromisos(pendientes),
            "ultima_interaccion_resumen": (ultima.resumen_llm if ultima else "") or "",
            "ultima_interaccion_dias_atras": dias_atras,
            "decisor_conocido": _decisor_conocido(lead),
            "empresa_nombre": str(self.empresa.get("nombre", "")),
            "empresa_producto_clave": str(self.empresa.get("producto_clave", "")),
        }

    def generar_resumen(self, lead: LeadDoc) -> str:
        """Markdown legible para Iván."""
        v = self.generar_dynamic_variables(lead)
        pendientes = [c for c in (lead.compromisos or []) if not c.cumplido]
        L = []
        titulo = v["negocio"] or v["nombre_lead"] or lead.id
        if v["ciudad"]:
            titulo += f" ({v['ciudad']})"
        L.append(f"# Briefing — {titulo}")
        L.append(f"**Estado**: {lead.estado_pipeline or 'cold'} → "
                 f"{v['razon_llamada']}")
        if v["decisor_conocido"]:
            L.append(f"**Decisor**: {v['decisor_conocido']}")

        if lead.interacciones:
            ultima = lead.interacciones[-1]
            dias = v["ultima_interaccion_dias_atras"]
            cuando = f"hace {dias} día(s)" if dias else "fecha n/d"
            L.append("")
            L.append(f"## Última interacción ({cuando})")
            L.append(ultima.resumen_llm or "_(sin resumen)_")

        if pendientes:
            L.append("")
            L.append("## Compromisos pendientes")
            for c in sorted(pendientes, key=lambda x: x.fecha_objetivo or ""):
                when = c.fecha_objetivo or "sin fecha"
                if when != "sin fecha":
                    d = _parsear_ts(when)
                    if d:
                        when = d.astimezone(TZ_ES).strftime("%Y-%m-%d %H:%M Madrid")
                tol = f" — tolerancia ±{c.tolerancia_min}min" if c.tolerancia_min else ""
                L.append(f"- **{c.tipo}** — {when}{tol}")
                if c.contexto:
                    L.append(f"  _{c.contexto}_")

        if lead.interacciones:
            L.append("")
            L.append("## Histórico de interacciones")
            for i, inter in enumerate(lead.interacciones, 1):
                ts = _parsear_ts(inter.ts)
                cuando = ts.astimezone(TZ_ES).strftime("%Y-%m-%d %H:%MZ") if ts \
                    else inter.ts or "?"
                dur = f" — {inter.duracion_s}s" if inter.duracion_s else ""
                L.append(f"- Intento {i} ({cuando}): {inter.resultado or '?'}{dur}")

        if v["empresa_nombre"]:
            L.append("")
            L.append(f"---")
            L.append(f"_Empresa: {v['empresa_nombre']}_")
        return "\n".join(L)
