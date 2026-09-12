"""Composición del comité — el selector (tesis §6.3).

Reglas, en orden:
  1. Carga los roles del dominio principal desde el catálogo (§6.2).
  2. Si las keywords del artefacto cruzan otros dominios, añade sus roles sin duplicar
     (una propuesta comercial con cláusulas legales suma roles de Comercial y de Legal).
  3. Aplica el tope: máximo 5 miembros + chair. Si la unión supera 5, prioriza el dominio
     principal y descarta el resto.
  4. Añade contrarian si el dominio principal es Finanzas o Comercial (donde el sesgo de
     confirmación es el mayor riesgo). Dedup: en Finanzas ya está en el trío.
  5. El chair es siempre el modelo más fuerte del comité (lo añade el committee, no aquí).

Lógica pura y determinista: misma entrada → mismo comité.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.opengravity.role_registry import (
    DOMINIOS, Role, roles_de_dominio, keywords_de, get_role,
)

MAX_MIEMBROS = 5                       # sin contar el chair (§6.3)
CONTRARIAN_EN = {"finanzas", "comercial"}


@dataclass
class ComposicionComite:
    dominio_principal: str
    miembros: list[Role]               # sin el chair
    dominios_cruzados: list[str]
    descartados_por_tope: list[str]    # role_ids que no entraron por el tope de 5


def detectar_dominios(texto: str) -> list[str]:
    """Dominios cuyas keywords aparecen en el texto, ordenados por nº de coincidencias desc."""
    t = (texto or "").lower()
    puntuacion: dict[str, int] = {}
    for dom in DOMINIOS:
        hits = sum(1 for kw in keywords_de(dom) if kw in t)
        if hits:
            puntuacion[dom] = hits
    return sorted(puntuacion, key=lambda d: puntuacion[d], reverse=True)


def componer(artifact_text: str, *, domain: str | None = None,
             context_text: str = "") -> ComposicionComite:
    """Compone el comité para un artefacto.

    `domain` fuerza el dominio principal (lo que pide el departamento en el contrato);
    si es None, se infiere por keywords. `context_text` se añade a la detección de cruces
    pero no decide el dominio principal.
    """
    texto = f"{artifact_text}\n{context_text}"
    detectados = detectar_dominios(texto)

    principal = domain or (detectados[0] if detectados else "comercial")
    if principal not in DOMINIOS:
        principal = "comercial"

    # 1 — dominio principal
    miembros: list[Role] = list(roles_de_dominio(principal))
    vistos = {r.role_id for r in miembros}

    # 2 — cruces de otros dominios (sin duplicar), en orden de relevancia
    cruzados: list[str] = []
    for dom in detectados:
        if dom == principal:
            continue
        cruzados.append(dom)
        for r in roles_de_dominio(dom):
            if r.role_id not in vistos:
                miembros.append(r)
                vistos.add(r.role_id)

    # 4 — contrarian si el principal es finanzas/comercial (dedup)
    if principal in CONTRARIAN_EN and "contrarian" not in vistos:
        contrarian = get_role("contrarian")
        if contrarian:
            miembros.append(contrarian)
            vistos.add("contrarian")

    # 3 — tope de 5 miembros, priorizando el dominio principal.
    # El contrarian del principal nunca se descarta; se ordena el resto por cercanía al
    # dominio principal (sus roles primero) y se corta.
    def prioridad(r: Role) -> int:
        if r.domain == principal:
            return 0
        if r.role_id == "contrarian":
            return 1
        return 2

    miembros.sort(key=prioridad)
    descartados = [r.role_id for r in miembros[MAX_MIEMBROS:]]
    miembros = miembros[:MAX_MIEMBROS]

    return ComposicionComite(
        dominio_principal=principal,
        miembros=miembros,
        dominios_cruzados=cruzados,
        descartados_por_tope=descartados,
    )
