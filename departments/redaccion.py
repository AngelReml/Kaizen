"""Departamento de Redacción (Ventas/Marketing de salida).

Recibe un lead y genera un borrador de primer contacto. NO envía: el envío es una
acción irreversible que pasa por el Guardián y aprobación humana. Reutiliza el núcleo
no interactivo del agente de redacción de Kaizen.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from departments.base import Department, Task, TaskResult, Especialista, PipelineDepartamento
from core.task_classes import ClaseTarea


def _norm(texto: str) -> str:
    """Minúsculas sin acentos, para emparejar el lead de forma robusta."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class RedaccionDepartment(Department):
    name = "redaccion"

    def __init__(self, bus, executor: Callable[[str, str], TaskResult] | None = None,
                 *, simulacion: bool = False) -> None:
        super().__init__(bus)
        self.simulacion = simulacion
        if executor is None:
            executor = self._sim_executor if simulacion else self._real_executor
        self._executor = executor
        self.pipeline = PipelineDepartamento(
            [AnalistaDePerfil(), RedactorDeCuerpo(), GeneradorDeAsunto(), ValidadorDeFormato()],
            "redaccion", bus=bus, simulacion=simulacion,
        )

    def _run_legacy(self, task: Task) -> TaskResult:
        # El lead puede venir explícito (handoff de Prospección) o haber que deducirlo
        # de la orden en lenguaje natural ("redacta un correo para Cliente B").
        lead = task.payload.get("lead") or self._resolver_lead(task.intent, task.company)
        if lead is None:
            import diario_ops as diario
            disponibles = [c for c in diario.list_clientes(task.company)
                           if not c.startswith("prospeccion_")]
            if disponibles:
                return TaskResult(False, "¿A qué lead redacto? Indícalo en la orden. "
                                  "Leads en el Diario: " + ", ".join(disponibles[:12]))
            return TaskResult(False, "No hay fichas de leads en el Diario todavía. Prospecta primero.")
        return self._executor(lead, task.company)

    @staticmethod
    def _resolver_lead(intent: str, company: str) -> str | None:
        """Deduce qué ficha del Diario menciona la orden. Compara el texto (sin acentos)
        contra los slugs de clientes y sus variantes (con espacios / sin separadores).
        Devuelve el slug más específico que aparezca, o None si ninguno encaja."""
        import diario_ops as diario
        objetivo = _norm(intent)
        objetivo_compacto = objetivo.replace(" ", "")
        mejor: str | None = None
        for slug in diario.list_clientes(company):
            if slug.startswith("prospeccion_"):     # lotes de prospección, no leads individuales
                continue
            base = _norm(slug)
            for forma in (base, base.replace("_", " "), base.replace("_", "")):
                if forma and (forma in objetivo or forma.replace(" ", "") in objetivo_compacto):
                    if mejor is None or len(slug) > len(mejor):
                        mejor = slug
                    break
        return mejor

    @staticmethod
    def _real_executor(lead: str, company: str) -> TaskResult:
        import agentes
        borrador = agentes.generar_borrador(lead, company)
        if borrador is None:
            return TaskResult(False, f"No hay ficha para '{lead}'.")
        return TaskResult(True, f"Borrador listo para '{lead}'.", {"lead": lead, **borrador})

    @staticmethod
    def _sim_executor(lead: str, company: str) -> TaskResult:
        return TaskResult(
            True, f"[SIM] Borrador de primer contacto para '{lead}'.",
            {"lead": lead, "asunto": f"Presentación comercial · {lead}", "simulado": True},
        )


# ─────────────────────────────────────────────────────────────
#  Especialistas del departamento (Bloque 3)
# ─────────────────────────────────────────────────────────────


class AnalistaDePerfil(Especialista):
    nombre = "AnalistaDePerfil"
    departamento = "redaccion"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Extrae los 3 argumentos de conexión lead-empresa más fuertes."

    def ejecutar(self, input: dict, context: dict) -> dict:
        texto = self._chat(
            [{"role": "user", "content": f"Lead: {input.get('ficha_lead','')}\nEmpresa: {input.get('contexto_empresa','')}"}],
            system="Devuelve los 3 argumentos de conexión más fuertes, uno por línea.",
            company=context.get("company", "default"),
        )
        argumentos = [l.strip("-• ").strip() for l in texto.splitlines() if l.strip()][:3]
        return {"argumentos": argumentos}


class RedactorDeCuerpo(Especialista):
    nombre = "RedactorDeCuerpo"
    departamento = "redaccion"
    clase = ClaseTarea.REDACCION
    descripcion = "Escribe el cuerpo del email."

    def ejecutar(self, input: dict, context: dict) -> dict:
        cuerpo = self._chat(
            [{"role": "user", "content": f"Argumentos: {input.get('argumentos',[])}\n"
                                          f"Lead: {input.get('ficha_lead','')}\n"
                                          f"Remitente: {input.get('identidad_remitente','')}"}],
            system="Escribe el cuerpo de un primer email comercial, sobrio, máx 150 palabras, con firma.",
            company=context.get("company", "default"),
        )
        return {"cuerpo": cuerpo}


class GeneradorDeAsunto(Especialista):
    nombre = "GeneradorDeAsunto"
    departamento = "redaccion"
    clase = ClaseTarea.CLASIFICACION
    descripcion = "Genera el asunto (máx. 8 palabras)."

    def ejecutar(self, input: dict, context: dict) -> dict:
        asunto = self._chat(
            [{"role": "user", "content": f"Cuerpo:\n{input.get('cuerpo','')}"}],
            system="Genera un asunto de email de máximo 8 palabras. Solo el asunto.",
            company=context.get("company", "default"),
        ).strip()
        return {"asunto": asunto}


class ValidadorDeFormato(Especialista):
    nombre = "ValidadorDeFormato"
    departamento = "redaccion"
    clase = ClaseTarea.FUNCION
    descripcion = "Verifica asunto, ausencia de placeholders, firma y longitud."

    def ejecutar(self, input: dict, context: dict) -> dict:
        asunto, cuerpo = input.get("asunto", ""), input.get("cuerpo", "")
        remitente = input.get("identidad_remitente") or context.get("identidad_remitente") or {}
        nombre_rem = remitente.get("nombre", "") if isinstance(remitente, dict) else ""
        problemas = []
        if not asunto.strip():
            problemas.append("sin asunto")
        if re.search(r"\[[^\]]+\]", f"{asunto} {cuerpo}") or re.search(r"\b(TODO|INSERTAR|XXX)\b", f"{asunto} {cuerpo}"):
            problemas.append("contiene placeholders")
        n = len(cuerpo.split())
        if not (50 <= n <= 200):
            problemas.append(f"longitud {n} palabras fuera de [50, 200]")
        if nombre_rem and nombre_rem not in cuerpo:   # solo si hay remitente configurado
            problemas.append("el cuerpo no contiene el nombre del remitente")
        return {"ok": not problemas, "problemas": problemas}
