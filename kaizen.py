#!/usr/bin/env python3
"""Kaizen CLI — Asistente operativo multi-tenant.

R-TENANT: esta CLI no sabe QUÉ tenant opera hasta que se lo dicen. El tenant
llega por `--empresa` o por `KAIZEN_COMPANY`; su nombre comercial y su contexto
salen de `empresas/<tenant>/perfil.json`, jamás de un literal aquí.
"""
import sys
import io
import os

# UTF-8 en Windows Terminal / PowerShell
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import claude_client as ai
import diario_ops as diario
import agentes

# B2 (serie D, D00 §2.2): tenant por defecto SOLO via entorno; patron api/server.py:74
EMPRESA_DEFECTO = os.getenv("KAIZEN_COMPANY", "laboratorio")

console = Console()

def _nombre_tenant(empresa: str = "") -> str:
    """Nombre comercial del tenant, leído de su perfil. Nunca un literal aquí."""
    from core.empresa import cargar_perfil_empresa
    perfil = cargar_perfil_empresa(empresa or EMPRESA_DEFECTO)
    return perfil.get("nombre") or (empresa or EMPRESA_DEFECTO)


def banner(empresa: str = "") -> str:
    return f"[bold cyan]KAIZEN[/] [dim]改善[/]  ·  {_nombre_tenant(empresa)}"


BANNER = "[bold cyan]KAIZEN[/] [dim]改善[/]"


def session_system(empresa: str = "") -> str:
    """System prompt de la sesión, POR TENANT (R-TENANT / R-10)."""
    return f"""Eres el asistente operativo de Kaizen para {_nombre_tenant(empresa)}.
Tienes acceso al Diario del negocio. Responde en español, de forma directa y útil.
Si el usuario quiere prospectar, redactar mensajes o consolidar la sesión, díselo explícitamente
para que use los comandos: kaizen prospectar / kaizen redactar / kaizen consolidar.
No inventes datos del Diario. Si no sabes algo, dilo."""



INTENT_SYSTEM = """Clasifica la intención del usuario en una sola palabra:
- PROSPECTAR: si quiere buscar candidatos, leads, clientes potenciales
- REDACTAR: si quiere escribir mensajes, borradores, emails de contacto
- CONSOLIDAR: si quiere cerrar la sesión, guardar lo hecho, actualizar el diario
- CHAT: cualquier otra consulta, pregunta o conversación

Responde SOLO con una de esas cuatro palabras."""


def _show_status() -> None:
    """Muestra el estado del negocio en 3 líneas."""
    estado = diario.read("ESTADO_ACTUAL")
    if not estado:
        console.print("[yellow]Diario vacío. Ejecuta 'kaizen consolidar' tras la primera sesión.[/]")
        return

    lines = [l.strip() for l in estado.splitlines() if l.strip()]
    estado_linea  = next((l for l in lines if l.startswith("## Estado:")), lines[0] if lines else "Sin datos")
    pendiente     = next((l for l in lines if "Pendiente" in l), "")
    leads         = next((l for l in lines if "Lead" in l or "lead" in l), "")

    console.print(Panel(
        f"[bold]{estado_linea.replace('## ', '')}[/]\n"
        f"[dim]{pendiente.replace('## ', '')}[/]\n"
        f"[dim]{leads.replace('## ', '')}[/]",
        title="Estado del negocio",
        border_style="cyan",
        box=box.ROUNDED,
    ))


