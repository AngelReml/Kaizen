"""Herramientas de QA (Fase 5.1). Deterministas, sin LLM."""
from __future__ import annotations

from departments.qa import reglas

# Pares (rasgo_del_contexto, rasgo_contradictorio_en_texto).
PARES_CONTRADICTORIOS = [
    ("artesan", "industrial"),
    ("local", "multinacional"),
    ("pequeñ", "gran cadena"),
    ("sin aditivos", "conservantes"),
]


def detectar_contradicciones(texto: str, contexto_empresa: str) -> dict:
    """Heurística por keywords: el texto afirma algo que choca con el contexto."""
    t, c = (texto or "").lower(), (contexto_empresa or "").lower()
    contradicciones = []
    for rasgo, opuesto in PARES_CONTRADICTORIOS:
        if rasgo in c and opuesto in t:
            contradicciones.append(f"el contexto dice '{rasgo}' pero el texto dice '{opuesto}'")
    return {"ok": not contradicciones, "contradicciones": contradicciones}


def validar_borrador(asunto: str, cuerpo: str, contexto: str = "") -> dict:
    """Aplica todas las reglas de QA a un borrador. Devuelve {ok, problemas[]}."""
    problemas: list[str] = []
    for ok, motivo in (
        reglas.correo_sin_asunto(asunto),
        reglas.cuerpo_demasiado_corto(cuerpo),
        reglas.contiene_placeholders(f"{asunto} {cuerpo}"),
    ):
        if not ok:
            problemas.append(motivo)
    if contexto:
        problemas += detectar_contradicciones(cuerpo, contexto)["contradicciones"]
    return {"ok": not problemas, "problemas": problemas}


def comparar_con_plantilla(texto: str, requeridos: list[str]) -> dict:
    """Comprueba que el texto contiene los elementos requeridos por la plantilla."""
    faltan = [r for r in requeridos if r.lower() not in (texto or "").lower()]
    return {"coincide_estructura": not faltan, "diferencias": faltan}
