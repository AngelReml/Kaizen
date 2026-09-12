"""Mediador del comité (tesis §4.3, §6.2).

`mediator.ts` en Shinobi es un mediador heurístico determinista (sin LLM): vota por peso
y riesgo. El flag de mediador-LLM existía pero ningún caller lo invocaba. Esta tesis lo
activa SOLO en zonas grises donde el heurístico no resuelve (`needs_mediator_llm`).

El mediador mide tres cosas (§4.2):
  * nivel de consenso del comité (porcentaje ponderado),
  * puntos de divergencia identificados entre los miembros,
  * confianza de la decisión final, ponderada por historial de cada rol (vote_history).

Si el consenso o la confianza están por debajo del umbral, NO ejecuta: marca escalado al
operador con la razón concreta. Lógica pura y determinista.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.opengravity.verdict import MemberVerdict, Verdict


class EscalationReason(str, Enum):
    LOW_CONSENSUS = "low_consensus"
    LOW_CONFIDENCE = "low_confidence"
    VALIDATION_FAILED = "validation_failed"
    NO_QUORUM = "no_quorum"
    TIMEOUT = "timeout"


# Zona gris: si los dos veredictos más votados están a menos de esto en peso, el
# heurístico no resuelve y se pide al mediador LLM (§6.2).
EPSILON_ZONA_GRIS = 1e-6


@dataclass
class Mediacion:
    verdict: Verdict                       # PASS | FAIL | ESCALATE
    consensus: float                       # [0, 1] — fracción ponderada que apoya el verdict ganador
    confidence: float                      # [0, 1] — confianza media ponderada del comité
    divergences: list[str] = field(default_factory=list)
    needs_mediator_llm: bool = False
    escalate: bool = False
    escalation_reason: EscalationReason | None = None
    n_validos: int = 0
    n_invalidos: int = 0
    tally: dict = field(default_factory=dict)   # verdict.value -> peso acumulado


def mediar(votos: list[MemberVerdict],
           pesos: dict[str, float] | None = None,
           *,
           consensus_min: float = 0.66,
           confidence_min: float = 0.70,
           quorum_min: int = 0) -> Mediacion:
    """Media los votos del comité. `pesos` mapea role_id → peso (vote_history); por defecto
    todos 1.0. `consensus_min`/`confidence_min` vienen del contrato por empresa/departamento.

    R-14 (auditoria 2026-07-20): `quorum_min` es el numero minimo de votos VALIDOS para que
    la decision sea vinculante. Bajo caida parcial de LLM (p. ej. 4 de 5 fallan y 1 devuelve
    PASS) el consenso salia 1.0 y la accion se volvia ejecutable con un solo votante. Con
    quorum, si no hay suficientes votos validos → ESCALATE (no PASS silencioso).
    """
    pesos = pesos or {}
    validos = [v for v in votos if v.valido]
    invalidos = [v for v in votos if not v.valido]

    if not validos:
        return Mediacion(
            verdict=Verdict.ESCALATE, consensus=0.0, confidence=0.0,
            escalate=True, escalation_reason=EscalationReason.VALIDATION_FAILED,
            n_validos=0, n_invalidos=len(invalidos),
            divergences=[f"{v.role_id}: {v.motivo_invalidez}" for v in invalidos],
        )

    if quorum_min and len(validos) < quorum_min:
        return Mediacion(
            verdict=Verdict.ESCALATE, consensus=0.0,
            confidence=round(sum(v.confidence for v in validos) / len(validos), 4),
            escalate=True, escalation_reason=EscalationReason.NO_QUORUM,
            n_validos=len(validos), n_invalidos=len(invalidos),
            divergences=([f"quorum insuficiente: {len(validos)} voto(s) valido(s) < "
                          f"minimo {quorum_min}"]
                         + [f"{v.role_id} descartado: {v.motivo_invalidez}" for v in invalidos]),
        )

    # Tally ponderado por verdict.
    tally: dict[str, float] = {}
    peso_total = 0.0
    for v in validos:
        w = pesos.get(v.role_id, 1.0)
        peso_total += w
        tally[v.verdict.value] = tally.get(v.verdict.value, 0.0) + w

    # Verdict ganador y consenso.
    ordenados = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
    ganador_str, peso_ganador = ordenados[0]
    verdict_ganador = Verdict(ganador_str)
    consensus = peso_ganador / peso_total if peso_total else 0.0

    # Zona gris: empate (o casi) entre los dos más votados.
    needs_llm = (len(ordenados) >= 2
                 and abs(ordenados[0][1] - ordenados[1][1]) <= EPSILON_ZONA_GRIS)

    # Confianza: media de confidence ponderada por peso de rol.
    confidence = sum(v.confidence * pesos.get(v.role_id, 1.0) for v in validos) / peso_total

    # Divergencias: miembros cuyo verdict difiere del ganador, con su razón.
    divergences: list[str] = []
    for v in validos:
        if v.verdict is not verdict_ganador:
            divergences.append(f"{v.role_id} → {v.verdict.value}: {v.rationale}".strip())
    # Divergencias explícitas declaradas por cada miembro frente al chair.
    for v in validos:
        for d in v.divergences_from_chair:
            if d:
                divergences.append(f"{v.role_id} (vs chair): {d}")
    # Votos descartados también se reportan, sin contar en el consenso.
    for v in invalidos:
        divergences.append(f"{v.role_id} descartado: {v.motivo_invalidez}")

    # Decisión de escalado.
    escalate = False
    reason: EscalationReason | None = None
    final_verdict = verdict_ganador

    if verdict_ganador is Verdict.ESCALATE:
        escalate = True
        # razón principal según qué umbral falla más
        reason = (EscalationReason.LOW_CONFIDENCE if confidence < confidence_min
                  else EscalationReason.LOW_CONSENSUS)
    elif consensus < consensus_min:
        escalate, reason, final_verdict = True, EscalationReason.LOW_CONSENSUS, Verdict.ESCALATE
    elif confidence < confidence_min:
        escalate, reason, final_verdict = True, EscalationReason.LOW_CONFIDENCE, Verdict.ESCALATE

    return Mediacion(
        verdict=final_verdict,
        consensus=round(consensus, 4),
        confidence=round(confidence, 4),
        divergences=divergences,
        needs_mediator_llm=needs_llm,
        escalate=escalate,
        escalation_reason=reason,
        n_validos=len(validos),
        n_invalidos=len(invalidos),
        tally={k: round(v, 4) for k, v in tally.items()},
    )