def _detect_intent(text: str) -> str:
    resp = ai.chat(
        [{"role": "user", "content": text}],
        system=INTENT_SYSTEM,
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
    ).strip().upper()
    for intent in ("PROSPECTAR", "REDACTAR", "CONSOLIDAR"):
        if intent in resp:
            return intent
    return "CHAT"


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Kaizen — Asistente operativo multi-tenant."""
    if ctx.invoked_subcommand is None:
        _session()


def _session() -> None:
    """Sesión interactiva de Kaizen."""
    console.print(f"\n{banner()}\n")
    _show_status()

    try:
        _, warn = ai.budget_status()
        if warn:
            console.print(f"[yellow]{warn}[/]")
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)
        sys.exit(1)

    console.print("\n[dim]Escribe tu consulta. 'salir' para cerrar. 'consolidar' para guardar la sesión.[/]\n")

    history: list[dict] = []
    session_notes: list[str] = []

    while True:
        try:
            user_input = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            break

        session_notes.append(user_input)

        # Detección rápida de intención
        intent = _detect_intent(user_input)

        if intent == "PROSPECTAR":
            console.print("[dim]Usa:[/] kaizen prospectar \"[perfil de candidato]\"")
            continue

        if intent == "REDACTAR":
            clientes = diario.list_clientes()
            if clientes:
                console.print(f"[dim]Usa:[/] kaizen redactar [nombre_cliente]")
                console.print(f"[dim]Clientes disponibles: {', '.join(clientes)}[/]")
            else:
                console.print("[dim]Aún no hay clientes en el Diario. Prospecta primero.[/]")
            continue

        if intent == "CONSOLIDAR":
            notas = "\n".join(session_notes)
            agentes.consolidar(notas)
            break

        # Chat general con contexto del Diario
        estado   = diario.read("ESTADO_ACTUAL")
        contexto = diario.read("CONTEXTO_NEGOCIO")
        system   = (
            session_system()
            + f"\n\n=== CONTEXTO DEL NEGOCIO ===\n{contexto[:1500]}"
            + f"\n\n=== ESTADO ACTUAL ===\n{estado[:1000]}"
        )

        history.append({"role": "user", "content": user_input})
        if len(history) > 10:
            history = history[-10:]

        try:
            respuesta = ai.chat(history, system=system, model="claude-haiku-4-5-20251001", max_tokens=1024)
            history.append({"role": "assistant", "content": respuesta})
            console.print(f"\n[bold cyan]Kaizen:[/] {respuesta}\n")
        except RuntimeError as e:
            console.print(f"[red]{e}[/]")
            break

    # Resumen de coste al salir
    session_eur = ai.session_cost_eur()
    daily_eur   = ai.daily_cost_eur()
    console.print(f"\n[dim]Sesión: {session_eur:.3f}€  ·  Hoy: {daily_eur:.3f}€[/]")


@cli.command(name="export-context")
def export_context() -> None:
    """Genera el bloque de arranque para pegar en una nueva sesión de Claude."""
    bloque = diario.export_context()
    console.print(Panel(bloque, title="Bloque de arranque — copia y pega al inicio de tu sesión", border_style="green"))


@cli.command()
@click.argument("perfil")
def prospectar(perfil: str) -> None:
    """Busca candidatos B2B para el tenant activo según el PERFIL dado.

    Ejemplo: kaizen prospectar "hoteles boutique Región de Murcia"
    """
    _check_budget()
    try:
        agentes.prospectar(perfil)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)


@cli.command()
@click.argument("cliente")
def redactar(cliente: str) -> None:
    """Genera un borrador de primer contacto para CLIENTE.

    CLIENTE es el nombre del archivo en diario/clientes/ (sin .md).
    Ejemplo: kaizen redactar hotel_la_parra
    """
    _check_budget()
    try:
        agentes.redactar(cliente)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)


@cli.command()
@click.option("--notas", default="", help="Notas opcionales sobre la sesión.")
def consolidar(notas: str) -> None:
    """Actualiza el Diario y hace commit de Git al final de la sesión."""
    _check_budget()
    try:
        agentes.consolidar(notas)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)


@cli.command()
def coste() -> None:
    """Muestra el coste de la sesión actual y el acumulado del día."""
    session_eur = ai.session_cost_eur()
    daily_eur   = ai.daily_cost_eur()
    daily_limit = ai.DAILY_BUDGET_EUR
    pct = daily_eur / daily_limit * 100

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("", style="dim")
    t.add_column("", justify="right")
    t.add_row("Esta sesión", f"[bold]{session_eur:.3f}€[/]")
    t.add_row("Hoy acumulado", f"[bold]{daily_eur:.3f}€[/]")
    t.add_row("Límite diario", f"{daily_limit:.2f}€")
    t.add_row("Uso del límite", f"{'[red]' if pct >= 80 else '[yellow]' if pct >= 50 else '[green]'}{pct:.1f}%[/]")
    console.print(t)


@cli.command()
def clientes() -> None:
    """Lista los clientes y leads en el Diario."""
    lista = diario.list_clientes()
    if not lista:
        console.print("[dim]No hay clientes en el Diario todavía.[/]")
        return
    for c in lista:
        console.print(f"  · {c}")


@cli.command()
@click.argument("nombre")
def ver(nombre: str) -> None:
    """Muestra la ficha de un cliente del Diario.

    Ejemplo: kaizen ver hotel_la_parra
    """
    from rich.markdown import Markdown
    ficha = diario.read_cliente(nombre)
    if not ficha:
        todos = diario.list_clientes()
        coincidencias = [c for c in todos if nombre.lower() in c.lower()]
        if coincidencias:
            console.print(f"[yellow]Clientes similares:[/] {', '.join(coincidencias)}")
        else:
            console.print(f"[red]'{nombre}' no encontrado.[/]")
        return
    console.print(Markdown(ficha))


def _check_budget() -> None:
    try:
        _, warn = ai.budget_status()
        if warn:
            console.print(f"[yellow]{warn}[/]")
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
#  Departamento Comercial — Fase 0+ (ver docs/PLAN_DEPARTAMENTO_COMERCIAL.md)
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def comercial() -> None:
    """Departamento Comercial sintético (cazador + agricultor)."""


@comercial.command(name="fase0")
@click.option("--empresa", default="laboratorio", show_default=True)
@click.option("--max-por-query", default=15, show_default=True, type=int,
              help="Resultados máximos por cada consulta de Places (1-20).")
@click.option("--prioridades", default="ALTA,MEDIA", show_default=True,
              help="Prioridades del ICP a incluir, separadas por coma.")
def comercial_fase0(empresa: str, max_por_query: int, prioridades: str) -> None:
    """Ejecuta una pasada completa de Fase 0 (Researcher + Enrichment + métricas + reporte).

    Hace llamadas reales a Google Places (Text Search New) y Google Routes (computeRoutes).
    Coste estimado: ~1-3€ por pasada. Persiste leads en Knowledge y escribe el reporte
    ejecutivo en docs/REPORTE_FASE0_<fecha>.md.
    """
    _check_budget()
    from dotenv import load_dotenv
    load_dotenv()
    from departments.comercial.director import DirectorComercial
    prios = tuple(p.strip().upper() for p in prioridades.split(",") if p.strip())
    director = DirectorComercial(empresa=empresa)
    resultado = director.ejecutar_fase0(prioridades=prios, max_por_query=max_por_query)
    cuadro = resultado.cuadro
    if resultado.gates_superados:
        console.print(f"\n[bold green]✓ Fase 0 SUPERADA[/] — "
                      f"{cuadro.cualificados_total} cualificados · "
                      f"{cuadro.enriquecidos_total} enriquecidos")
        console.print(f"[dim]Reporte: {resultado.reporte}[/]")
    else:
        console.print("\n[bold yellow]Fase 0 NO superada — revisa los gates:[/]")
        for g, info in cuadro.gates_fase0.items():
            if g == "__superados__": continue
            estado = "[green]✓[/]" if info["ok"] else "[red]✗[/]"
            console.print(f"  {estado} {g}: valor={info['valor']} umbral={info['umbral']}")
        console.print(f"[dim]Reporte: {resultado.reporte}[/]")


# ─────────────────────────────────────────────────────────────────────────────
#  Fase 1 — SDR Multicanal (sandbox obligatorio: NUNCA envía sin aprobación)
# ─────────────────────────────────────────────────────────────────────────────

@comercial.group(name="fase1")
def comercial_fase1() -> None:
    """SDR Multicanal — compone, encola, espera aprobación; NO envía sin orden explícita."""


def _sdr():
    from dotenv import load_dotenv
    load_dotenv()
    from core.knowledge import get_knowledge
    from departments.comercial.cola_aprobacion import ColaAprobacion
    from departments.comercial.lifecycle import LeadStore
    from departments.comercial.sdr.multicanal import SDRMulticanal
    k = get_knowledge()
    store = LeadStore(k, EMPRESA_DEFECTO)
    cola = ColaAprobacion(k, EMPRESA_DEFECTO)
    return SDRMulticanal(lead_store=store, cola=cola), store, cola


def _dump_muestra_md(lead: dict, asunto: str, cuerpo: str, review: dict | None = None,
                    *, pendiente_id: str | None = None, estado: str = "muestra") -> Path:
    """Vuelca el email en un .md legible para revisión humana. Devuelve la ruta del archivo."""
    from datetime import datetime
    raiz = Path(__file__).parent / "_workspace" / "muestras_email"
    raiz.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = (lead.get("id") or "lead").replace("/", "_")[:40]
    ruta = raiz / f"{ts}_{slug}_{estado}.md"
    ubic = (lead.get("ubicacion") or {})
    meta = (lead.get("metadatos_fuente") or {})
    cab = [
        f"# {lead.get('nombre', '?')}",
        f"*Estado: **{estado}**" + (f" · pendiente {pendiente_id}" if pendiente_id else "") + "*",
        "",
        f"- **ID lead:** `{lead.get('id', '?')}`",
        f"- **Categoría ICP:** {lead.get('categoria_icp','?')} ({lead.get('prioridad_icp','?')})",
        f"- **Anillo:** {lead.get('anillo','?')} · {lead.get('distancia_minutos','?')} min en coche",
        f"- **Dirección:** {ubic.get('direccion','?')}",
        f"- **Web:** {(lead.get('contacto') or {}).get('web','—')}",
        f"- **Teléfono:** {(lead.get('contacto') or {}).get('telefono','—')}",
        f"- **Reseñas:** {meta.get('ratings_count','—')} · rating {meta.get('rating','—')}",
        "",
        "## Borrador",
        "",
        f"**Asunto:** {asunto}",
        "",
        cuerpo,
        "",
    ]
    if review:
        cab.extend([
            "## Brand Guardian",
            "",
            f"- aprobado: **{review.get('aprobado')}**",
        ])
        if review.get("problemas"):
            cab.append("- problemas: " + "; ".join(review["problemas"]))
        if review.get("sugerencias"):
            cab.append("- sugerencias: " + "; ".join(review["sugerencias"]))
        if review.get("detalle_llm"):
            cab.extend(["", "**Dictamen LLM:**", "", review["detalle_llm"].strip()])
    ruta.write_text("\n".join(cab), encoding="utf-8")
    return ruta


@comercial_fase1.command(name="preparar")
@click.option("--limite", default=10, show_default=True, type=int)
@click.option("--lead", default=None, help="ID de lead concreto (slug). Si no se da, "
              "el Priorizador elige los top --limite enriquecidos.")
@click.option("--prioridades", default="ALTA,MEDIA", show_default=True,
              help="Prioridades ICP a incluir (coma-separadas).")
def fase1_preparar(limite: int, lead: str | None, prioridades: str) -> None:
    """Compone mensajes para los top leads y los ENCOLA. NUNCA envía nada.

    Además dumpea cada borrador como Markdown en _workspace/muestras_email/<ts>_<lead>.md
    para revisión humana cómoda (abrir en cualquier editor).
    """
    _check_budget()
    sdr, store, cola = _sdr()
    prios = tuple(p.strip().upper() for p in prioridades.split(",") if p.strip())
    res = sdr.preparar(limite=limite, lead_id=lead, prioridades=prios)
    console.print(f"\n[bold cyan]SDR · campaña {res.campaign_id}[/]")
    console.print(f"  preparados (encolados, NO enviados): [bold]{res.preparados}[/]")
    if res.sin_destino:
        console.print(f"  sin destino email (Enrichment §1.5 pendiente): {res.sin_destino}")
    if res.fallos:
        for f in res.fallos:
            console.print(f"  [yellow]·[/] {f}")

    # Dump cada pendiente recién creado a un .md legible.
    rutas: list[Path] = []
    for pid in res.pendientes_ids:
        p = cola.get(pid)
        lead_obj = store.get(p["lead_id"]) or {}
        rutas.append(_dump_muestra_md(
            lead_obj, p["asunto"], p["cuerpo"],
            review=p.get("brand_review"), pendiente_id=pid, estado="pendiente",
        ))
    if rutas:
        console.print(f"\n[dim]Borradores en disco para revisión:[/] "
                      f"[bold]_workspace/muestras_email/[/]")
        for r in rutas[:10]:
            console.print(f"  · {r.name}")
        if len(rutas) > 10:
            console.print(f"  · … +{len(rutas)-10} más")
    console.print(f"\n[dim]Para revisarlos por CLI: kaizen comercial fase1 cola[/]")


@comercial_fase1.command(name="cola")
@click.option("--estado", default="pendiente",
              type=click.Choice(["pendiente", "aprobado", "rechazado", "enviado", "todos"]),
              show_default=True)
@click.option("--campania", default=None)
def fase1_cola(estado: str, campania: str | None) -> None:
    """Lista los mensajes en cola por estado."""
    _, _, cola = _sdr()
    items = cola.listar(estado=None if estado == "todos" else estado, campaign_id=campania)
    if not items:
        console.print("[dim]Cola vacía.[/]")
        return
    from rich.table import Table
    t = Table(box=box.SIMPLE, show_lines=False)
    t.add_column("id", style="dim", width=10)
    t.add_column("lead", style="bold")
    t.add_column("destino")
    t.add_column("asunto")
    t.add_column("brand", justify="center")
    t.add_column("estado", justify="center")
    for it in items:
        brand_ok = (it.get("brand_review") or {}).get("aprobado", False)
        t.add_row(
            it["id"][:8], it["lead_id"][:30],
            (it.get("destino") or "—")[:30], it["asunto"][:50],
            "[green]✓[/]" if brand_ok else "[yellow]?[/]",
            it["estado"],
        )
    console.print(t)


@comercial_fase1.command(name="ver")
@click.argument("pendiente_id")
def fase1_ver(pendiente_id: str) -> None:
    """Muestra un mensaje completo de la cola para revisión humana."""
    _, store, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente_id)]
    if not items:
        console.print(f"[red]No hay pendiente con id que empiece por '{pendiente_id}'.[/]")
        return
    p = items[0]
    lead = store.get(p["lead_id"]) or {}
    _mostrar_pendiente(p, lead)


@comercial_fase1.command(name="muestra")
@click.option("--lead", default=None, help="ID del lead. Si no se da, elige el top del Priorizador.")
def fase1_muestra(lead: str | None) -> None:
    """Genera UN sample y lo muestra. Si no se da --lead, elige el top-priority enriquecido.

    NO se envía nada. NO se persiste si --lead no se da (el sample queda fuera de la cola).
    Si --lead se da, sí se encola para que puedas aprobarlo después.
    """
    _check_budget()
    sdr, store, _ = _sdr()
    if lead is None:
        # Pick top
        from departments.comercial.priorizador import Priorizador
        top = Priorizador(store).cola(limite=1)
        if not top:
            console.print("[red]No hay leads enriquecidos en el Knowledge. Ejecuta primero "
                          "`kaizen comercial fase0`.[/]")
            return
        lead_obj = top[0]
        console.print(f"[dim]Top elegido por Priorizador: [bold]{lead_obj['nombre']}[/] "
                      f"(anillo {lead_obj['anillo']}, prioridad {lead_obj.get('prioridad_icp','?')}).[/]\n")
        # Componer SIN encolar — es solo una muestra
        borrador = sdr.composer.componer(lead_obj)
        ruta_md = _dump_muestra_md(
            lead_obj, borrador.asunto, borrador.cuerpo,
            review={"aprobado": borrador.review.aprobado,
                    "problemas": borrador.review.problemas,
                    "sugerencias": borrador.review.sugerencias,
                    "detalle_llm": borrador.review.detalle_llm},
            estado="muestra",
        )
        _mostrar_borrador_libre(lead_obj, borrador, sdr.composer)
        console.print(f"\n[dim]Archivo en disco para revisión:[/] [bold]{ruta_md}[/]")
    else:
        # Compone y encola para ese lead específico → así puedes aprobarlo si te gusta
        res = sdr.preparar(limite=1, lead_id=lead)
        if not res.pendientes_ids:
            console.print(f"[red]No se pudo preparar mensaje para '{lead}': {res.fallos}[/]")
            return
        pid = res.pendientes_ids[0]
        _, store, cola = _sdr()
        p = cola.get(pid)
        lead_obj = store.get(p["lead_id"]) or {}
        ruta_md = _dump_muestra_md(
            lead_obj, p["asunto"], p["cuerpo"],
            review=p.get("brand_review"), pendiente_id=pid, estado="pendiente",
        )
        _mostrar_pendiente(p, lead_obj)
        console.print(f"\n[dim]Archivo en disco para revisión:[/] [bold]{ruta_md}[/]")


def _mostrar_borrador_libre(lead: dict, borrador, composer) -> None:
    from rich.panel import Panel
    from rich.text import Text
    nombre = lead.get("nombre", "?")
    cabecera = (
        f"[bold]{nombre}[/]\n"
        f"[dim]Categoría: {lead.get('categoria_icp','?')} ({lead.get('prioridad_icp','?')}) · "
        f"Anillo {lead.get('anillo','?')} · "
        f"{lead.get('distancia_minutos','?')} min en coche · "
        f"{(lead.get('ubicacion') or {}).get('direccion','')}[/]"
    )
    review = borrador.review
    review_txt = "[green]✓ Brand Guardian: aprobado[/]" if review.aprobado else (
        "[red]✗ Brand Guardian: " + "; ".join(review.problemas) + "[/]"
    )
    if review.sugerencias:
        review_txt += "\n[yellow]· " + "\n· ".join(review.sugerencias) + "[/]"
    if review.detalle_llm:
        review_txt += f"\n[dim italic]{review.detalle_llm.strip()}[/]"

    contenido = (
        f"[bold]Asunto:[/] {borrador.asunto}\n\n"
        f"{borrador.cuerpo}\n"
    )
    console.print(Panel(cabecera, title="Lead", border_style="cyan", box=box.ROUNDED))
    console.print(Panel(contenido, title="Borrador (NO ENVIADO · solo muestra)",
                        border_style="green", box=box.ROUNDED))
    console.print(Panel(review_txt, title="Revisión", border_style="magenta", box=box.ROUNDED))
    console.print("\n[dim]Para encolar y aprobar este lead concreto:[/]")
    console.print(f"  kaizen comercial fase1 muestra --lead {lead.get('id','')}")
    console.print("  kaizen comercial fase1 aprobar <pendiente_id>")


def _mostrar_pendiente(p: dict, lead: dict) -> None:
    from rich.panel import Panel
    nombre = lead.get("nombre") or p.get("lead_id", "?")
    cabecera = (
        f"[bold]{nombre}[/]\n"
        f"[dim]Pendiente {p['id']} · estado [bold]{p['estado']}[/] · "
        f"campaña {p['campaign_id']}[/]\n"
        f"[dim]Destino: {p.get('destino') or 'no descubierto aún (Enrichment §1.5 pendiente)'}[/]"
    )
    review = p.get("brand_review") or {}
    if review.get("aprobado"):
        review_txt = "[green]✓ Brand Guardian: aprobado[/]"
    else:
        review_txt = "[red]✗ Brand Guardian: " + "; ".join(review.get("problemas", [])) + "[/]"
    if review.get("sugerencias"):
        review_txt += "\n[yellow]· " + "\n· ".join(review["sugerencias"]) + "[/]"
    contenido = f"[bold]Asunto:[/] {p['asunto']}\n\n{p['cuerpo']}\n"
    console.print(Panel(cabecera, title="Lead", border_style="cyan", box=box.ROUNDED))
    console.print(Panel(contenido, title="Borrador (en cola · NO enviado)",
                        border_style="green", box=box.ROUNDED))
    console.print(Panel(review_txt, title="Revisión", border_style="magenta", box=box.ROUNDED))
    if p["estado"] == "pendiente":
        console.print(f"\n[dim]Si te convence:[/]")
        console.print(f"  kaizen comercial fase1 aprobar {p['id'][:8]}")
        console.print(f"[dim]Si quieres regenerar / rechazar:[/]")
        console.print(f"  kaizen comercial fase1 rechazar {p['id'][:8]} --motivo \"...\"")


@comercial_fase1.command(name="aprobar")
@click.argument("pendiente_id")
def fase1_aprobar(pendiente_id: str) -> None:
    _, _, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente_id)]
    if not items:
        console.print(f"[red]No existe pendiente que empiece por '{pendiente_id}'.[/]")
        return
    nodo = cola.aprobar(items[0]["id"])
    console.print(f"[green]✓ Aprobado[/] · token: [dim]{nodo['token_aprobacion'][:12]}…[/]")
    console.print("[dim]El envío real requiere además KAIZEN_ENVIO_HABILITADO=true "
                  "y `kaizen comercial fase1 enviar --confirmar-envio-real`.[/]")


@comercial_fase1.command(name="aprobar-campania")
@click.argument("campaign_id")
def fase1_aprobar_campania(campaign_id: str) -> None:
    _, _, cola = _sdr()
    nodos = cola.aprobar_campania(campaign_id)
    console.print(f"[green]✓ Aprobada campaña[/] {campaign_id}: {len(nodos)} mensajes.")


@comercial_fase1.command(name="rechazar")
@click.argument("pendiente_id")
@click.option("--motivo", required=True)
def fase1_rechazar(pendiente_id: str, motivo: str) -> None:
    _, _, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente_id)]
    if not items:
        console.print(f"[red]No existe pendiente que empiece por '{pendiente_id}'.[/]")
        return
    cola.rechazar(items[0]["id"], motivo)
    console.print(f"[yellow]· Rechazado[/] · motivo: {motivo}")


@comercial_fase1.group(name="voz")
def comercial_fase1_voz() -> None:
    """SDR conversacional bidireccional — voz clonada de Iván vía ElevenLabs CAI + Twilio."""


@comercial_fase1_voz.command(name="desplegar-agente")
@click.option("--version", default="v2", show_default=True,
              help="Versión del snapshot a desplegar (agente_config_<version>.py).")
def fase1_voz_desplegar_agente(version: str) -> None:
    """Despliega el snapshot del agente a ElevenLabs CAI (idempotente).

    Requiere que ELEVENLABS_API_KEY tenga los scopes convai_read + convai_write.
    Si ya existe un agente con el mismo nombre, lo actualiza. Si no, lo crea.
    Guarda el `agent_id` en .env como ELEVENLABS_AGENT_ID.
    """
    from dotenv import load_dotenv; load_dotenv()
    import importlib
    snapshot = importlib.import_module(
        f"departments.comercial.sdr.voz_conversacional.agente_config_{version}"
    )
    from departments.comercial.sdr.voz_conversacional.cliente_eleven_cai import ClienteCAI
    try:
        res = ClienteCAI().crear_o_actualizar_agente(snapshot)
    except Exception as e:
        console.print(f"[red]✗ Despliegue falló:[/] {e}")
        if "401" in str(e) or "scope" in str(e).lower():
            console.print("[yellow]ⓘ Tu ELEVENLABS_API_KEY no tiene los scopes "
                          "convai_read + convai_write. Añádelos en el dashboard "
                          "de ElevenLabs → Profile → API Keys, o configura el agente "
                          "manualmente desde el dashboard de Conversational AI.[/]")
        sys.exit(1)

    verbo = "creado" if res.creado else "actualizado"
    console.print(f"[green]✓ Agente {verbo}[/] · [bold]{res.nombre}[/] · "
                  f"agent_id=[bold cyan]{res.agent_id}[/]")

    # Persistir agent_id en .env
    p = Path(".env")
    texto = p.read_text(encoding="utf-8") if p.exists() else ""
    import re as _re
    if _re.search(r"^ELEVENLABS_AGENT_ID=", texto, _re.M):
        texto = _re.sub(r"^ELEVENLABS_AGENT_ID=.*$",
                        f"ELEVENLABS_AGENT_ID={res.agent_id}", texto, flags=_re.M)
    else:
        texto = texto.rstrip() + f"\nELEVENLABS_AGENT_ID={res.agent_id}\n"
    p.write_text(texto, encoding="utf-8")
    console.print(f"[dim].env actualizado con ELEVENLABS_AGENT_ID[/]")


# ─────────────────────────────────────────────────────────────────────────────
#  voz_play: MP3 pre-renderizado con voz clonada (el stack que funciona)
# ─────────────────────────────────────────────────────────────────────────────

@comercial_fase1_voz.group(name="play")
def comercial_fase1_voz_play() -> None:
    """SDR voz por MP3 pre-renderizado con voz clonada (estable y probado).

    Cada lead recibe una llamada con un mensaje hablado por Iván (TTS) personalizado
    para ese lead. NO es conversación bidireccional. La parte conversacional queda
    pausada hasta resolver la arquitectura — esto es lo que SÍ funciona.
    """


@comercial_fase1_voz_play.command(name="preparar")
@click.option("--limite", default=3, show_default=True, type=int)
@click.option("--lead", default=None, help="ID concreto del lead a preparar.")
def fase1_voz_play_preparar(limite: int, lead: str | None) -> None:
    """Genera mensaje personalizado por Claude + sintetiza MP3 con tu voz clonada +
    encola pendiente `canal='voz_play'`. NO llama a nadie.
    """
    _check_budget()
    from dotenv import load_dotenv; load_dotenv()
    _, store, cola = _sdr()
    from datetime import datetime, timezone
    from departments.comercial.priorizador import Priorizador
    from departments.comercial.sdr.voz_play.composer import ComposerVoz

    if lead:
        l = store.get(lead)
        if l is None:
            console.print(f"[red]Lead '{lead}' no existe en Knowledge.[/]"); return
        leads = [l]
    else:
        ya_en_play = {p["lead_id"] for p in cola.listar()
                      if p.get("canal") == "voz_play"
                      and p["estado"] in ("pendiente", "aprobado", "enviado")}
        leads = [l for l in Priorizador(store).cola(excluir_lead_ids=ya_en_play)
                 if (l.get("contacto") or {}).get("telefono")][:limite]

    if not leads:
        console.print("[yellow]Sin leads disponibles con teléfono.[/]"); return

    composer = ComposerVoz()
    campaign_id = f"play_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    base = os.environ.get("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")

    console.print(f"\n[bold cyan]SDR voz_play · campaña {campaign_id}[/]")
    for l in leads:
        try:
            guion = composer.componer(l)
        except Exception as e:
            console.print(f"  [red]✗[/] {l.get('nombre','?')}: {e}")
            continue
        tel = (l.get("contacto") or {}).get("telefono", "")
        mp3_url = f"{base}/{guion.mp3_path.name}" if base else ""
        p = cola.encolar(
            lead_id=l["id"], canal="voz_play", destino=tel,
            asunto=f"Voz personalizada · {l.get('nombre','')}",
            cuerpo=guion.texto,
            brand_review=guion.review,
            campaign_id=campaign_id,
            razones_personalizacion=[
                f"anillo {l.get('anillo','?')} · prioridad {l.get('prioridad_icp','?')}"
            ],
        )
        nodo = cola.get(p.id)
        nodo["mp3_path"] = str(guion.mp3_path)
        nodo["mp3_bytes"] = guion.mp3_bytes
        nodo["mp3_url"] = mp3_url
        nodo["voice_id"] = guion.voice_id
        cola.k.add(cola.company, "email_pendiente_aprobacion", p.id, nodo)
        review_emoji = "[green]✓[/]" if guion.review["aprobado"] else "[yellow]?[/]"
        console.print(f"  {review_emoji} {l.get('nombre','?')[:35]:35s}  "
                      f"{tel:16s}  {guion.mp3_bytes//1024}KB  pid={p.id[:8]}")
        if not guion.review["aprobado"]:
            for prob in guion.review["problemas"]:
                console.print(f"      [yellow]· {prob}[/]")
    console.print(f"\n[dim]Escuchar: kaizen comercial fase1 voz play escuchar <pid>[/]")
    console.print(f"[dim]Aprobar: kaizen comercial fase1 aprobar <pid>[/]")
    console.print(f"[dim]Lanzar: kaizen comercial fase1 voz play lanzar --pendiente <pid> "
                  f"--confirmar-envio-real[/]")


@comercial_fase1_voz_play.command(name="escuchar")
@click.argument("pid_partial")
def fase1_voz_play_escuchar(pid_partial: str) -> None:
    """Muestra el texto del guion + abre el MP3 en el reproductor del sistema."""
    _, store, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pid_partial)]
    if not items:
        console.print(f"[red]Sin pendiente que empiece por '{pid_partial}'.[/]"); return
    p = items[0]
    lead = store.get(p["lead_id"]) or {}
    mp3 = p.get("mp3_path")
    if not mp3:
        console.print(f"[red]Pendiente sin MP3 asociado.[/]"); return
    from rich.panel import Panel
    review = p.get("brand_review") or {}
    review_txt = "[green]✓ Brand Guardian aprueba[/]" if review.get("aprobado") else \
                 "[yellow]Brand Guardian con observaciones:[/] " + "; ".join(review.get("problemas", []))
    console.print(Panel(
        f"[bold]{lead.get('nombre', p['lead_id'])}[/]\n"
        f"[dim]{lead.get('categoria_icp','?')} · Anillo {lead.get('anillo','?')} · "
        f"Destino: {p.get('destino','')}[/]\n"
        f"[dim]Estado: {p['estado']} · {review_txt}[/]\n\n"
        f"[bold]Texto sintetizado:[/]\n{p['cuerpo']}\n\n"
        f"[bold]MP3 local:[/] {mp3}\n[bold]URL pública:[/] {p.get('mp3_url','—')}",
        border_style="cyan",
    ))
    import platform
    try:
        if platform.system() == "Windows":
            os.startfile(mp3)
        elif platform.system() == "Darwin":
            import subprocess; subprocess.call(["open", mp3])
        else:
            import subprocess; subprocess.call(["xdg-open", mp3])
        console.print("[dim](Abriendo reproductor del sistema)[/]")
    except Exception as e:
        console.print(f"[yellow]No pude abrirlo automáticamente: {e}.[/]")


@comercial_fase1_voz_play.command(name="lanzar")
@click.option("--pendiente", required=True, help="ID del pendiente aprobado.")
@click.option("--confirmar-envio-real", is_flag=True, required=True,
              help="Flag obligatorio para confirmar llamada real.")
@click.option("--ignorar-franja", is_flag=True,
              help="Salta franja horaria (test fuera de horario).")
def fase1_voz_play_lanzar(pendiente: str, confirmar_envio_real: bool,
                           ignorar_franja: bool) -> None:
    """Coloca la llamada Twilio con `<Play>` apuntando al MP3 personalizado."""
    if not confirmar_envio_real:
        console.print("[red]Falta --confirmar-envio-real.[/]"); sys.exit(2)
    from dotenv import load_dotenv; load_dotenv()
    _, store, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente)]
    if not items:
        console.print(f"[red]Sin pendiente '{pendiente}'.[/]"); sys.exit(2)
    p = items[0]
    if p.get("canal") != "voz_play":
        console.print(f"[red]canal='{p.get('canal')}', no 'voz_play'.[/]"); sys.exit(2)
    if not p.get("mp3_url"):
        console.print(f"[red]Sin mp3_url.[/]"); sys.exit(2)
    lead = store.get(p["lead_id"])
    if not lead:
        console.print(f"[red]Lead '{p['lead_id']}' no existe.[/]"); sys.exit(2)

    from departments.comercial.sdr.voz_conversacional import pre_flight
    pf = pre_flight.verificar(lead=lead, pendiente=p, ignorar_franja=ignorar_franja)
    if not pf.ok:
        console.print("[red]✗ Pre-flight bloqueó la llamada:[/]")
        for f in pf.fallos: console.print(f"  · {f}")
        sys.exit(1)
    for w in pf.advertencias: console.print(f"  [yellow]·[/] {w}")

    from departments.comercial.cola_aprobacion import hash_mensaje
    telefono = pf.contexto["telefono_e164"]
    h = hash_mensaje("voz_play", telefono, p["asunto"], p["cuerpo"])
    try:
        cola.verificar_token(pendiente_id=p["id"],
                              token=p["token_aprobacion"], hash_a_enviar=h)
    except Exception:
        h_orig = hash_mensaje("voz_play", p["destino"], p["asunto"], p["cuerpo"])
        try:
            cola.verificar_token(pendiente_id=p["id"],
                                  token=p["token_aprobacion"], hash_a_enviar=h_orig)
        except Exception as e2:
            console.print(f"[red]✗ Token/hash inválido: {e2}[/]"); sys.exit(1)

    from departments.comercial.sdr.voz_conversacional import agente_config_v2 as snap
    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    from departments.comercial.sdr.voz_play.outbound import colocar_llamada
    res = colocar_llamada(
        telefono_destino_e164=telefono, mp3_url=p["mp3_url"],
        aviso_legal=snap.aviso_legal_twilio(),
    )
    if not res.ok:
        console.print(f"[red]✗ Twilio rechazó:[/] {res.motivo}"); sys.exit(1)

    from core.knowledge import get_knowledge
    k = get_knowledge()
    _t.crear_llamada(k, EMPRESA_DEFECTO,
                     call_sid=res.call_sid, lead_id=lead["id"], pendiente_id=p["id"],
                     agente_config_version=f"voz_play_{snap.VERSION}",
                     aviso_legal_version=snap.VERSION, telefono_destino=telefono)
    cola.marcar_enviado(p["id"], referencia_externa=res.call_sid)
    console.print(f"\n[bold green]✓ Llamada colocada[/]")
    console.print(f"  call_sid: [bold cyan]{res.call_sid}[/]")
    console.print(f"  destino: {telefono}")
    console.print(f"  mp3: {p['mp3_url']}")


@comercial_fase1_voz.command(name="preparar")
@click.option("--limite", default=5, show_default=True, type=int)
@click.option("--lead", default=None, help="ID concreto del lead a encolar para voz.")
def fase1_voz_preparar(limite: int, lead: str | None) -> None:
    """Encola leads para llamada de voz. NO coloca llamadas — solo crea pendientes
    `canal='voz'` que después tendrás que aprobar y lanzar explícitamente.
    El cuerpo del pendiente contiene el `first_message` del agente (lo que el
    cliente oirá al inicio); el hash de aprobación queda ligado a ese mensaje."""
    _, store, cola = _sdr()
    from datetime import datetime, timezone
    from departments.comercial.priorizador import Priorizador
    from departments.comercial.sdr.voz_conversacional import agente_config_v2 as snap

    if lead:
        leads = [store.get(lead)] if store.get(lead) else []
    else:
        ya_en_voz = {p["lead_id"] for p in cola.listar()
                     if p.get("canal") == "voz" and p["estado"] in ("pendiente", "aprobado", "enviado")}
        # Priorizador devuelve enriquecidos; filtramos los que tienen teléfono.
        candidatos = Priorizador(store).cola(excluir_lead_ids=ya_en_voz)
        leads = [l for l in candidatos if (l.get("contacto") or {}).get("telefono")][:limite]

    if not leads:
        console.print("[yellow]No hay leads enriquecidos con teléfono disponibles para voz.[/]")
        return

    campaign_id = f"voz_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    asunto = f"Llamada de voz · agente {snap.VERSION}"
    cuerpo = snap.FIRST_MESSAGE
    brand_review = {"aprobado": True, "tipo": "voz",
                    "agente_config_version": snap.VERSION,
                    "voice_id": snap.VOZ["voice_id"],
                    "llm": snap.LLM["model"]}

    encolados = []
    for l in leads:
        if not l: continue
        tel = (l.get("contacto") or {}).get("telefono", "")
        p = cola.encolar(lead_id=l["id"], canal="voz", destino=tel,
                         asunto=asunto, cuerpo=cuerpo,
                         brand_review=brand_review, campaign_id=campaign_id,
                         razones_personalizacion=[
                             f"anillo {l.get('anillo','?')} · "
                             f"prioridad {l.get('prioridad_icp','?')} · "
                             f"{l.get('categoria_icp','?')}"
                         ])
        encolados.append((l["nombre"], tel, p.id))

    console.print(f"\n[bold cyan]SDR voz · campaña {campaign_id}[/]")
    console.print(f"  encolados (NO lanzados): [bold]{len(encolados)}[/]")
    for nombre, tel, pid in encolados[:10]:
        console.print(f"  · {nombre[:40]:40s}  {tel:18s}  pid={pid[:8]}")
    console.print(f"\n[dim]Revisa la cola: kaizen comercial fase1 cola --canal voz[/]")
    console.print(f"[dim]Lanza una llamada: kaizen comercial fase1 voz lanzar --pendiente <pid> "
                  f"--confirmar-envio-real[/]")


@comercial_fase1_voz.command(name="dry-run")
@click.option("--pendiente", required=True, help="ID del pendiente aprobado a inspeccionar.")
@click.option("--ignorar-franja", is_flag=True)
def fase1_voz_dry_run(pendiente: str, ignorar_franja: bool) -> None:
    """Muestra qué se enviaría a ElevenLabs Outbound API SIN colocar la llamada.

    Idéntico flujo que `lanzar` excepto el POST final: corre pre_flight, verifica
    token+hash, construye el body, y lo pinta en pantalla. Útil para validar antes
    de marcar el teléfono.
    """
    from dotenv import load_dotenv; load_dotenv()
    _, store, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente)]
    if not items:
        console.print(f"[red]No existe pendiente '{pendiente}'.[/]"); sys.exit(2)
    p = items[0]
    if p.get("canal") != "voz":
        console.print(f"[red]canal='{p.get('canal')}', no 'voz'.[/]"); sys.exit(2)
    lead = store.get(p["lead_id"])
    if not lead:
        console.print(f"[red]Lead '{p['lead_id']}' no existe.[/]"); sys.exit(2)

    from departments.comercial.sdr.voz_conversacional import pre_flight, eleven_outbound
    pf = pre_flight.verificar(lead=lead, pendiente=p, ignorar_franja=ignorar_franja)
    console.print("\n[bold]Pre-flight:[/]")
    if pf.ok:
        console.print("  [green]✓ todos los checks pasan[/]")
    else:
        for f in pf.fallos: console.print(f"  [red]·[/] {f}")
    for w in pf.advertencias: console.print(f"  [yellow]·[/] {w}")

    telefono = pf.contexto.get("telefono_e164", p.get("destino", ""))
    inspeccion = eleven_outbound.dry_run(to_number_e164=telefono, lead=lead)
    from rich.panel import Panel
    from rich.json import JSON
    console.print(Panel(JSON.from_data(inspeccion),
                        title="Lo que se mandaría a ElevenLabs (NO enviado)",
                        border_style="cyan"))
    if not pf.ok or any(v == "FALTA" for v in inspeccion["estado_credenciales"].values()):
        console.print("\n[yellow]No se puede lanzar — resuelve lo de arriba primero.[/]")
    else:
        console.print(f"\n[green]Listo para lanzar.[/] Comando real:")
        console.print(f"  kaizen comercial fase1 voz lanzar --pendiente {p['id'][:8]} "
                      f"--confirmar-envio-real" +
                      (" --ignorar-franja" if ignorar_franja else ""))


@comercial_fase1_voz.command(name="lanzar")
@click.option("--pendiente", required=True, help="ID del pendiente aprobado a lanzar.")
@click.option("--confirmar-envio-real", is_flag=True, required=True,
              help="Flag obligatorio (igual que envío de email): confirma llamada real.")
@click.option("--ignorar-franja", is_flag=True,
              help="Salta el check de franja horaria comercial (solo para tu propio número).")
def fase1_voz_lanzar(pendiente: str, confirmar_envio_real: bool, ignorar_franja: bool) -> None:
    """Coloca una llamada Twilio para un pendiente aprobado. Pre-flight enforcement total."""
    if not confirmar_envio_real:
        console.print("[red]Falta --confirmar-envio-real.[/]"); sys.exit(2)
    _, store, cola = _sdr()
    items = [p for p in cola.listar() if p["id"].startswith(pendiente)]
    if not items:
        console.print(f"[red]No existe pendiente '{pendiente}'.[/]"); sys.exit(2)
    p = items[0]
    if p.get("canal") != "voz":
        console.print(f"[red]El pendiente '{p['id'][:8]}' es canal '{p.get('canal')}', no 'voz'.[/]")
        sys.exit(2)

    lead = store.get(p["lead_id"])
    if not lead:
        console.print(f"[red]Lead '{p['lead_id']}' no existe.[/]"); sys.exit(2)

    # ── Pre-flight ─────────────────────────────────────────────────────────
    from departments.comercial.sdr.voz_conversacional import pre_flight
    res_pf = pre_flight.verificar(lead=lead, pendiente=p, ignorar_franja=ignorar_franja)
    if not res_pf.ok:
        console.print("[red]✗ Pre-flight bloqueó la llamada:[/]")
        for f in res_pf.fallos:
            console.print(f"  · {f}")
        sys.exit(1)
    for w in res_pf.advertencias:
        console.print(f"  [yellow]·[/] {w}")

    telefono = res_pf.contexto["telefono_e164"]

    # ── Verificar token + hash (3ª barrera arquitectónica) ─────────────────
    from departments.comercial.cola_aprobacion import hash_mensaje
    h = hash_mensaje("voz", telefono, p["asunto"], p["cuerpo"])
    try:
        cola.verificar_token(pendiente_id=p["id"], token=p["token_aprobacion"], hash_a_enviar=h)
    except Exception as e:
        # Si destino se normalizó, el hash original (sin normalizar) puede no coincidir.
        # Aceptamos como advertencia y re-verificamos con el destino aprobado.
        h_orig = hash_mensaje("voz", p["destino"], p["asunto"], p["cuerpo"])
        try:
            cola.verificar_token(pendiente_id=p["id"], token=p["token_aprobacion"], hash_a_enviar=h_orig)
        except Exception as e2:
            console.print(f"[red]✗ Token/hash inválido: {e2}[/]"); sys.exit(1)

    # ── Colocar llamada vía ElevenLabs Outbound API (NO directo a Twilio) ──
    # `<Connect><Stream>` directo a CAI no funciona — ElevenLabs orquesta su propio
    # POST a Twilio Calls.json usando el número importado, y maneja el audio.
    from departments.comercial.sdr.voz_conversacional import eleven_outbound, transcripts
    res_cai = eleven_outbound.colocar_llamada_via_cai(
        to_number_e164=telefono, lead=lead,
    )
    if not res_cai.ok:
        console.print(f"[red]✗ ElevenLabs rechazó: {res_cai.motivo}[/]"); sys.exit(1)
    # Adaptamos la respuesta CAI al schema esperado por el resto del pipeline.
    class _R:
        call_sid = res_cai.call_sid or res_cai.conversation_id
        twilio_status = "queued (vía CAI)"
        conversation_id = res_cai.conversation_id
    res = _R()

    # Persistir el nodo `llamada` en Knowledge (los webhooks lo irán completando).
    from core.knowledge import get_knowledge
    k = get_knowledge()
    transcripts.crear_llamada(k, EMPRESA_DEFECTO,
                               call_sid=res.call_sid, lead_id=lead["id"],
                               pendiente_id=p["id"],
                               agente_config_version="v2", aviso_legal_version="v2",
                               telefono_destino=telefono)
    cola.marcar_enviado(p["id"], referencia_externa=res.call_sid)
    console.print(f"\n[bold green]✓ Llamada colocada[/]")
    console.print(f"  call_sid: [bold cyan]{res.call_sid}[/]")
    console.print(f"  status: {res.twilio_status}")
    console.print(f"  destino: {telefono}")
    console.print(f"\n[dim]Esperando webhooks (status/recording/transcript) para análisis post-call.[/]")


@comercial_fase1_voz.command(name="transcripts")
@click.argument("lead_id")
def fase1_voz_transcripts(lead_id: str) -> None:
    """Lista las llamadas (+transcripts) de un lead concreto."""
    _, store, _ = _sdr()
    from core.knowledge import get_knowledge
    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    k = get_knowledge()
    todas = _t.todas_las_llamadas(k, EMPRESA_DEFECTO)
    de_lead = [l for l in todas if l.get("lead_id") == lead_id]
    if not de_lead:
        console.print(f"[dim]Sin llamadas registradas para '{lead_id}'.[/]"); return
    from rich.table import Table
    t = Table(box=box.SIMPLE)
    t.add_column("call_sid"); t.add_column("estado"); t.add_column("inicio")
    t.add_column("duración", justify="right"); t.add_column("turnos", justify="right")
    for l in de_lead:
        turnos = len(l.get("transcript") or [])
        t.add_row(l["id"][-16:], l.get("estado", "?"),
                  (l.get("inicio_ts","") or "")[:19],
                  f"{l.get('duracion_s',0):.0f}s", str(turnos))
    console.print(t)


@comercial_fase1_voz.command(name="analisis")
@click.argument("call_sid")
def fase1_voz_analisis(call_sid: str) -> None:
    """Muestra el dictamen de calidad para un call_sid."""
    from core.knowledge import get_knowledge
    k = get_knowledge()
    # Buscar el analisis cuyo call_sid coincida (parcial).
    for an_id, an in k.all(EMPRESA_DEFECTO, "analisis_llamada").items():
        if an.get("call_sid", "").endswith(call_sid) or call_sid in an_id:
            from rich.panel import Panel
            from rich.json import JSON
            console.print(Panel(JSON.from_data(an), title=f"Análisis · {an_id}",
                                border_style="cyan"))
            return
    console.print(f"[red]Sin análisis para '{call_sid}'.[/]")


@comercial_fase1_voz.command(name="grabacion")
@click.argument("call_sid")
def fase1_voz_grabacion(call_sid: str) -> None:
    """Muestra la ruta local del MP3 + metadata de la grabación."""
    from core.knowledge import get_knowledge
    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    k = get_knowledge()
    todas = _t.todas_las_llamadas(k, EMPRESA_DEFECTO)
    coincide = [l for l in todas if l["id"].endswith(call_sid) or call_sid in l["id"]]
    if not coincide:
        console.print(f"[red]Sin llamada para '{call_sid}'.[/]"); return
    l = coincide[0]
    console.print(f"  call_sid: [bold]{l['id']}[/]")
    console.print(f"  lead: {l.get('lead_id','?')}")
    console.print(f"  estado: {l.get('estado','?')}")
    console.print(f"  recording_path: {l.get('recording_path','(no descargado)')}")
    console.print(f"  recording_bytes: {l.get('recording_bytes','?')}")
    console.print(f"  recording_sha256: {l.get('recording_sha256','?')}")
    console.print(f"  duracion: {l.get('duracion_s','?')}s")


@comercial_fase1_voz.command(name="estado-agente")
def fase1_voz_estado_agente() -> None:
    """Consulta el agente activo en ElevenLabs (verifica que el deploy está vivo)."""
    from dotenv import load_dotenv; load_dotenv()
    import os
    aid = os.environ.get("ELEVENLABS_AGENT_ID")
    if not aid:
        console.print("[red]No hay ELEVENLABS_AGENT_ID en .env. Ejecuta desplegar-agente.[/]")
        sys.exit(2)
    from departments.comercial.sdr.voz_conversacional.cliente_eleven_cai import ClienteCAI
    try:
        d = ClienteCAI().obtener_agente(aid)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)
    console.print(f"[bold]Agente:[/] {d.get('name')}")
    console.print(f"[bold]ID:[/] {aid}")
    cfg = d.get("conversation_config", {}) or {}
    agente_cfg = cfg.get("agent", {}) or {}
    prompt_cfg = agente_cfg.get("prompt", {}) or {}
    tts_cfg    = cfg.get("tts", {}) or {}
    console.print(f"  LLM: {prompt_cfg.get('llm','?')} · temp={prompt_cfg.get('temperature','?')}")
    console.print(f"  Voz: {tts_cfg.get('voice_id','?')} · modelo {tts_cfg.get('model_id','?')}")
    console.print(f"  First message ({len(agente_cfg.get('first_message',''))} chars): "
                  f"{agente_cfg.get('first_message','')[:80]}...")


@comercial_fase1.command(name="descubrir-emails")
@click.option("--limite", default=None, type=int,
              help="Procesa solo los primeros N leads ENRIQUECIDOS sin email.")
@click.option("--lead", default=None, help="Solo este lead (su slug).")
def fase1_descubrir_emails(limite: int | None, lead: str | None) -> None:
    """Recorre leads ENRIQUECIDOS sin email, hace fetch de su web y extrae el contacto.

    Sin LLM; regex + ranking por prefijos comerciales. Skip de redes sociales (FB/IG/Twitter)
    donde el email no está expuesto. Persiste en `lead.contacto.email`.
    """
    _, store, _ = _sdr()
    from departments.comercial.email_discovery import descubrir_emails
    res = descubrir_emails(store, limite=limite, lead_id=lead)
    console.print(f"\n[bold]Descubrimiento de emails[/]")
    console.print(f"  procesados:       {res.procesados}")
    console.print(f"  [green]descubiertos:[/]     {res.descubiertos}")
    console.print(f"  ya tenían email:  {res.con_email_previo}")
    console.print(f"  sin web:          {res.sin_web}")
    console.print(f"  solo redes soc.:  {res.web_solo_social}")
    console.print(f"  no encontrado:    {res.no_encontrado}")
    console.print(f"  errores:          {res.errores}")


@comercial_fase1.command(name="detectar")
@click.argument("lead_id")
@click.option("--texto", default=None, help="Texto de respuesta del cliente.")
@click.option("--stdin", is_flag=True, help="Lee el texto desde stdin (un pipe).")
@click.option("--escalar", is_flag=True,
              help="Si el detector confirma compromiso (≥0.6 confianza), llama al "
                   "Account Executive para transicionar y registrar la operación.")
def fase1_detectar(lead_id: str, texto: str | None, stdin: bool, escalar: bool) -> None:
    """Analiza una respuesta del cliente y decide si hay Compromiso Recíproco."""
    _check_budget()
    if stdin:
        texto = sys.stdin.read()
    if not texto:
        console.print("[red]Falta --texto o --stdin con el contenido de la respuesta.[/]")
        sys.exit(2)
    _, store, _ = _sdr()
    lead = store.get(lead_id)
    if lead is None:
        console.print(f"[red]Lead '{lead_id}' no existe.[/]")
        sys.exit(2)
    from departments.comercial.sdr.compromiso import CompromisoDetector
    decision = CompromisoDetector().evaluar(texto, lead=lead)
    emoji = "[green]✓[/]" if decision.es_compromiso else "[yellow]·[/]"
    console.print(f"\n{emoji} es_compromiso=[bold]{decision.es_compromiso}[/] · "
                  f"confianza=[bold]{decision.confianza:.2f}[/]")
    console.print(f"  motivo: {decision.motivo}")
    if decision.senales_detectadas:
        console.print("  señales:")
        for s in decision.senales_detectadas:
            console.print(f"    · \"{s}\"")
    console.print(f"  recomendación: [bold]{decision.recomendacion}[/]")

    if escalar and decision.es_compromiso:
        from departments.comercial.account_executive import AccountExecutive
        ae = AccountExecutive(lead_store=store)
        res = ae.gestionar_compromiso(lead_id, decision, respuesta_texto=texto)
        if res.ok:
            console.print(f"\n[bold green]✓ Lead escalado.[/] operación: {res.operacion_id}")
        else:
            console.print(f"\n[yellow]· No escalado:[/] {res.motivo}")


@comercial_fase1.command(name="reporte")
@click.option("--tipo", default="diario", type=click.Choice(["diario", "semanal"]),
              show_default=True)
def fase1_reporte(tipo: str) -> None:
    """Genera el reporte (diario o semanal con las 5 secciones del v0.2 §7.4)."""
    _, store, cola = _sdr()
    from departments.comercial import rituales
    fn = rituales.daily_report if tipo == "diario" else rituales.weekly_report
    ruta = fn(lead_store=store, cola=cola)
    console.print(f"[green]✓[/] Reporte {tipo} generado: [bold]{ruta}[/]")


@comercial_fase1.command(name="operaciones")
@click.option("--estado", default=None,
              type=click.Choice(["preparada", "enviada", "convertida", "descartada"]))
def fase1_operaciones(estado: str | None) -> None:
    """Lista las operaciones de muestra preparadas por el Account Executive."""
    _, store, _ = _sdr()
    from departments.comercial.account_executive import AccountExecutive
    ae = AccountExecutive(lead_store=store)
    ops = ae.listar_operaciones(estado)
    if not ops:
        console.print("[dim]No hay operaciones registradas.[/]")
        return
    from rich.table import Table
    t = Table(box=box.SIMPLE)
    t.add_column("operacion"); t.add_column("lead"); t.add_column("estado")
    t.add_column("confianza", justify="right"); t.add_column("creada")
    for o in ops:
        dc = o.get("decision_compromiso") or {}
        t.add_row(o["id"][-16:], o["lead_id"][:30], o["estado"],
                  f"{dc.get('confianza',0):.2f}", o.get("creada_en","")[:19])
    console.print(t)


@comercial_fase1.command(name="enviar")
@click.option("--pendiente", default=None, help="ID específico a enviar.")
@click.option("--todos-aprobados", is_flag=True, help="Envía TODOS los aprobados.")
@click.option("--confirmar-envio-real", is_flag=True, required=True,
              help="Flag obligatorio para confirmar envío SMTP real.")
def fase1_enviar(pendiente: str | None, todos_aprobados: bool, confirmar_envio_real: bool) -> None:
    """Envía SOLO los aprobados. Requiere --confirmar-envio-real + KAIZEN_ENVIO_HABILITADO=true."""
    if not confirmar_envio_real:
        console.print("[red]Falta --confirmar-envio-real.[/]")
        return
    sdr, _, cola = _sdr()
    if pendiente:
        items = [p for p in cola.listar(estado="aprobado") if p["id"].startswith(pendiente)]
        ids = [p["id"] for p in items]
    elif todos_aprobados:
        ids = None      # SDR lo resuelve
    else:
        console.print("[red]Indica --pendiente <id> o --todos-aprobados.[/]")
        return
    res = sdr.enviar(pendientes_ids=ids)
    console.print(f"\n[bold]Resultado:[/]  enviados={res.enviados} · "
                  f"bloqueados={res.bloqueados_sin_aprobacion} · "
                  f"canal_off={res.canal_deshabilitado} · "
                  f"fallos_smtp={res.fallos_smtp}")
    for d in res.detalle[:10]:
        console.print(f"  · {d}")


# ─────────────────────────────────────────────────────────────────────────────
#  Comandos de diagnóstico — `kaizen test ...`
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def test() -> None:
    """Comandos de prueba (diagnóstico de canales antes de activarlos)."""


@test.command(name="voz")
@click.argument("numero")
@click.option("--texto", default=None, help="Texto a sintetizar (por defecto un saludo de prueba CON disclosure de IA).")
@click.option("--solo-mp3", is_flag=True, help="Solo genera el MP3 local; no coloca llamada Twilio.")
@click.option("--confirmar-envio-real", is_flag=True,
              help="Obligatorio para colocar una llamada real (R-02). Sin este flag: solo MP3.")
def test_voz(numero: str, texto: str | None, solo_mp3: bool, confirmar_envio_real: bool) -> None:
    """Genera un MP3 con la voz clonada (ElevenLabs). La llamada REAL exige --confirmar-envio-real
    y cruza la guardia de seguridad (R-02): voz no de baja, sandbox on, y NUMERO en tu allowlist.

    Antes de la correccion del 2026-07-20, este comando colocaba una llamada real saltandose
    sandbox, aprobacion, Robinson, franja y cuota, con un guion que se hacia pasar por Ivan sin
    avisar de que es IA. Ahora: por defecto solo genera MP3; la llamada real pasa por la guardia.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from departments.comercial.sdr.canales.voz import VoiceChannel, VozBloqueada
    import os

    canal = VoiceChannel()
    # Guion por defecto CON disclosure de IA proactivo (art. 50 AI Act): jamas impersona.
    saludo = texto or (
        f"Hola, le llama el asistente virtual con inteligencia artificial de {_nombre_tenant()}. "
        "Esta es una llamada de prueba del sistema Kaizen para verificar la voz. "
        "Si me oye con claridad, el sistema funciona. Gracias."
    )
    try:
        mp3 = canal.generar_audio(saludo)
    except Exception as e:
        console.print(f"[red]✗ ElevenLabs falló:[/] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/] MP3 generado: [bold]{mp3}[/]")
    console.print("[dim]Escúchalo para validar la calidad de la voz clonada.[/]")

    if solo_mp3 or not confirmar_envio_real:
        if not confirmar_envio_real:
            console.print("[yellow]ⓘ Sin --confirmar-envio-real: no se coloca ninguna llamada (R-02).[/]")
        return

    publica = os.environ.get("PUBLIC_MEDIA_BASE_URL")
    try:
        if publica:
            audio_url = f"{publica.rstrip('/')}/{mp3.name}"
            console.print(f"[dim]Twilio servirá Play sobre {audio_url}[/]")
            data = canal.colocar_llamada(a=numero, audio_url=audio_url, confirmar_envio_real=True)
        else:
            twiml = (f"<Response><Say voice=\"Polly.Conchita\" language=\"es-ES\">{saludo}</Say></Response>")
            data = canal.colocar_llamada(a=numero, twiml=twiml, confirmar_envio_real=True)
    except VozBloqueada as e:
        console.print(f"[red]✗ Bloqueado por seguridad (R-02):[/] {e}")
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]✗ Twilio falló:[/] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/] Llamada Twilio colocada · SID [bold]{data.get('sid')}[/] · estado [bold]{data.get('status')}[/]")


