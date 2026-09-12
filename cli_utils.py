"""Utilidades para la capa CLI y agentes de Kaizen v1.

Estas funciones operan a nivel de consola y CLI.
No confundir con core/guardian.py, que es el Guardián
de seguridad del SOE (evalúa acciones, emite veredictos
al bus, capa semántica LLM).
"""
import re


def require_approval(prompt: str) -> None:
    """Pausa y exige confirmación explícita del usuario. Lanza si se cancela."""
    print(f"\n⛔  ACCIÓN IRREVERSIBLE\n   {prompt}")
    resp = input("   Confirmar [s/N]: ").strip().lower()
    if resp != "s":
        raise RuntimeError("Acción cancelada por el usuario.")


def sanitize_query(query: str) -> str:
    """Elimina caracteres peligrosos de una consulta de búsqueda."""
    return re.sub(r"[^\w\s\-.,áéíóúüñÁÉÍÓÚÜÑ]", " ", query).strip()[:200]


def max_retries() -> int:
    """Número máximo de reintentos permitidos por agente (regla del roadmap)."""
    return 2
