"""Departamento de Prospección.

Reutiliza el agente de prospección de Kaizen (agentes.prospectar) como sub-agente
ejecutor. El executor es inyectable para poder probar el flujo sin coste ni red.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Callable

from ddgs import DDGS

from departments.base import Department, Task, TaskResult, Especialista, PipelineDepartamento
from core.task_classes import ClaseTarea
from cli_utils import sanitize_query

# Sectores para el simulador contextual: (keywords sin acentos, leads de ejemplo).
_SECTORES: dict[str, tuple[tuple[str, ...], list[str]]] = {
    "alimentacion": (
        ("aliment", "reposter", "gourmet", "hosteler", "pasteler", "panader",
         "cafeter", "restaurant", "cocina", "delicatessen"),
        ["Hotel Boutique Demo", "Tienda Gourmet Ejemplo S.L."],
    ),
    "software": (
        ("software", "tecnolog", "saas", "app ", "digital", "informatic", "startup"),
        ["Startup Tech Demo", "Consultora Digital Ejemplo S.L."],
    ),
}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class ProspeccionDepartment(Department):
    name = "prospeccion"

    def __init__(self, bus, executor: Callable[[str, str], TaskResult] | None = None,
                 *, simulacion: bool = False) -> None:
        super().__init__(bus)
        self.simulacion = simulacion
        if executor is None:
            executor = self._sim_executor if simulacion else self._real_executor
        self._executor = executor
        self.pipeline = PipelineDepartamento(
            [Buscador(), ExtractorDeContacto(), ClasificadorDeFit(), GeneradorDeFicha()],
            "prospeccion", bus=bus, simulacion=simulacion,
        )

    def _run_legacy(self, task: Task) -> TaskResult:
        perfil = task.payload.get("perfil") or task.intent
        return self._executor(perfil, task.company)

    @staticmethod
    def _real_executor(perfil: str, company: str) -> TaskResult:
        """Sub-agente real: ejecuta la búsqueda y guarda fichas en el Diario de la empresa."""
        import agentes
        creadas = agentes.prospectar(perfil, company) or []
        return TaskResult(True, f"Prospección ejecutada para '{perfil}'.",
                          {"perfil": perfil, "leads": creadas})

    @staticmethod
    def _sim_executor(perfil: str, company: str) -> TaskResult:
        """Simulación contextual: detecta el sector en CONTEXTO_NEGOCIO (por keywords, sin
        LLM) y devuelve leads coherentes. Sin red ni coste; no contamina el Diario real."""
        import diario_ops as diario
        ctx = _norm(diario.read("CONTEXTO_NEGOCIO", company))
        for sector, (kws, leads) in _SECTORES.items():
            if any(k in ctx for k in kws):
                return TaskResult(
                    True, f"[SIM] {len(leads)} leads de ejemplo (sector {sector}) para '{perfil}'.",
                    {"perfil": perfil, "simulado": True, "sector": sector, "leads": leads},
                )
        return TaskResult(
            True,
            "[SIM] Sin contexto sectorial detectado en CONTEXTO_NEGOCIO.md; no se generan leads de ejemplo.",
            {"perfil": perfil, "simulado": True, "leads": []},
        )


# ─────────────────────────────────────────────────────────────
#  Especialistas del departamento (Bloque 3)
# ─────────────────────────────────────────────────────────────


class Buscador(Especialista):
    nombre = "Buscador"
    departamento = "prospeccion"
    clase = ClaseTarea.FUNCION
    descripcion = "Busca candidatos en la web (ddgs)."

    def ejecutar(self, input: dict, context: dict) -> dict:
        perfil = sanitize_query(input.get("perfil") or context.get("intent", ""))
        queries = [perfil]
        resultados_raw: list[dict] = []
        for q in queries:
            try:
                resultados_raw.extend(list(DDGS().text(q, max_results=6)))
            except Exception as e:  # red/rate-limit: best-effort, pero no silencioso
                import sys
                print(f"[prospeccion.Buscador] búsqueda '{q}' falló: {e}", file=sys.stderr)
        return {"queries": queries, "resultados_raw": resultados_raw}


class ExtractorDeContacto(Especialista):
    nombre = "ExtractorDeContacto"
    departamento = "prospeccion"
    clase = ClaseTarea.FUNCION
    descripcion = "Scrapea URLs y extrae emails/teléfonos."

    def ejecutar(self, input: dict, context: dict) -> dict:
        import agentes
        contactos = []
        vistas: set[str] = set()
        for r in input.get("resultados_raw", [])[:12]:
            url = r.get("href", "")
            if not url.startswith("http") or url in vistas:
                continue
            vistas.add(url)
            texto = agentes._fetch_page(url)
            contactos.append({"url": url, "titulo": r.get("title", ""),
                              "emails": agentes._extract_emails(texto),
                              "telefonos": agentes._extract_phones(texto),
                              "texto_pagina": texto[:800]})
        return {"contactos": contactos}


class ClasificadorDeFit(Especialista):
    nombre = "ClasificadorDeFit"
    departamento = "prospeccion"
    clase = ClaseTarea.CLASIFICACION
    descripcion = "Asigna fit Alta/Media/Baja a cada candidato."

    def ejecutar(self, input: dict, context: dict) -> dict:
        texto = self._chat(
            [{"role": "user", "content": f"Perfil: {context.get('intent','')}\nCandidatos: {input.get('contactos', [])}"}],
            system="Clasifica cada candidato con fit Alta/Media/Baja y una frase de razón.",
            company=context.get("company", "default"),
        )
        return {"candidatos_clasificados": texto}


class GeneradorDeFicha(Especialista):
    nombre = "GeneradorDeFicha"
    departamento = "prospeccion"
    clase = ClaseTarea.EXTRACCION
    descripcion = "Genera la ficha estructurada en Markdown para el Diario."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = context.get("company", "default")
        texto = self._chat(
            [{"role": "user", "content": f"Candidatos: {input.get('candidatos_clasificados', '')}"}],
            system="Genera una ficha Markdown por candidato (### Nombre + bullets).",
            company=company,
        )
        import agentes
        import diario_ops
        creadas = []
        for nombre, cuerpo in agentes._split_fichas(texto):
            slug = agentes._slug(nombre)
            if not slug or diario_ops.read_cliente(slug, company):
                continue
            diario_ops.write_cliente(slug, f"# {nombre}\n\n{cuerpo}\n", company)
            creadas.append(slug)
        return {"fichas_md": texto, "fichas_creadas": creadas}
