"""Sub-agentes de Customer Success (tesis §3.4).

Support Agent · Customer Success Manager · Churn Detector.
"""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.customer_success import herramientas as h


class _CsBase(Especialista):
    departamento = "customer_success"

    def __init__(self, bus=None, knowledge=None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()


class SupportAgent(_CsBase):
    nombre = "SupportAgent"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Resuelve incidencias con tono de marca; degrada a acuse si no hay red."

    def ejecutar(self, input: dict, context: dict) -> dict:
        asunto = input.get("asunto", "")
        if not asunto:
            return {"respuesta_soporte": ""}
        tono = context.get("tono_marca", "cálido, profesional, sobrio")
        try:
            resp = self._chat(
                [{"role": "user", "content": f"Incidencia del cliente: {asunto}. "
                  "Responde con una solución o el siguiente paso, breve."}],
                system=f"Eres el Support Agent. Tono: {tono}. Resuelve, no enrolles.",
                company=context.get("company", "default"))
        except Exception:  # noqa: BLE001
            resp = f"Recibido: «{asunto}». Lo revisamos y te respondemos enseguida."
        return {"respuesta_soporte": resp}


class CustomerSuccessManager(_CsBase):
    nombre = "CustomerSuccessManager"
    clase = ClaseTarea.FUNCION
    descripcion = "Acompaña el ciclo de vida; detecta oportunidades de upsell."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"upsell": h.detectar_upsell(self.knowledge, company),
                "salud": h.salud_cartera(self.knowledge, company)}


class ChurnDetector(_CsBase):
    nombre = "ChurnDetector"
    clase = ClaseTarea.FUNCION
    descripcion = "Detecta señales de abandono antes de que ocurran."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"en_riesgo": h.detectar_churn(self.knowledge, company)}
