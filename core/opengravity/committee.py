"""Motor del comité multi-agente (tesis §4, §6.2).

Equivalente Python del `Committee.ts` de Shinobi (436 líneas, 12 audits reales en mayo),
con los tres fixes de §4.4 ya aplicados por diseño:

  Fix 1 — temperature 0: cada miembro corre a temperatura 0 (fijado en role_registry).
  Fix 2 — votingRuns 3: cada miembro hace N pasadas y su veredicto consolidado es la
          mayoría de sus pasadas. Detecta la alucinación que una sola pasada no ve.
  Fix 3 — catálogo de roles de negocio (role_registry), no solo software.

Flujo: el selector compone el comité → cada miembro vota (N pasadas, validación endurecida
con reintento único) en paralelo → el chair sintetiza → el mediador heurístico mide
consenso/confianza → si hay zona gris, se invoca al mediador LLM.

El `chat` es inyectable (por defecto `claude_client.chat`) para tests sin red.
"""
from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from core.opengravity.role_registry import Role, CHAIR, MEDIATOR_LLM
from core.opengravity.role_selector import componer, ComposicionComite
from core.opengravity.mediator import mediar, Mediacion, EscalationReason
from core.opengravity.verdict import (
    MemberVerdict, Verdict, parse_and_validate, invalid_verdict,
    VerdictValidationError,
)

MAX_WORKERS = 5
DEFAULT_VOTING_RUNS = 3


def _neutralizar_artefacto(texto: str) -> str:
    """R-03: rompe cualquier marca de cierre de delimitador que el propio artefacto
    contenga, para que un lead malicioso no pueda 'cerrar' el bloque y colar ordenes."""
    if not texto:
        return ""
    return (texto.replace("ARTEFACTO>>>", "ARTEFACTO​>>>")
                 .replace("<<<ARTEFACTO", "<<<​ARTEFACTO"))


@dataclass
class MemberResult:
    role_id: str
    consolidado: MemberVerdict
    pasadas: list[MemberVerdict] = field(default_factory=list)   # las N pasadas crudas


@dataclass
class CommitteeOutcome:
    composicion: ComposicionComite
    members: list[MemberResult]
    mediacion: Mediacion
    chair_synthesis: str
    voting_runs: int

    def to_payload(self) -> dict:
        """Payload canónico para el evento review_completed y para el sellado (§6.3)."""
        return {
            "verdict": self.mediacion.verdict.value,
            "consensus": self.mediacion.consensus,
            "confidence": self.mediacion.confidence,
            "domain": self.composicion.dominio_principal,
            "members": [
                {
                    "role_id": m.role_id,
                    "verdict": m.consolidado.verdict.value,
                    "confidence": m.consolidado.confidence,
                    "risk_level": (m.consolidado.risk_level.value
                                   if m.consolidado.risk_level else None),
                    "valido": m.consolidado.valido,
                    "n_pasadas": len(m.pasadas),
                    "n_pasadas_validas": sum(1 for p in m.pasadas if p.valido),
                    "rationale": m.consolidado.rationale,
                }
                for m in self.members
            ],
            "divergences": self.mediacion.divergences,
            "chair_synthesis": self.chair_synthesis,
            "voting_runs": self.voting_runs,
            "escalate": self.mediacion.escalate,
            "escalation_reason": (self.mediacion.escalation_reason.value
                                  if self.mediacion.escalation_reason else None),
        }


def _consolidar(role_id: str, pasadas: list[MemberVerdict]) -> MemberVerdict:
    """Veredicto del miembro = mayoría de sus N pasadas válidas (fix votingRuns, §4.4)."""
    validas = [p for p in pasadas if p.valido]
    if not validas:
        return invalid_verdict(role_id, "todas las pasadas inválidas")
    conteo = Counter(p.verdict for p in validas)
    verdict_mayoria, _ = conteo.most_common(1)[0]
    coincidentes = [p for p in validas if p.verdict is verdict_mayoria]
    confidence = sum(p.confidence for p in coincidentes) / max(1, len(coincidentes))
    findings = [f for p in coincidentes for f in p.findings]
    divergencias = [d for p in coincidentes for d in p.divergences_from_chair]
    base = coincidentes[0]
    return MemberVerdict(
        role_id=role_id,
        verdict=verdict_mayoria,
        confidence=round(confidence, 4),
        risk_level=base.risk_level,
        findings=findings,
        rationale=base.rationale,
        divergences_from_chair=divergencias,
        valido=True,
    )


