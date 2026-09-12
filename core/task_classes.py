"""Clases de tarea y routing por tipo (Bloque 2).

Cada tarea de un especialista se etiqueta con una ClaseTarea; según su clase se elige el
tier de modelo (cheap/medium/heavy) o ninguno (FUNCION = lógica Python pura).
"""
from __future__ import annotations

from enum import Enum

from core.model_router import CHAIN, ModelEntry, get_cheap_model, get_heavy_model


class ClaseTarea(str, Enum):
    CLASIFICACION = "clasificacion"   # juicio binario o escala simple → modelo más barato
    EXTRACCION = "extraccion"         # sacar datos estructurados → barato
    REDACCION = "redaccion"           # texto de calidad para envío externo → medio
    RAZONAMIENTO = "razonamiento"     # análisis complejo, jurídico, estratégico → mejor disponible
    SINTETIZAR = "sintetizar"         # resumir/consolidar info ya estructurada → barato
    FUNCION = "funcion"               # lógica Python pura, sin LLM → no se instancia modelo


PRESUPUESTO_POR_CLASE: dict[ClaseTarea, str | None] = {
    ClaseTarea.CLASIFICACION: "cheap",
    ClaseTarea.EXTRACCION: "cheap",
    ClaseTarea.REDACCION: "medium",
    ClaseTarea.RAZONAMIENTO: "heavy",
    ClaseTarea.SINTETIZAR: "cheap",
    ClaseTarea.FUNCION: None,
}

# Modelos medium preferidos, por orden.
_MEDIUM_PREF = ["claude-haiku-4-5", "gpt-4o-mini", "glm-4-air", "gemini-2.0-flash", "deepseek-chat"]


def get_model_for_class(clase: ClaseTarea) -> ModelEntry | None:
    """Devuelve el ModelEntry adecuado al tier de la clase (build perezoso). None para FUNCION.

    Si la clase NO es FUNCION y no hay ningún modelo disponible (sin API keys), lanza
    RuntimeError claro en el momento de la llamada, en vez de devolver None y explotar
    luego con un error oscuro al invocar. El reintento ante fallo retriable (advance, máx. 3)
    se realiza al invocar, en Especialista._chat.
    """
    presupuesto = PRESUPUESTO_POR_CLASE[clase]
    if presupuesto is None:
        return None
    if presupuesto == "cheap":
        modelo = get_cheap_model()
    elif presupuesto == "heavy":
        modelo = get_heavy_model()
    else:  # medium
        modelo = None
        for mid in _MEDIUM_PREF:
            modelo = next((x for x in CHAIN if x.model_id == mid and x.available()), None)
            if modelo:
                break
        if modelo is None:
            modelo = get_cheap_model()
    if modelo is None:
        raise RuntimeError(
            f"No hay modelo disponible para ClaseTarea.{clase.name} "
            f"(presupuesto={presupuesto}). "
            f"Configura al menos una API key en .env. "
            f"Ver .env.example para las opciones disponibles."
        )
    return modelo
