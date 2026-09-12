"""Reglas duras de Legal (Fase 5.3). Funciones puras (pasa: bool, motivo: str)."""
from __future__ import annotations

from core.guardian import Action, Decision

TOPE_CONTRATO_EUR = 10_000          # contratos por encima requieren revisión humana
MAX_MESES_NO_COMPETENCIA = 24       # no competencia > 2 años se escala


def contrato_supera_tope(importe_anual_eur: float, tope: float = TOPE_CONTRATO_EUR) -> tuple[bool, str]:
    if importe_anual_eur > tope:
        return False, f"Contrato de {importe_anual_eur:.0f}€/año supera el tope ({tope:.0f}€); requiere revisión humana"
    return True, "ok"


def responsabilidad_ilimitada(texto: str) -> tuple[bool, str]:
    t = (texto or "").lower()
    if "responsabilidad ilimitada" in t or "sin limite de responsabilidad" in t:
        return False, "Cláusula de responsabilidad ilimitada: bloqueada automáticamente"
    return True, "ok"


def no_competencia_larga(meses: int, max_meses: int = MAX_MESES_NO_COMPETENCIA) -> tuple[bool, str]:
    if meses > max_meses:
        return False, f"No competencia de {meses} meses (> {max_meses}); se escala a revisión humana"
    return True, "ok"


def como_regla_guardian(action: Action) -> tuple[Decision, str]:
    """Inyectable en el Guardián central (departamento -> core, sentido correcto)."""
    p = action.payload
    if "clausula_texto" in p:
        ok, motivo = responsabilidad_ilimitada(p["clausula_texto"])
        if not ok:
            return Decision.BLOCKED, motivo                 # responsabilidad ilimitada: bloqueo duro
    if "contrato_importe_eur" in p:
        ok, motivo = contrato_supera_tope(float(p["contrato_importe_eur"]))
        if not ok:
            return Decision.ESCALATED, motivo               # contrato caro: revisión humana
    if "no_competencia_meses" in p:
        ok, motivo = no_competencia_larga(int(p["no_competencia_meses"]))
        if not ok:
            return Decision.ESCALATED, motivo
    return Decision.APPROVED, "ok"
