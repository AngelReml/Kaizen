"""Reglas duras de QA (Fase 5.1). Funciones puras (pasa: bool, motivo: str)."""
from __future__ import annotations

import re


def correo_sin_asunto(asunto: str) -> tuple[bool, str]:
    if not asunto or not asunto.strip():
        return False, "El correo no tiene asunto."
    return True, "ok"


def cuerpo_demasiado_corto(cuerpo: str, min_palabras: int = 30) -> tuple[bool, str]:
    n = len((cuerpo or "").split())
    if n < min_palabras:
        return False, f"El cuerpo tiene {n} palabras (mínimo {min_palabras}); probablemente vacío."
    return True, "ok"


def contiene_placeholders(texto: str) -> tuple[bool, str]:
    """Detecta marcadores sin rellenar SIN falsos positivos con el 'todo' español."""
    t = texto or ""
    problemas = []
    if re.search(r"\[[^\]]+\]", t):                       # [nombre], [empresa]...
        problemas.append("corchetes sin rellenar [...]")
    if re.search(r"\b(TODO|INSERTAR|XXX|FIXME|PENDIENTE)\b", t):   # marcadores en mayúsculas
        problemas.append("marcador de plantilla (TODO/INSERTAR/XXX)")
    if "lorem ipsum" in t.lower():
        problemas.append("texto lorem ipsum")
    if problemas:
        return False, "; ".join(problemas)
    return True, "ok"
