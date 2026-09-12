"""Reporte ejecutivo del viernes — estructura fija de 5 secciones (§7.4 del v0.2).

Genera Markdown con números reales del estado del `LeadStore` y la última pasada
Researcher/Enrichment. Lo escribe en `docs/REPORTE_FASE0_<fecha>.md` y, opcionalmente,
emite un evento al bus para que el panel lo refleje.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.metricas import CuadroMetricas


def generar_reporte(*, lead_store: LeadStore, cuadro: CuadroMetricas,
                    salida: Path | None = None) -> Path:
    """Genera el reporte y lo devuelve. Si `salida` es None, lo escribe en
    `docs/REPORTE_FASE0_<fecha>.md` del repo."""
    if salida is None:
        salida = (Path(__file__).resolve().parent.parent.parent
                  / "docs" / f"REPORTE_FASE0_{datetime.now():%Y%m%d_%H%M}.md")
    salida.parent.mkdir(parents=True, exist_ok=True)

    cuentas = lead_store.contar_por_estado()
    md = _renderizar_reporte(lead_store.company, cuadro, cuentas)
    salida.write_text(md, encoding="utf-8")
    return salida


def _renderizar_reporte(empresa: str, cuadro: CuadroMetricas, cuentas: dict) -> str:
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    gates = cuadro.gates_fase0
    superados = gates.get("__superados__", False)

    # ── 1. Resultados de la semana ──────────────────────────────────────────
    seccion_resultados = [
        "## 1. Resultados",
        f"- **Empresa:** {empresa}",
        f"- **Cualificados (ICP-pass, en pipeline activo):** {cuadro.cualificados_total}",
        f"- **Enriquecidos (con contacto + actualidad):** {cuadro.enriquecidos_total}",
        f"- **Perdidos / descartados:** {cuentas.get(EstadoLead.PERDIDO.value, 0)}",
        "- **Coste total:** registrado por `cost_tracker` (panel Finanzas).",
        "- **Coste por cliente adquirido:** N/A en Fase 0 (sin envíos ni cierres).",
    ]

    # ── 2. Embudo ──────────────────────────────────────────────────────────
    estados_orden = [
        EstadoLead.IDENTIFICADO, EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO,
        EstadoLead.EN_CONTACTO, EstadoLead.COMPROMISO_RECIPROCO,
        EstadoLead.MUESTRA_ENVIADA, EstadoLead.CLIENTE_ACTIVO,
        EstadoLead.EN_RIESGO, EstadoLead.PERDIDO,
    ]
    seccion_embudo = ["## 2. Embudo",
                      "| Estado | Leads |", "|---|---:|"]
    for e in estados_orden:
        seccion_embudo.append(f"| {e.value} | {cuentas.get(e.value, 0)} |")

    # ── 3. Desviaciones (gates del v0.2) ────────────────────────────────────
    seccion_desv = ["## 3. Desviaciones — Gates de Fase 0 (§2.1)",
                    "| Gate | Real | Umbral | ¿OK? |", "|---|---:|---:|:---:|"]
    seccion_desv.append(
        f"| Leads cualificados | {gates['cualificados_100']['valor']} | "
        f"≥{gates['cualificados_100']['umbral']} | "
        f"{'✅' if gates['cualificados_100']['ok'] else '❌'} |"
    )
    valor_descarte = gates['descarte_icp_menos_40']['valor']
    seccion_desv.append(
        f"| Descarte ICP | {valor_descarte}% | "
        f"<{gates['descarte_icp_menos_40']['umbral']}% | "
        f"{'✅' if gates['descarte_icp_menos_40']['ok'] else '❌'} |"
    )
    valor_verif = gates['contacto_verificado_85']['valor']
    valor_verif_str = f"{valor_verif}%" if valor_verif is not None else "N/A"
    seccion_desv.append(
        f"| Contacto verificado | {valor_verif_str} | "
        f">{gates['contacto_verificado_85']['umbral']}% | "
        f"{'✅' if gates['contacto_verificado_85']['ok'] else '❌'} |"
    )
    seccion_desv.append("")
    seccion_desv.append(
        f"**Veredicto Fase 0:** {'SUPERADA — habilitar Fase 1.' if superados else 'NO superada — no encender Fase 1.'}"
    )

    # ── 4. Riesgos ──────────────────────────────────────────────────────────
    riesgos = []
    en_cualificado_sin_enriquecer = cuentas.get(EstadoLead.CUALIFICADO.value, 0)
    if en_cualificado_sin_enriquecer:
        riesgos.append(
            f"- {en_cualificado_sin_enriquecer} leads atascados en CUALIFICADO sin pasar enrichment."
        )
    for m in cuadro.metricas:
        if m.banda == "ROJO":
            riesgos.append(f"- 🔴 {m.nombre} ({m.rol}): {m.valor}{m.unidad} — {m.detalle}")
        elif m.banda == "AMBAR":
            riesgos.append(f"- 🟡 {m.nombre} ({m.rol}): {m.valor}{m.unidad} — {m.detalle}")
    if not riesgos:
        riesgos = ["- Sin métricas en ámbar o rojo. Pipeline saludable en Fase 0."]
    seccion_riesgos = ["## 4. Riesgos", *riesgos]

    # ── 5. Próxima semana ───────────────────────────────────────────────────
    if superados:
        proxima = [
            "## 5. Próxima semana",
            "- **Encender Fase 1** (§2.1): activar SDR Multicanal + Jefe de Prospección + Brand Guardian básico.",
            "- Definir cuota inicial: contactar 30 leads ENRIQUECIDOS la primera semana.",
            "- Confirmar `IVAN_VOICE_ID` y, si la voz se va a probar, claim de número Twilio.",
            "- Revisar política LSSI/RGPD antes de cualquier llamada de voz a producción.",
        ]
    else:
        proxima = [
            "## 5. Próxima semana",
            "- **NO se enciende Fase 1**: faltan gates por superar.",
            "- Plan: relanzar Researcher con más ciudades o categorías hasta llegar a 100 cualificados.",
            "- Revisar JSON del ICP si el descarte está muy alto (¿falta una categoría legítima?).",
            "- Reforzar enrichment si `pct_contacto_verificado` está bajo (canales adicionales, fuente extra).",
        ]

    metricas_md = ["", "## Anexo — Cuadro de métricas (§7.1)",
                   "| Métrica | Rol | Valor | Banda | Detalle |", "|---|---|---:|:---:|---|"]
    bandas_emoji = {"VERDE": "🟢", "AMBAR": "🟡", "ROJO": "🔴", "NO_APLICA": "⚪"}
    for m in cuadro.metricas:
        v = f"{m.valor}{m.unidad}" if m.valor is not None else "—"
        metricas_md.append(f"| {m.nombre} | {m.rol} | {v} | "
                           f"{bandas_emoji[m.banda]} {m.banda} | {m.detalle} |")

    cabecera = [
        f"# Reporte ejecutivo — Departamento Comercial Sintético ({empresa})",
        f"*Generado {fecha}. Estructura: §7.4 del v0.2.*",
        "",
    ]
    return "\n".join([
        *cabecera, *seccion_resultados, "",
        *seccion_embudo, "",
        *seccion_desv, "",
        *seccion_riesgos, "",
        *proxima, "",
        *metricas_md, "",
    ])