# ─────────────────────────────────────────────────────────────────────────────
#  Sistema nervioso — comandos de migración/operación
# ─────────────────────────────────────────────────────────────────────────────

@cli.command(name="migrar-knowledge")
@click.option("--empresa", default="laboratorio", show_default=True)
@click.option("--dry-run", is_flag=True, help="No escribe; solo reporta qué se migraría.")
def migrar_knowledge(empresa: str, dry_run: bool) -> None:
    """Migra los leads del knowledge al esquema unificado del sistema nervioso.

    Backup automático en state/knowledge.json.bak.<ts>. Idempotente. Ver
    docs/MODELO_DATOS_LEAD.md y ADR-007.
    """
    from dotenv import load_dotenv; load_dotenv()
    from pathlib import Path as _P
    from core.knowledge_migration import migrar
    # R-TENANT: misma resolución que core.knowledge.get_knowledge() — respeta
    # KAIZEN_KNOWLEDGE_PATH si está definida; si no, state/ en la raíz de datos
    # (fuera del árbol de git), nunca una ruta relativa a este fichero.
    ruta_env = os.getenv("KAIZEN_KNOWLEDGE_PATH")
    if ruta_env:
        ruta = _P(ruta_env)
    else:
        from core.rutas import dir_state
        ruta = dir_state() / "knowledge.json"
    res = migrar(knowledge_path=ruta, company=empresa, dry_run=dry_run)
    console.print(f"\n[bold cyan]Migración knowledge ({empresa})[/]")
    console.print(f"  total: {res.leads_total}")
    console.print(f"  migrados: {res.leads_migrados}")
    console.print(f"  ya al día: {res.leads_ya_al_dia}")
    console.print(f"  errores: {res.leads_con_error}")
    if res.backup_path:
        console.print(f"  backup: {res.backup_path.name}")
    if res.errores:
        console.print("[yellow]Errores:[/]")
        for e in res.errores[:5]:
            console.print(f"  · {e}")
    if dry_run:
        console.print("[dim](dry-run: no se escribió nada)[/]")


