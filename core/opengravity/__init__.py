"""OpenGravity — la capa de verificación por comité multi-agente (tesis §6).

El cubo QA/Verificación (§3.10): transversal a todos los departamentos, comunicado solo
por eventos. Convierte a OpenGravity de árbitro pasivo/forense en árbitro activo en tiempo
real, que certifica el NIVEL DE CONFIANZA de una decisión antes de que se ejecute (§4.2).

Piezas:
  * verdict       — forma `veredicto_v1` y validación endurecida (§6.2).
  * role_registry — 15 roles de negocio (5 dominios × 3) + 3 transversales, temperatura 0.
  * role_selector — composición del comité con tope y contrarian (§6.3).
  * mediator      — consenso/confianza ponderados, escalado determinista (§4.3).
  * vote_history  — pesos por rol (sin diferenciar hasta 10 votos, §5.2).
  * committee     — motor: N miembros en paralelo, votingRuns 3 (§4.4).
  * sealing       — hash SHA-256 encadenado por empresa (§6.3).
  * classifier    — preventivo vs forense + candado de umbrales (§6.5, §6.3).
  * department    — el contrato sobre el bus (§6.1, §6.3).
"""
from core.opengravity.verdict import (
    MemberVerdict, Verdict, RiskLevel, Finding,
    parse_and_validate, invalid_verdict, VerdictValidationError,
)
from core.opengravity.committee import Committee, CommitteeOutcome, MemberResult
from core.opengravity.mediator import mediar, Mediacion, EscalationReason
from core.opengravity.sealing import HashChain, hash_canonico
from core.opengravity.vote_history import VoteHistory
from core.opengravity.classifier import clasificar, Modo, Clasificacion
from core.opengravity.thresholds import Umbrales, resolver_umbrales, LogInmutableUmbrales
from core.opengravity.department import OpenGravity, Veredicto, solicitar_revision

__all__ = [
    "MemberVerdict", "Verdict", "RiskLevel", "Finding",
    "parse_and_validate", "invalid_verdict", "VerdictValidationError",
    "Committee", "CommitteeOutcome", "MemberResult",
    "mediar", "Mediacion", "EscalationReason",
    "HashChain", "hash_canonico", "VoteHistory",
    "clasificar", "Modo", "Clasificacion",
    "Umbrales", "resolver_umbrales", "LogInmutableUmbrales",
    "OpenGravity", "Veredicto", "solicitar_revision",
]
