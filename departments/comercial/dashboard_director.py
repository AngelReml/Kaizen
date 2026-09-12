"""Dashboard del Director Comercial (Módulo 7 del sistema nervioso).

Vista panel determinista del estado del departamento. NO muta nada. NO usa LLM.
Ver `docs/DASHBOARD_DIRECTOR.md`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from core.lead_schema import LeadDoc
from core.briefing import _ciudad_desde_direccion, _parsear_ts


TZ_ES = ZoneInfo("Europe/Madrid")


# Orden visual del pipeline (mismo orden que la matriz M2)
ORDEN_ESTADOS = [
    "cold", "queued", "contacting", "no_answer", "contacted", "engaged",
    "sample_requested", "sample_sent", "trial", "customer", "lost", "do_not_call",
]


def _fmt_madrid(dt_utc: datetime) -> str:
    return dt_utc.astimezone(TZ_ES).strftime("%Y-%m-%d %H:%M Madrid")


def _ciudad(lead: LeadDoc) -> str:
    return _ciudad_desde_direccion(
        lead.ubicacion.direccion if lead.ubicacion else "")


class DashboardDirector:
    """Vista panel. Loader inyectable; clock inyectable para tests."""

    def __init__(self, knowledge_loader: Callable[[], list[LeadDoc]],
                 empresa: str = "laboratorio",
                 clock: Optional[Callable[[], datetime]] = None) -> None:
        self.knowledge_loader = knowledge_loader
        self.empresa = empresa
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- núcleo: datos estructurados --------------------------------------

    def datos_para_dashboard(self) -> dict:
        leads = self.knowledge_loader() or []
        ahora = self.clock()
        ahora_mas_24h = ahora + timedelta(hours=24)
        ahora_mas_7d = ahora + timedelta(days=7)
        ahora_menos_7d = ahora - timedelta(days=7)

        # 1. Buckets de estado (12 siempre presentes, aunque a 0)
        buckets = {e: 0 for e in ORDEN_ESTADOS}
        for ld in leads:
            estado = (ld.estado_pipeline or "cold").lower()
            if estado in buckets:
                buckets[estado] += 1

        # 2. Próximas acciones (24h)
        proximas = []
        for ld in leads:
            if not ld.reintentos or not ld.reintentos.proxima_accion_ts:
                continue
            ts = _parsear_ts(ld.reintentos.proxima_accion_ts)
            if not ts:
                continue
            if ahora <= ts <= ahora_mas_24h:
                proximas.append({
                    "lead_id": ld.id,
                    "nombre": ld.nombre or "",
                    "ciudad": _ciudad(ld),
                    "ts_madrid": _fmt_madrid(ts),
                    "ts_utc_iso": ts.isoformat(),
                    "tipo": ld.reintentos.proxima_accion_tipo or "",
                })
        proximas.sort(key=lambda x: x["ts_utc_iso"])

        # 3 + 6. Compromisos próximos (7 días) y vencidos
        proximos_comp = []
        vencidos = []
        for ld in leads:
            for c in ld.compromisos or []:
                if c.cumplido:
                    continue
                ts = _parsear_ts(c.fecha_objetivo)
                if not ts:
                    continue
                item = {
                    "lead_id": ld.id,
                    "nombre": ld.nombre or "",
                    "tipo": c.tipo,
                    "ts_madrid": _fmt_madrid(ts),
                    "ts_utc_iso": ts.isoformat(),
                    "tolerancia_min": c.tolerancia_min,
                    "contexto": c.contexto or "",
                }
                if ts < ahora:
                    vencidos.append(item)
                elif ts <= ahora_mas_7d:
                    proximos_comp.append(item)
        proximos_comp.sort(key=lambda x: x["ts_utc_iso"])
        vencidos.sort(key=lambda x: x["ts_utc_iso"])

        # 5. Histórico reciente (últimos 7 días)
        interacciones_recientes = []
        for ld in leads:
            for inter in ld.interacciones or []:
                ts = _parsear_ts(inter.ts)
                if not ts:
                    continue
                if ahora_menos_7d <= ts <= ahora:
                    interacciones_recientes.append({
                        "lead_id": ld.id,
                        "nombre": ld.nombre or "",
                        "ts_madrid": _fmt_madrid(ts),
                        "ts_utc_iso": ts.isoformat(),
                        "resultado": inter.resultado or "",
                        "duracion_s": inter.duracion_s or 0,
                    })
        interacciones_recientes.sort(key=lambda x: x["ts_utc_iso"], reverse=True)

        # 7. Embudo de conversión
        avanzados = {"contacted", "engaged", "sample_requested", "sample_sent",
                     "trial", "customer"}
        engaged_o_mas_set = {"engaged", "sample_requested", "sample_sent",
                              "trial", "customer"}
        cold = sum(buckets[e] for e in ("cold", "queued", "contacting",
                                         "no_answer"))
        contacted_o_mas = sum(buckets[e] for e in avanzados)
        engaged_o_mas = sum(buckets[e] for e in engaged_o_mas_set)
        customer = buckets["customer"]

        def _ratio(num, den):
            return round(num / den, 3) if den > 0 else 0.0

        return {
            "empresa": self.empresa,
            "timestamp_madrid": _fmt_madrid(ahora),
            "total_leads": len(leads),
            "estado_pipeline": buckets,
            "proximas_acciones_24h": proximas,
            "compromisos_proximos": proximos_comp,
            "compromisos_vencidos": vencidos,
            "interacciones_recientes": interacciones_recientes,
            "embudo": {
                "cold": cold,
                "contacted_o_mas": contacted_o_mas,
                "engaged_o_mas": engaged_o_mas,
                "customer": customer,
                "tasa_contact": _ratio(contacted_o_mas, cold or contacted_o_mas),
                "tasa_engaged": _ratio(engaged_o_mas, contacted_o_mas),
                "tasa_customer": _ratio(customer, engaged_o_mas),
            },
        }

    # --- renderizado markdown ---------------------------------------------

    def renderizar(self) -> str:
        d = self.datos_para_dashboard()
        L: list[str] = []
        L.append(f"# KAIZEN · Director Comercial · {d['empresa']}")
        L.append(f"_{d['timestamp_madrid']}_  ·  total leads: **{d['total_leads']}**")
        L.append("")

        # Estado del pipeline
        L.append("## Estado del pipeline")
        max_n = max(d["estado_pipeline"].values()) or 1
        for estado in ORDEN_ESTADOS:
            n = d["estado_pipeline"][estado]
            barra_n = int((n / max_n) * 24) if max_n > 0 else 0
            barra = "█" * barra_n
            L.append(f"- `{estado:<17s}` {n:>4d}  {barra}")

        # Próximas acciones
        L.append("")
        L.append("## Próximas acciones (24h)")
        if not d["proximas_acciones_24h"]:
            L.append("_ninguna_")
        else:
            for p in d["proximas_acciones_24h"]:
                L.append(f"- **{p['ts_madrid']}** — {p['tipo']} · "
                         f"{p['nombre']} ({p['ciudad']})")

        # Compromisos próximos
        L.append("")
        L.append("## Compromisos pendientes (próximos 7 días)")
        if not d["compromisos_proximos"]:
            L.append("_ninguno_")
        else:
            for c in d["compromisos_proximos"]:
                tol = f" ±{c['tolerancia_min']}m" if c["tolerancia_min"] else ""
                L.append(f"- **{c['ts_madrid']}**{tol} — {c['tipo']} · {c['nombre']}")
                if c["contexto"]:
                    L.append(f"  _{c['contexto']}_")

        # Compromisos vencidos
        L.append("")
        L.append("## ⚠ Compromisos vencidos sin cumplir")
        if not d["compromisos_vencidos"]:
            L.append("_ninguno_")
        else:
            for c in d["compromisos_vencidos"]:
                L.append(f"- **{c['ts_madrid']}** — {c['tipo']} · {c['nombre']}")

        # Histórico reciente
        L.append("")
        L.append("## Histórico reciente (últimos 7 días)")
        if not d["interacciones_recientes"]:
            L.append("_ninguno_")
        else:
            for i in d["interacciones_recientes"][:15]:
                dur = f" · {i['duracion_s']}s" if i["duracion_s"] else ""
                L.append(f"- {i['ts_madrid']} · {i['nombre']} · "
                         f"**{i['resultado']}**{dur}")

        # Embudo
        L.append("")
        L.append("## Embudo de conversión")
        e = d["embudo"]
        L.append(f"- cold/queued/contacting/no_answer : **{e['cold']}**")
        L.append(f"- contacted o más                  : **{e['contacted_o_mas']}** "
                 f"(tasa contact: {e['tasa_contact']*100:.1f}%)")
        L.append(f"- engaged o más                    : **{e['engaged_o_mas']}** "
                 f"(tasa engagement: {e['tasa_engaged']*100:.1f}%)")
        L.append(f"- customer                         : **{e['customer']}** "
                 f"(tasa cierre: {e['tasa_customer']*100:.1f}%)")

        return "\n".join(L)

    # --- impresión consola (rich) -----------------------------------------

    def imprimir(self, console=None) -> None:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        c = console or Console()
        d = self.datos_para_dashboard()

        c.print(Panel.fit(
            f"[bold cyan]KAIZEN · Director Comercial[/]  ·  "
            f"[white]{d['empresa']}[/]\n"
            f"[dim]{d['timestamp_madrid']}  ·  total leads: "
            f"[bold]{d['total_leads']}[/][/]",
            border_style="cyan"))

        # Estado del pipeline
        t = Table(title="Estado del pipeline", show_header=True, header_style="bold")
        t.add_column("Estado", no_wrap=True)
        t.add_column("N", justify="right")
        t.add_column("")
        max_n = max(d["estado_pipeline"].values()) or 1
        for estado in ORDEN_ESTADOS:
            n = d["estado_pipeline"][estado]
            barra_n = int((n / max_n) * 24) if max_n > 0 else 0
            t.add_row(estado, str(n), "█" * barra_n)
        c.print(t)

        # Próximas acciones
        t = Table(title="Próximas acciones (24h)", show_header=True,
                  header_style="bold yellow")
        t.add_column("Cuándo")
        t.add_column("Tipo")
        t.add_column("Lead")
        if not d["proximas_acciones_24h"]:
            t.add_row("[dim]ninguna[/]", "", "")
        else:
            for p in d["proximas_acciones_24h"]:
                t.add_row(p["ts_madrid"], p["tipo"],
                          f"{p['nombre']} ({p['ciudad']})")
        c.print(t)

        # Compromisos próximos
        t = Table(title="Compromisos pendientes (próximos 7 días)",
                  show_header=True, header_style="bold magenta")
        t.add_column("Cuándo")
        t.add_column("Tipo")
        t.add_column("Lead")
        t.add_column("Contexto")
        if not d["compromisos_proximos"]:
            t.add_row("[dim]ninguno[/]", "", "", "")
        else:
            for ce in d["compromisos_proximos"]:
                t.add_row(ce["ts_madrid"], ce["tipo"], ce["nombre"],
                          ce["contexto"][:60])
        c.print(t)

        # Vencidos
        if d["compromisos_vencidos"]:
            t = Table(title="⚠ Compromisos vencidos sin cumplir",
                      show_header=True, header_style="bold red")
            t.add_column("Cuándo"); t.add_column("Tipo"); t.add_column("Lead")
            for ce in d["compromisos_vencidos"]:
                t.add_row(ce["ts_madrid"], ce["tipo"], ce["nombre"])
            c.print(t)

        # Histórico reciente
        if d["interacciones_recientes"]:
            t = Table(title="Histórico reciente (últimos 7 días)",
                      show_header=True, header_style="bold green")
            t.add_column("Cuándo"); t.add_column("Lead")
            t.add_column("Resultado"); t.add_column("Duración")
            for i in d["interacciones_recientes"][:15]:
                dur = f"{i['duracion_s']}s" if i["duracion_s"] else "—"
                t.add_row(i["ts_madrid"], i["nombre"], i["resultado"], dur)
            c.print(t)

        # Embudo
        e = d["embudo"]
        c.print(Panel.fit(
            f"[bold]Embudo[/]\n"
            f"cold/queued/contacting/no_answer : [bold]{e['cold']}[/]\n"
            f"contacted o más                  : [bold]{e['contacted_o_mas']}[/]  "
            f"[dim](contact rate {e['tasa_contact']*100:.1f}%)[/]\n"
            f"engaged o más                    : [bold]{e['engaged_o_mas']}[/]  "
            f"[dim](engagement rate {e['tasa_engaged']*100:.1f}%)[/]\n"
            f"customer                         : [bold]{e['customer']}[/]  "
            f"[dim](close rate {e['tasa_customer']*100:.1f}%)[/]",
            border_style="green", title="Conversión"))
