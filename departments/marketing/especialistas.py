"""Sub-agentes del Departamento Marketing (tesis §3.3).

Estratega de contenido · Redactor · SEO/SEM · Analista.
Patrón gemelo de los especialistas de Finanzas: FUNCION (lógica pura) salvo el Redactor,
que sintetiza con LLM y degrada a un borrador heurístico si no hay red.
"""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.marketing import herramientas as h


class _MktBase(Especialista):
    departamento = "marketing"

    def __init__(self, bus=None, knowledge=None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()


class EstrategaContenido(_MktBase):
    nombre = "EstrategaContenido"
    clase = ClaseTarea.FUNCION
    descripcion = "Plan editorial a partir del posicionamiento (Brand) y objeciones (Comercial)."

    def ejecutar(self, input: dict, context: dict) -> dict:
        plan = h.planificar_contenido(
            input.get("posicionamiento") or context.get("posicionamiento", ""),
            input.get("objeciones") or context.get("objeciones", []),
            n=int(input.get("n", 5)))
        return {"plan_contenido": plan}


class Redactor(_MktBase):
    nombre = "Redactor"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Redacta la pieza de la primera idea del plan."

    def ejecutar(self, input: dict, context: dict) -> dict:
        plan = input.get("plan_contenido") or []
        if not plan:
            return {"borrador": "", "tema": ""}
        idea = plan[0]
        tema = idea.get("tema", "")
        try:
            cuerpo = self._chat(
                [{"role": "user", "content": f"Redacta una pieza breve ({idea.get('formato')}) "
                  f"sobre: {tema}. Tono de marca. Sin promesas de precio."}],
                system="Eres el Redactor del Departamento Marketing. Escribe humano, conciso, "
                       "fiel a la marca. Nada de jerga corporativa.",
                company=context.get("company", "default"))
        except Exception:  # noqa: BLE001 — sin red: borrador heurístico
            cuerpo = f"{tema}. (Borrador pendiente de redacción creativa.)"
        return {"borrador": cuerpo, "tema": tema, "formato": idea.get("formato", "post")}


class SEOSEM(_MktBase):
    nombre = "SEOSEM"
    clase = ClaseTarea.FUNCION
    descripcion = "Extrae palabras clave de la pieza para posicionamiento y paid."

    def ejecutar(self, input: dict, context: dict) -> dict:
        texto = f"{input.get('tema','')} {input.get('borrador','')}"
        return {"keywords": h.palabras_clave(texto)}


class Analista(_MktBase):
    nombre = "Analista"
    clase = ClaseTarea.FUNCION
    descripcion = "Mide alcance y conversión a inbound."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"metricas": h.metricas_alcance(self.knowledge, company)}