# (Corregido 2026-07-03: aqui habia un segundo @cli.group(name="comercial") que
# SOBREESCRIBIA al grupo de la linea ~276 y dejaba inalcanzables fase0/fase1/voz.
# El dashboard se registra ahora en el grupo original.)
@comercial.command(name="dashboard")
@click.option("--empresa", default="laboratorio", show_default=True)
def comercial_dashboard(empresa: str) -> None:
    """Panel de estado del departamento comercial. Vista determinista del knowledge."""
    from dotenv import load_dotenv; load_dotenv()
    from departments.comercial.dashboard_director import DashboardDirector
    from core.knowledge import get_knowledge
    from core.lead_schema import LeadDoc

    def _loader() -> list:
        leads_dict = get_knowledge().all(empresa, "lead")
        return [LeadDoc.from_dict(v) for v in leads_dict.values()
                if isinstance(v, dict) and v.get("id")]

    dash = DashboardDirector(knowledge_loader=_loader, empresa=empresa)
    dash.imprimir(console=console)


@cli.group()
def bitacora() -> None:
    """Bitacora encadenada por tenant (D00 §3.4, serie D B3)."""


@bitacora.command(name="verificar")
@click.option("--tenant", default=None, help="Id del tenant (default: KAIZEN_COMPANY).")
def bitacora_verificar(tenant: str | None) -> None:
    """Verifica la cadena de hash de la bitacora del tenant y nombra la ruptura si la hay."""
    from core.knowledge import get_knowledge
    from core.rue import Bitacora
    t = tenant or EMPRESA_DEFECTO
    v = Bitacora(get_knowledge(), t).verificar()
    if v.get("integra"):
        console.print(f"[green]INTEGRA[/] · {t} · {v['eventos']} eventos encadenados")
    else:
        console.print(f"[red]ROTA[/] · {t} · punto de ruptura: {v['punto_ruptura']} (event_id {v.get('event_id')})")
        raise SystemExit(1)


