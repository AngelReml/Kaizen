"""Forma común del veredicto del comité (`veredicto_v1`) y su validación endurecida.

Tesis §6.2: cada miembro del comité devuelve un objeto estructurado y validado. La
validación que cierra el bug del `risk_level` vacío (§4.4) aplica cinco reglas:

  1. schema check del JSON (campos presentes, tipos correctos),
  2. enum check de `verdict` y `risk_level` con rechazo explícito de cadena vacía,
  3. `findings` no vacío si el `verdict` no es PASS,
  4. `confidence` en rango [0, 1],
  5. un reintento controlado único que, si vuelve a fallar, marca el voto como
     INVALID_VERDICT y lo descarta del cómputo de consenso —ni a favor ni en contra.

Este módulo es lógica pura (sin LLM): el reintento lo orquesta `committee.py`, que
llama a `parse_and_validate` dos veces como máximo por miembro.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"
    INVALID = "INVALID_VERDICT"   # voto descartado del consenso (regla 5)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_SEVERIDADES = {"info", "warn", "block"}


@dataclass
class Finding:
    severity: str            # info | warn | block
    text: str

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(severity=str(d.get("severity", "info")).strip().lower(),
                   text=str(d.get("text", "")).strip())


@dataclass
class MemberVerdict:
    """Veredicto de un miembro del comité (`veredicto_v1`).

    Cuando la validación falla dos veces, se construye con `verdict=INVALID_VERDICT`
    y `valido=False`; el mediador lo excluye del cómputo de consenso.
    """
    role_id: str
    verdict: Verdict = Verdict.INVALID
    confidence: float = 0.0                       # [0, 1]
    risk_level: RiskLevel | None = None           # nunca cadena vacía
    findings: list[Finding] = field(default_factory=list)
    rationale: str = ""                           # una frase
    divergences_from_chair: list[str] = field(default_factory=list)
    valido: bool = True
    motivo_invalidez: str = ""                    # por qué se descartó, si aplica

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["risk_level"] = self.risk_level.value if self.risk_level else None
        return d


class VerdictValidationError(ValueError):
    """La carga no cumple el contrato `veredicto_v1`. Dispara el reintento único."""


def _extraer_json(raw: str) -> dict:
    """Tolera que el LLM envuelva el JSON en texto o en una valla de markdown."""
    if isinstance(raw, dict):
        return raw
    texto = (raw or "").strip()
    if not texto:
        raise VerdictValidationError("respuesta vacía")
    m = re.search(r"\{[\s\S]*\}", texto)
    if not m:
        raise VerdictValidationError("no se encontró objeto JSON en la respuesta")
    try:
        data = json.loads(m.group(0))
    except Exception as e:  # noqa: BLE001
        raise VerdictValidationError(f"JSON inválido: {e}") from e
    if not isinstance(data, dict):
        raise VerdictValidationError("el JSON no es un objeto")
    return data


def parse_and_validate(raw: str | dict, role_id: str) -> MemberVerdict:
    """Aplica las cinco reglas. Lanza `VerdictValidationError` si algo falla;
    el llamador (committee.py) decide reintentar o descartar."""
    data = _extraer_json(raw)

    # Regla 2 — enum de verdict, rechazo de cadena vacía.
    verdict_raw = str(data.get("verdict", "")).strip().upper()
    if not verdict_raw:
        raise VerdictValidationError("verdict vacío")
    try:
        verdict = Verdict(verdict_raw)
    except ValueError:
        raise VerdictValidationError(f"verdict fuera de enum: '{verdict_raw}'")
    if verdict is Verdict.INVALID:
        raise VerdictValidationError("verdict no puede declararse INVALID_VERDICT por el miembro")

    # Regla 2 — enum de risk_level, rechazo explícito de cadena vacía (el bug de §4.4).
    risk_raw = data.get("risk_level", None)
    risk_str = str(risk_raw).strip().lower() if risk_raw is not None else ""
    if risk_str == "":
        raise VerdictValidationError("risk_level vacío (cadena vacía rechazada)")
    try:
        risk = RiskLevel(risk_str)
    except ValueError:
        raise VerdictValidationError(f"risk_level fuera de enum: '{risk_str}'")

    # Regla 4 — confidence en [0, 1].
    try:
        confidence = float(data.get("confidence", None))
    except (TypeError, ValueError):
        raise VerdictValidationError("confidence no numérico")
    if not (0.0 <= confidence <= 1.0):
        raise VerdictValidationError(f"confidence fuera de [0,1]: {confidence}")

    # findings con severidad válida.
    findings: list[Finding] = []
    for f in data.get("findings", []) or []:
        if not isinstance(f, dict):
            raise VerdictValidationError("finding no es objeto")
        finding = Finding.from_dict(f)
        if finding.severity not in _SEVERIDADES:
            raise VerdictValidationError(f"severidad inválida: '{finding.severity}'")
        findings.append(finding)

    # Regla 3 — findings no vacío si verdict no es PASS.
    if verdict is not Verdict.PASS and not findings:
        raise VerdictValidationError(f"verdict {verdict.value} exige al menos un finding")

    return MemberVerdict(
        role_id=role_id,
        verdict=verdict,
        confidence=confidence,
        risk_level=risk,
        findings=findings,
        rationale=str(data.get("rationale", "")).strip(),
        divergences_from_chair=[str(x) for x in (data.get("divergences_from_chair", []) or [])],
        valido=True,
    )


def invalid_verdict(role_id: str, motivo: str) -> MemberVerdict:
    """Construye el voto descartado de la regla 5 (tras fallar el reintento único)."""
    return MemberVerdict(
        role_id=role_id,
        verdict=Verdict.INVALID,
        valido=False,
        motivo_invalidez=motivo,
    )
