"""Sub-agentes de Inteligencia de Mercado (tesis §3.8).

Market Monitor · Trend Analyst · Strategic Advisor.
"""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.inteligencia import herramientas as h


class _IntBase(Especialista):
    departamento = "inteligencia"

    def __init__(self, bus=None, knowledge=None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()


class MarketMonitor(_IntBase):
    nombre = "MarketMonitor"
    clase = ClaseTarea.FUNCION
    descripcion = "Rastrea competidores y movimientos del sector (agrega señales)."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"alertas_competencia": h.alertas_competencia(self.knowledge, company)}


class TrendAnalyst(_IntBase):
    nombre = "TrendAnalyst"
    clase = ClaseTarea.FUNCION
    descripcion = "Detecta señales débiles antes de que sean obvias."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"tendencias": h.detectar_tendencias(self.knowledge, company)}


class StrategicAdvisor(_IntBase):
    nombre = "StrategicAdvisor"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Sintetiza señales y tendencias en recomendaciones accionables."

    def ejecutar(self, input: dict, context: dict) -> dict:
        alertas = input.get("alertas_competencia", [])
        tendencias = input.get("tendencias", [])
        if not alertas and not tendencias:
            return {"briefing": "Sin señales relevantes en la ventana actual.",
                    "recomendaciones": []}
        resumen = ("Competencia: " + "; ".join(a["tema"] for a in alertas[:5]) +
                   " | Tendencias: " + "; ".join(f"{t['tema']} (x{t['repeticiones']})"
                                                  for t in tendencias[:5]))
        try:
            texto = self._chat(
                [{"role": "user", "content": f"Señales del mercado:\n{resumen}\n\n"
                  "Da 2-3 recomendaciones accionables y concretas para el operador."}],
                system="Eres el Strategic Advisor. Sé concreto y accionable, sin relleno.",
                company=context.get("company", "default"))
        except Exception:  # noqa: BLE001
            texto = f"Briefing: {resumen}. (Recomendaciones pendientes de síntesis.)"
        return {"briefing": resumen, "recomendaciones_llm": texto}