@cli.command(name="pregunta")
@click.argument("texto", nargs=-1, required=True)
@click.option("--empresa", default="laboratorio", show_default=True)
def pregunta_cmd(texto: tuple, empresa: str) -> None:
    """Consulta natural sobre los leads (NLQ).

    Ejemplos:
      kaizen pregunta "cuántos hoteles boutique en queued"
      kaizen pregunta "leads en Murcia con callback pendiente"
      kaizen pregunta "desglosa los leads por estado"
    """
    from dotenv import load_dotenv; load_dotenv()
    from core.consulta_natural import ConsultaNatural
    from core.knowledge import get_knowledge
    from core.lead_schema import LeadDoc

    pregunta = " ".join(texto).strip()
    if not pregunta:
        console.print("[red]Pregunta vacía.[/]")
        sys.exit(1)

    def _loader() -> list:
        leads_dict = get_knowledge().all(empresa, "lead")
        return [LeadDoc.from_dict(v) for v in leads_dict.values()
                if isinstance(v, dict) and v.get("id")]

    nlq = ConsultaNatural(knowledge_loader=_loader, company=empresa)
    console.print(f"[dim]Pregunta: {pregunta}[/]")
    console.print(f"[dim]Empresa : {empresa}[/]")
    console.print()
    salida = nlq.responder(pregunta)
    console.print(salida)


