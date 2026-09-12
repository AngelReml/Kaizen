"""Departamentos especialistas LLM (Fase 5): Legal, Desarrollo, QA, Finanzas, Ops, RRHH.

Cada uno es un orquestador departamental respaldado por Claude con una persona propia.
Misma base, distinto prompt: estructura uniforme, se encienden bajo demanda. Cada uno
tiene modo simulación para validarse antes de operar de verdad.
"""
from __future__ import annotations

from departments.base import Department, Task, TaskResult

_REGLA = ("Eres el {nombre} del Sistema Operativo Empresarial. {rol} "
          "Responde en español, de forma concreta y útil. No inventes datos; si no sabes algo, dilo. "
          "Prepara el trabajo para que el humano decida; nunca ejecutes acciones irreversibles por tu cuenta.")

PERSONAS: dict[str, tuple[str, str]] = {
    "legal":      ("Departamento Legal", "Revisas contratos, cláusulas, RGPD y riesgos jurídicos."),
    "desarrollo": ("Departamento de Desarrollo", "Resuelves tareas técnicas, código e integraciones."),
    "qa":         ("Departamento de QA", "Validas calidad, revisas resultados y detectas errores."),
    "finanzas":   ("Departamento de Finanzas", "Analizas presupuesto, costes, márgenes y rentabilidad."),
    "ops":        ("Departamento de Operaciones", "Coordinas logística, proveedores, pedidos e inventario."),
    "rrhh":       ("Departamento de RRHH", "Gestionas contratación, personal y organización del equipo."),
}


class LLMDepartment(Department):
    """Departamento genérico respaldado por un LLM con persona configurable."""

    def __init__(self, bus, name: str, system_prompt: str, *,
                 simulacion: bool = False, model: str = "claude-haiku-4-5-20251001") -> None:
        super().__init__(bus)
        self.name = name
        self.system_prompt = system_prompt
        self.simulacion = simulacion
        self.model = model

    def run(self, task: Task) -> TaskResult:
        if self.simulacion:
            return TaskResult(True, f"[SIM] {self.name}: respuesta de ejemplo para '{task.intent}'.",
                              {"simulado": True})
        import claude_client as ai
        resp = ai.chat(
            [{"role": "user", "content": task.intent}],
            system=self.system_prompt, model=self.model, max_tokens=800, company=task.company,
        ).strip()
        return TaskResult(True, resp[:200], {"respuesta": resp})


def crear_departamentos(bus, *, simulacion: bool = False) -> dict[str, Department]:
    """Crea los 6 departamentos especialistas listos para registrar en el Director."""
    out: dict[str, Department] = {}
    for name, (nombre, rol) in PERSONAS.items():
        prompt = _REGLA.format(nombre=nombre, rol=rol)
        out[name] = LLMDepartment(bus, name, prompt, simulacion=simulacion)
    return out