class Committee:
    def __init__(self, chat=None, *, max_workers: int = MAX_WORKERS) -> None:
        if chat is None:
            import claude_client
            chat = claude_client.chat
        self.chat = chat
        self.max_workers = max_workers

    # ── Una pasada de un miembro, con reintento controlado único (regla 5 de §6.2) ──
    def _una_pasada(self, role: Role, user: str, system: str, company: str) -> MemberVerdict:
        def _llamar(extra: str = "") -> str:
            return self.chat(
                [{"role": "user", "content": user + extra}],
                system=system, model=role.model, max_tokens=600,
                company=company, temperature=role.temperature,
            )
        try:
            return parse_and_validate(_llamar(), role.role_id)
        except VerdictValidationError as e1:
            # Reintento único, recordando el formato exacto.
            recordatorio = ("\n\nTu respuesta anterior no cumplió el formato "
                            f"({e1}). Devuelve SOLO el JSON con todos los campos obligatorios.")
            try:
                return parse_and_validate(_llamar(recordatorio), role.role_id)
            except VerdictValidationError as e2:
                return invalid_verdict(role.role_id, f"falló validación dos veces: {e2}")
        except Exception as e:  # noqa: BLE001 — fallo de red/LLM ⇒ voto inválido, no rompe el comité
            return invalid_verdict(role.role_id, f"error LLM: {e}")

    def _votar_miembro(self, role: Role, user: str, contexto_empresa: str,
                       company: str, voting_runs: int) -> MemberResult:
        system = role.render_system(contexto_empresa)
        pasadas = [self._una_pasada(role, user, system, company)
                   for _ in range(voting_runs)]
        return MemberResult(role.role_id, _consolidar(role.role_id, pasadas), pasadas)

    def _sintetizar_chair(self, user: str, members: list[MemberResult],
                          contexto_empresa: str, company: str) -> str:
        resumen = "\n".join(
            f"- {m.role_id}: {m.consolidado.verdict.value} "
            f"(confianza {m.consolidado.confidence}) — {m.consolidado.rationale}"
            for m in members if m.consolidado.valido
        ) or "(ningún voto válido)"
        prompt = (
            f"{user}\n\n=== VEREDICTOS DE LOS MIEMBROS ===\n{resumen}\n\n"
            "Sintetiza en 2-3 frases el dictamen del comité: el sentido mayoritario, las "
            "divergencias relevantes si las hay, y la recomendación. No inventes datos."
        )
        try:
            return self.chat(
                [{"role": "user", "content": prompt}],
                system=CHAIR.render_system(contexto_empresa),
                model=CHAIR.model, max_tokens=400,
                company=company, temperature=CHAIR.temperature,
            ).strip()
        except Exception as e:  # noqa: BLE001
            return f"(síntesis del chair no disponible: {e})"

    def _romper_zona_gris(self, user: str, members: list[MemberResult],
                          contexto_empresa: str, company: str) -> Verdict | None:
        """Invoca al mediador LLM solo en zona gris (§6.2). Devuelve su verdict o None."""
        resumen = "\n".join(
            f"- {m.role_id}: {m.consolidado.verdict.value} — {m.consolidado.rationale}"
            for m in members if m.consolidado.valido)
        prompt = (
            f"{user}\n\n=== VOTOS EN CONFLICTO (empate) ===\n{resumen}\n\n"
            "El mediador heurístico no resuelve. Decide el verdict más defendible: "
            'responde SOLO una palabra: PASS, FAIL o ESCALATE.')
        try:
            raw = self.chat(
                [{"role": "user", "content": prompt}],
                system=MEDIATOR_LLM.render_system(contexto_empresa),
                model=MEDIATOR_LLM.model, max_tokens=10,
                company=company, temperature=MEDIATOR_LLM.temperature,
            ).strip().upper()
        except Exception:  # noqa: BLE001
            return None
        for v in (Verdict.PASS, Verdict.FAIL, Verdict.ESCALATE):
            if v.value in raw:
                return v
        return None

    # ── Punto de entrada ───────────────────────────────────────────────────────
    def run(self, *, artifact: str, company: str, domain: str | None = None,
            context: str = "", contexto_empresa: str = "",
            voting_runs: int = DEFAULT_VOTING_RUNS,
            consensus_min: float = 0.66, confidence_min: float = 0.70,
            quorum_min: int = 3,
            pesos: dict[str, float] | None = None) -> CommitteeOutcome:
        comp = componer(artifact, domain=domain, context_text=context)
        # R-03: el artefacto se entrega DELIMITADO y neutralizado (las marcas de cierre que
        # pudiera contener se rompen) para que jamas se lea como instruccion del sistema.
        artefacto_seguro = _neutralizar_artefacto(artifact)
        user = (f"<<<ARTEFACTO\n{artefacto_seguro}\nARTEFACTO>>>\n"
                + (f"\n=== CONTEXTO ===\n{_neutralizar_artefacto(context)}\n" if context else ""))

        # Miembros en paralelo (cada uno hace `voting_runs` pasadas).
        with ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(comp.miembros)))) as ex:
            members = list(ex.map(
                lambda r: self._votar_miembro(r, user, contexto_empresa, company, voting_runs),
                comp.miembros))

        votos = [m.consolidado for m in members]
        med = mediar(votos, pesos, consensus_min=consensus_min, confidence_min=confidence_min,
                     quorum_min=quorum_min)

        # Zona gris → mediador LLM rompe el empate.
        if med.needs_mediator_llm:
            decision = self._romper_zona_gris(user, members, contexto_empresa, company)
            if decision is not None:
                # Re-evalúa escalado con el verdict del mediador, conservando consenso/confianza.
                med.verdict = decision
                if decision is Verdict.ESCALATE:
                    med.escalate = True
                    med.escalation_reason = med.escalation_reason or EscalationReason.LOW_CONSENSUS
                med.divergences.append(f"mediator_llm rompió zona gris → {decision.value}")

        chair = self._sintetizar_chair(user, members, contexto_empresa, company)
        return CommitteeOutcome(comp, members, med, chair, voting_runs)