# ─────────────────────────────────────────────────────────────────────────────
#  OpenGravity — capa de verificación por comité (tesis §6, §7.4)
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def opengravity() -> None:
    """Verificación por comité multi-agente y salud del sistema nervioso (tesis §6, §7.4)."""


@opengravity.command(name="verificar")
@click.argument("texto", nargs=-1)
@click.option("--empresa", default="laboratorio", show_default=True)
@click.option("--dominio", default=None,
              help="legal|finanzas|brand|comercial|operaciones (si no, se infiere por keywords).")
@click.option("--modo", default=None, type=click.Choice(["preventive", "forensic"]),
              help="Si no se da, lo decide el clasificador (§6.5).")
@click.option("--tipo", "artifact_type", default=None,
              help="Tipo de artefacto del catálogo (p. ej. contrato_firmable, email_frio).")
@click.option("--pasadas", default=3, show_default=True, type=int,
              help="votingRuns: pasadas por miembro (§4.4).")
@click.option("--simular", is_flag=True,
              help="No llama al LLM: usa un comité simulado (PASS) para ver el flujo y el sellado.")
def opengravity_verificar(texto: str, empresa: str, dominio: str | None, modo: str | None,
                          artifact_type: str | None, pasadas: int, simular: bool) -> None:
    """Levanta un comité que verifica un artefacto y emite un veredicto sellado.

    Ejemplos:
      kaizen opengravity verificar "Propuesta con descuento del 10% y cláusula RGPD" --dominio comercial
      kaizen opengravity verificar "Contrato de distribución, total a pagar 5000€, firma" --tipo contrato_firmable
      kaizen opengravity verificar "campaña de lanzamiento de los rollicos" --simular
    """
    from dotenv import load_dotenv; load_dotenv()
    artifact = " ".join(texto).strip()
    if not artifact:
        console.print("[red]Falta el artefacto a verificar.[/]"); sys.exit(1)

    from core.bus import InMemoryBus
    from core.opengravity.committee import Committee
    from core.opengravity.department import OpenGravity

    chat = None
    if simular:
        import json as _json
        def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
            if "Chair" in system:
                return "Comité simulado: aprueba por consenso."
            return _json.dumps({"verdict": "PASS", "confidence": 0.92, "risk_level": "low",
                                "findings": [], "rationale": "simulación"})
    else:
        _check_budget()

    bus = InMemoryBus()
    og = OpenGravity(bus, committee=Committee(chat=chat) if simular else Committee())
    ver = og.revisar(artifact=artifact, company=empresa, domain=dominio, mode=modo,
                     artifact_type=artifact_type, emitir=True)

    color = {"PASS": "green", "FAIL": "red", "ESCALATE": "yellow"}.get(ver.verdict, "white")
    console.print(Panel.fit(
        f"[bold {color}]{ver.verdict}[/]  ·  modo [bold]{ver.mode}[/]\n"
        f"consenso {ver.consensus}  ·  confianza {ver.confidence}\n"
        f"clasificación: {ver.clasificacion['motivo']}"
        + (f"  [dim](regla {ver.clasificacion['regla_dura']})[/]" if ver.clasificacion.get('regla_dura') else "")
        + (f"\n[red]escalado: {ver.escalation_reason}[/]" if ver.escalate else "")
        + (f"\n[yellow]relajación de umbral bloqueada[/]" if ver.relajacion_bloqueada else ""),
        title=f"Veredicto del comité · {empresa}", border_style=color))

    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    tabla.add_column("rol"); tabla.add_column("verdict"); tabla.add_column("conf"); tabla.add_column("razón")
    for m in ver.payload.get("members", []):
        tabla.add_row(m["role_id"], m["verdict"], str(m["confidence"]),
                      (m.get("rationale") or "")[:60])
    console.print(tabla)
    console.print(f"[dim]síntesis del chair:[/] {ver.payload.get('chair_synthesis','')}")
    console.print(f"[dim]hash del veredicto:[/] {ver.trace['hash'][:16]}…  "
                  f"[dim]← prev[/] {ver.trace['chain_prev_hash'][:16]}…")
    if ver.bloquea and not ver.ejecutable:
        console.print("[bold red]El cubo se mantiene BLOQUEADO: no ejecuta hasta resolver.[/]")


