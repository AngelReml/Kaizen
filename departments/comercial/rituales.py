"""Rituales del Departamento Comercial (v0.2 §7.2).

Reportes determinados sobre el estado actual del pipeline. Pensados para ejecutarse:
  - Daily stand-up (cada mañana): `daily_report()` resume el día anterior + atascos.
  - Viernes ejecutivo: `weekly_report()` con las 5 secciones del §7.4 + métricas + cola.

La ejecución programada (cron / Task Scheduler) la conecta el operador en su SO; este
módulo solo expone las funciones que generan los reportes deterministas.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from departments.comercial.cola_aprobacion import ColaAprobacion
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.metricas import calcular


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def daily_report(*, lead_store: LeadStore, cola: ColaAprobacion,
                 salida: Path | None = None) -> Path:
    """Resumen diario corto. Foco: ¿qué pasó ayer, dónde estamos atascados, qué hay en cola?"""
    ahora = _ts()
    ayer_iso = (ahora - timedelta(days=1)).isoformat()
    cuentas = lead_store.contar_por_estado()
    leads = lead_store.listar()

    nuevos_24h = sum(1 for l in leads if l.get("creado_en", "") >= ayer_iso)
    transiciones_24h = sum(
        sum(1 for t in (l.get("historial") or []) if t.get("ts", "") >= ayer_iso)
        for l in leads
    )
    atascados = {
        EstadoLead.CUALIFICADO.value: [l for l in leads
                                       if l.get("estado") == EstadoLead.CUALIFICADO.value
                                       and l.get("actualizado_en", "") < ayer_iso],
        EstadoLead.EN_CONTACTO.value: [l for l in leads
                                       if l.get("estado") == EstadoLead.EN_CONTACTO.value
                                       and l.get("actualizado_en", "") < (ahora - timedelta(days=10)).isoformat()],
    }
    pendientes = cola.listar(estado="pendiente")
    aprobados = cola.listar(estado="aprobado")
    enviados = cola.listar(estado="enviado")

    md = [
        f"# Daily stand-up — {ahora.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Últimas 24h",
        f"- Leads nuevos identificados: {nuevos_24h}",
        f"- Transiciones de estado: {transiciones_24h}",
        f"- Pendientes en cola de aprobación: {len(pendientes)}",
        f"- Aprobados a la espera de enviar: {len(aprobados)}",
        f"- Enviados en cola: {len(enviados)}",
        "",
        "## Estado del pipeline",
        "| Estado | Leads |",
        "|---|---:|",
    ]
    for estado in EstadoLead:
        md.append(f"| {estado.value} | {cuentas.get(estado.value, 0)} |")
    md += [
        "",
        "## Atascos",
        f"- {len(atascados[EstadoLead.CUALIFICADO.value])} leads CUALIFICADOS sin pasar enrichment >24h.",
        f"- {len(atascados[EstadoLead.EN_CONTACTO.value])} leads EN_CONTACTO sin respuesta >10 días.",
        "",
    ]
    if salida is None:
        raiz = Path(__file__).resolve().parent.parent.parent / "docs"
        raiz.mkdir(parents=True, exist_ok=True)
        salida = raiz / f"DAILY_COMERCIAL_{ahora.strftime('%Y%m%d')}.md"
    salida.write_text("\n".join(md), encoding="utf-8")
    return salida


def weekly_report(*, lead_store: LeadStore, cola: ColaAprobacion,
                  salida: Path | None = None) -> Path:
    """Reporte ejecutivo del viernes con las 5 secciones del v0.2 §7.4 + cola actual."""
    ahora = _ts()
    cuentas = lead_store.contar_por_estado()
    cuadro = calcular(lead_store)

    semana = (ahora - timedelta(days=7)).isoformat()
    leads = lead_store.listar()
    transiciones_semana = []
    for l in leads:
        for t in (l.get("historial") or []):
            if t.get("ts", "") >= semana:
                transiciones_semana.append((l["id"], t))

    en_compromiso = cuentas.get(EstadoLead.COMPROMISO_RECIPROCO.value, 0)
    muestras_enviadas = cuentas.get(EstadoLead.MUESTRA_ENVIADA.value, 0)
    clientes_activos = cuentas.get(EstadoLead.CLIENTE_ACTIVO.value, 0)
    aprobados = cola.listar(estado="aprobado")
    enviados = cola.listar(estado="enviado")
    pendientes = cola.listar(estado="pendiente")

    md = [
        f"# Reporte ejecutivo del viernes — Departamento Comercial",
        f"*Generado {ahora.strftime('%Y-%m-%d %H:%M')}. Estructura: v0.2 §7.4.*",
        "",
        "## 1. Resultados de la semana",
        f"- Transiciones de estado: {len(transiciones_semana)}",
        f"- Emails enviados esta semana: "
        f"{sum(1 for e in enviados if e.get('enviado_en', '') >= semana)}",
        f"- Leads en Compromiso Recíproco: {en_compromiso}",
        f"- Muestras enviadas (acumulado): {muestras_enviadas}",
        f"- Clientes activos (acumulado): {clientes_activos}",
        "",
        "## 2. Embudo",
        "| Estado | Leads |",
        "|---|---:|",
    ]
    for e in EstadoLead:
        md.append(f"| {e.value} | {cuentas.get(e.value, 0)} |")
    md += [
        "",
        "## 3. Desviaciones",
        f"- Gate semanal Fase 1 (v0.2 §2.1): 5 leads en Compromiso Recíproco la "
        f"primera semana → actual: **{en_compromiso}**.",
    ]
    if en_compromiso >= 5:
        md.append("- ✅ Gate cumplido.")
    elif en_compromiso > 0:
        md.append(f"- ⚠ Por debajo del gate; faltan {5 - en_compromiso} compromisos.")
    else:
        md.append("- ❌ Ningún compromiso recíproco aún esta semana.")
    md += [
        "",
        "## 4. Riesgos",
        f"- Pendientes en cola de aprobación: {len(pendientes)} (revisión humana requerida).",
        f"- Aprobados sin enviar (¿flag KAIZEN_ENVIO_HABILITADO?): {len(aprobados)}.",
    ]
    for m in cuadro.metricas:
        if m.banda == "ROJO":
            md.append(f"- 🔴 {m.nombre} ({m.rol}): {m.valor}{m.unidad} — {m.detalle}")
        elif m.banda == "AMBAR":
            md.append(f"- 🟡 {m.nombre} ({m.rol}): {m.valor}{m.unidad} — {m.detalle}")
    md += [
        "",
        "## 5. Próxima semana",
    ]
    if en_compromiso == 0:
        md += [
            "- Aprobar y enviar más mensajes pendientes (subir cadencia).",
            "- Recuperar leads EN_CONTACTO sin respuesta >10 días (nurturing o descarte).",
        ]
    else:
        md += [
            "- Account Executive: cerrar las operaciones de muestra de los compromisos.",
            "- Subir cuota de cola: aspirar a 30+ mensajes por revisar la próxima semana.",
        ]

    # ── Sección 6: Calidad de llamadas (Fase 1 voz · R4 del operador) ──────
    md += ["", "## 6. Calidad de llamadas (esta semana)"]
    md.extend(_seccion_calidad_llamadas(lead_store.k, lead_store.company, semana))

    if salida is None:
        raiz = Path(__file__).resolve().parent.parent.parent / "docs"
        raiz.mkdir(parents=True, exist_ok=True)
        salida = raiz / f"WEEKLY_COMERCIAL_{ahora.strftime('%Y%m%d')}.md"
    salida.write_text("\n".join(md), encoding="utf-8")
    return salida


def _seccion_calidad_llamadas(knowledge, company: str, desde_iso: str) -> list[str]:
    """Agrega los `analisis_llamada` desde la fecha indicada. Devuelve líneas Markdown."""
    llamadas = list(knowledge.all(company, "llamada").values())
    semana_l = [l for l in llamadas if l.get("inicio_ts", "") >= desde_iso]
    if not semana_l:
        return ["- *Sin llamadas registradas esta semana.*"]

    analisis_todos = knowledge.all(company, "analisis_llamada")
    analisis_por_call = {a["call_sid"]: a for a in analisis_todos.values()}

    contestadas = [l for l in semana_l if (l.get("transcript") or [])]
    no_conformes = [l for l in semana_l if l.get("estado") == "no_conforme"]
    duracion_total = sum(float(l.get("duracion_s", 0) or 0) for l in semana_l)
    dur_media = duracion_total / max(len(contestadas), 1)

    dictamenes = [analisis_por_call[l["id"]] for l in contestadas
                  if l["id"] in analisis_por_call]
    n_compromiso = sum(1 for d in dictamenes
                       if (d.get("compromiso") or {}).get("es_compromiso"))
    n_tono_ok = sum(1 for d in dictamenes if (d.get("tono") or {}).get("ok"))
    pts = [d.get("puntuacion_global", 0) for d in dictamenes]
    pts_media = sum(pts) / max(len(pts), 1)

    # Top objeciones y mejoras (clustering trivial por substring; mejorar con embeddings en V4+)
    objeciones_flat: list[str] = []
    mejoras_flat: list[str] = []
    for d in dictamenes:
        for o in d.get("objeciones") or []:
            if not o.get("abordada"):
                objeciones_flat.append((o.get("frase_cliente") or "")[:80])
        mejoras_flat.extend((d.get("mejoras") or [])[:3])

    bajo_5 = [d for d in dictamenes if d.get("puntuacion_global", 0) < 5]

    lineas = [
        f"- Llamadas totales: {len(semana_l)}",
        f"- Contestadas (con transcript): {len(contestadas)}",
        f"- No conformes (recording/transcript/aviso legal faltó): {len(no_conformes)}",
        f"- Duración media (contestadas): {dur_media:.0f}s",
        f"- Compromisos Recíprocos detectados: {n_compromiso}/{len(dictamenes)}",
        f"- Tono de marca OK: {n_tono_ok}/{len(dictamenes)}",
        f"- Puntuación media (0-10): {pts_media:.1f}",
        "",
        "### Objeciones no abordadas más frecuentes",
    ]
    if objeciones_flat:
        # Sin clustering avanzado: solo listamos las top 5 únicas
        unicas = []
        for o in objeciones_flat:
            if o not in unicas:
                unicas.append(o)
            if len(unicas) >= 5: break
        lineas.extend(f"- \"{o}\"" for o in unicas)
    else:
        lineas.append("- *Sin objeciones registradas no abordadas.*")

    lineas.extend(["", "### Sugerencias de mejora más repetidas"])
    if mejoras_flat:
        unicas = []
        for m in mejoras_flat:
            if m not in unicas:
                unicas.append(m)
            if len(unicas) >= 5: break
        lineas.extend(f"- {m}" for m in unicas)
    else:
        lineas.append("- *Sin sugerencias registradas.*")

    if bajo_5:
        lineas.extend(["", "### Llamadas con puntuación <5 (revisión humana)"])
        for d in bajo_5[:10]:
            lineas.append(f"- {d['call_sid']} · puntuación {d.get('puntuacion_global')} "
                          f"· lead {d.get('lead_id','?')}")
    return lineas