@opengravity.command(name="panel-bus")
def opengravity_panel_bus() -> None:
    """Panel de salud del sistema nervioso y umbral de migración SQLite→Redis (tesis §7.4)."""
    from core.migracion_bus import MonitorMigracion
    panel = MonitorMigracion().panel()
    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold",
                  title="Salud del sistema nervioso · umbral de migración (estimación)")
    tabla.add_column("métrica"); tabla.add_column("valor"); tabla.add_column("umbral"); tabla.add_column("")
    for f in panel["metricas"]:
        marca = "[red]✗ cruza[/]" if f["cruza"] else "[green]ok[/]"
        tabla.add_row(f["metrica"], str(f["valor"]), str(f["umbral"]), marca)
    console.print(tabla)
    estado = ("[bold red]ABIERTA[/]" if panel["decision_abierta"] else "[green]cerrada[/]")
    console.print(f"Días consecutivos ≥2 métricas: {panel['dias_consecutivos_sobre_umbral']}/"
                  f"{panel['dias_necesarios']}  ·  decisión de migración: {estado}")
    console.print(f"[dim]{panel['nota']}[/]")


@cli.command(name="catalogo")
def catalogo_cmd() -> None:
    """Muestra los diez cubos del catálogo, su orden de construcción y estado (tesis §3, §3.11)."""
    from departments import catalogo as cat
    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold",
                  title="Catálogo de departamentos (cubos) · Kaizen")
    tabla.add_column("#"); tabla.add_column("Departamento"); tabla.add_column("Estado")
    for c in cat.info():
        color = "green" if c["estado"] == "construido" else "yellow"
        tabla.add_row(str(c["orden"]), c["titulo"], f"[{color}]{c['estado']}[/]")
    console.print(tabla)
    console.print(f"[dim]Cuadrado mínimo viable (primer producto vendible, §3.11):[/] "
                  f"{' → '.join(cat.CUADRADO_MINIMO)}")


# --- Sustrato (Bloques 1+): comandos aditivos; no tocan comandos existentes ---
try:
    from sustrato.cli import comandos_para_kaizen as _sustrato_comandos
    for _cmd in _sustrato_comandos():
        cli.add_command(_cmd)
except Exception as _exc_sustrato:  # el CLI del operador nunca debe caer por el sustrato
    print(f"[aviso] sustrato no disponible: {_exc_sustrato}", file=sys.stderr)


if __name__ == "__main__":
    cli()
