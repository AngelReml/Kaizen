"""El departamento OpenGravity — el contrato sobre el bus (tesis §6.1, §6.3, §3.10).

OpenGravity es un cubo más —el de QA/Verificación— y se comunica con el resto SOLO por
eventos. Ninguna llamada es directa. El contrato define tres eventos (§6.3):

  opengravity.review_requested   Departamento → OpenGravity
      decision_id, mode (preventive/forensic), domain, artifact, context, thresholds, timeout
  opengravity.review_completed   OpenGravity → Departamento
      verdict, consensus, confidence, members, divergences, chair_synthesis,
      trace (hash + chain_prev_hash)
  opengravity.escalation_requested  OpenGravity → operador
      reason (low_consensus/low_confidence/validation_failed/timeout), summary,
      recommended_action

El mismo motor de comité sirve para los dos modos (§6.1); lo único que cambia es si el
caller bloquea (preventivo: `revisar()` devuelve el veredicto) o no (forense: el caller
publica el evento y sigue, el veredicto llega después por review_completed).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from core.empresa import cargar_perfil_empresa
from core.opengravity.committee import Committee, CommitteeOutcome
from core.opengravity.classifier import clasificar, Modo, Clasificacion
from core.opengravity.thresholds import (
    Umbrales, resolver_umbrales, DEFAULT_CONSENSO, DEFAULT_CONFIANZA,
)
from core.opengravity.vote_history import VoteHistory
from core.opengravity.sealing import HashChain

_RAIZ = Path(__file__).resolve().parent.parent.parent


@dataclass
class Veredicto:
    """Resultado completo de una revisión. Es el payload de review_completed más metadatos."""
    decision_id: str
    company: str
    mode: str                          # preventive | forensic
    verdict: str                       # PASS | FAIL | ESCALATE
    consensus: float
    confidence: float
    escalate: bool
    escalation_reason: str | None
    payload: dict = field(default_factory=dict)     # outcome.to_payload()
    trace: dict = field(default_factory=dict)       # {hash, chain_prev_hash}
    clasificacion: dict = field(default_factory=dict)
    relajacion_bloqueada: bool = False

    @property
    def bloquea(self) -> bool:
        return self.mode == Modo.PREVENTIVO.value

    @property
    def ejecutable(self) -> bool:
        """¿El cubo puede ejecutar el artefacto? En preventivo, solo si PASS sin escalar."""
        if self.mode == Modo.FORENSE.value:
            return True                              # forense ejecuta de inmediato
        return self.verdict == "PASS" and not self.escalate


def _empresa_floor(company: str) -> Umbrales:
    """Umbrales mínimos de empresa. Configurables en empresas/<company>/opengravity.json."""
    from core.rutas import dir_empresa
    ruta = dir_empresa(company) / "opengravity.json"
    cons, conf = DEFAULT_CONSENSO, DEFAULT_CONFIANZA
    if ruta.exists():
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
            cons = float(d.get("consensus_min", cons))
            conf = float(d.get("confidence_min", conf))
        except Exception:  # noqa: BLE001
            pass
    return Umbrales(cons, conf)


class OpenGravity:
    """El cubo de verificación. Se suscribe a review_requested y ofrece `revisar()` síncrono
    para callers preventivos que necesitan bloquear."""

    name = "opengravity"

    def __init__(self, bus: MessageBus, *, committee: Committee | None = None,
                 vote_history: VoteHistory | None = None, chain: HashChain | None = None,
                 suscribir: bool = True, contexto_loader=None) -> None:
        self.bus = bus
        self.committee = committee or Committee()
        self.votes = vote_history or VoteHistory()
        self.chain = chain or HashChain()
        self._contexto_loader = contexto_loader
        if suscribir:
            bus.subscribe(self._on_review_requested,
                          types=[EventType.OPENGRAVITY_REVIEW_REQUESTED])

    # ── Contexto de empresa (sin acoplar a diario_ops si se inyecta) ──────────
    def _contexto_empresa(self, company: str) -> str:
        if self._contexto_loader is not None:
            return self._contexto_loader(company)
        try:
            import diario_ops
            return diario_ops.read("CONTEXTO_NEGOCIO", company) or ""
        except Exception:  # noqa: BLE001
            return ""

    # ── Revisión síncrona (preventivo bloquea aquí; forense también la usa) ───
    def revisar(self, *, artifact: str, company: str, decision_id: str | None = None,
                mode: str | None = None, domain: str | None = None,
                artifact_type: str | None = None, context: str = "",
                thresholds: dict | None = None, emitir: bool = True,
                correlation_id: str | None = None, voting_runs: int = 3) -> Veredicto:
        decision_id = decision_id or uuid.uuid4().hex
        perfil = cargar_perfil_empresa(company)
        sector = perfil.get("sector", "")

        # Clasificación preventivo/forense (si el caller no fija el modo).
        clasif: Clasificacion = clasificar(
            artifact_type=artifact_type, artifact_text=f"{artifact}\n{context}",
            domain=domain, sector=sector,
            override_firmado=bool((thresholds or {}).get("override_firmado")),
        )
        modo = Modo(mode) if mode in (Modo.PREVENTIVO.value, Modo.FORENSE.value) else clasif.modo

        # Candado de umbrales (§6.3): el departamento solo puede endurecer.
        floor = _empresa_floor(company)
        solicitud = None
        if thresholds:
            try:
                solicitud = Umbrales(
                    float(thresholds.get("consensus_min", floor.consensus_min)),
                    float(thresholds.get("confidence_min", floor.confidence_min)))
            except (TypeError, ValueError):
                solicitud = None
        resol = resolver_umbrales(floor, solicitud)

        # Pesos por rol (vote_history; neutros hasta diferenciar).
        contexto = self._contexto_empresa(company)
        outcome: CommitteeOutcome = self.committee.run(
            artifact=artifact, company=company, domain=domain,
            context=context, contexto_empresa=contexto,
            consensus_min=resol.efectivos.consensus_min,
            confidence_min=resol.efectivos.confidence_min,
            voting_runs=voting_runs,
            pesos=self._pesos(company, artifact, context),
        )

        # Sellado con hash encadenado por empresa (§6.3).
        payload = outcome.to_payload()
        payload["decision_id"] = decision_id
        payload["mode"] = modo.value
        trace = self.chain.sellar(company, payload)

        ver = Veredicto(
            decision_id=decision_id, company=company, mode=modo.value,
            verdict=outcome.mediacion.verdict.value,
            consensus=outcome.mediacion.consensus,
            confidence=outcome.mediacion.confidence,
            escalate=outcome.mediacion.escalate,
            escalation_reason=(outcome.mediacion.escalation_reason.value
                               if outcome.mediacion.escalation_reason else None),
            payload=payload, trace=trace,
            clasificacion={"modo": modo.value, "motivo": clasif.motivo,
                           "regla_dura": clasif.regla_dura},
            relajacion_bloqueada=resol.relajacion_bloqueada,
        )

        if emitir:
            self._emitir_completado(ver, correlation_id)
            if ver.escalate:
                self._emitir_escalado(ver, outcome, correlation_id)
        return ver

    def _pesos(self, company: str, artifact: str, context: str) -> dict[str, float]:
        # Pesos de todos los role_ids que podrían entrar; el mediador solo usa los presentes.
        from core.opengravity.role_registry import ROLE_REGISTRY
        return {rid: self.votes.peso(company, rid) for rid in ROLE_REGISTRY}

    # ── Emisión de eventos del contrato ──────────────────────────────────────
    def _emitir_completado(self, ver: Veredicto, correlation_id: str | None) -> None:
        self.bus.publish(Event(
            EventType.OPENGRAVITY_REVIEW_COMPLETED, source=self.name,
            payload={**ver.payload, "trace": ver.trace,
                     "clasificacion": ver.clasificacion,
                     "relajacion_bloqueada": ver.relajacion_bloqueada},
            company=ver.company, correlation_id=correlation_id,
            criticality=Criticality.HIGH if ver.bloquea else Criticality.MEDIUM,
        ))

    def _emitir_escalado(self, ver: Veredicto, outcome: CommitteeOutcome,
                         correlation_id: str | None) -> None:
        recomendacion = ("Revisar manualmente y resolver antes de ejecutar."
                         if ver.bloquea else "Auditar a posteriori; el artefacto ya salió.")
        self.bus.publish(Event(
            EventType.OPENGRAVITY_ESCALATION_REQUESTED, source=self.name,
            payload={
                "decision_id": ver.decision_id,
                "reason": ver.escalation_reason,
                "summary": outcome.chair_synthesis,
                "divergences": outcome.mediacion.divergences,
                "consensus": ver.consensus, "confidence": ver.confidence,
                "recommended_action": recomendacion,
                "mode": ver.mode,
            },
            company=ver.company, correlation_id=correlation_id,
            criticality=Criticality.CRITICAL,
        ))

    # ── Handler del evento review_requested (forense fire-and-forget) ─────────
    def _on_review_requested(self, event: Event) -> None:
        p = event.payload or {}
        artifact = p.get("artifact", "")
        if not artifact:
            return
        self.revisar(
            artifact=artifact, company=event.company,
            decision_id=p.get("decision_id"), mode=p.get("mode"),
            domain=p.get("domain"), artifact_type=p.get("artifact_type"),
            context=p.get("context", ""), thresholds=p.get("thresholds"),
            correlation_id=event.correlation_id, emitir=True,
        )


def solicitar_revision(bus: MessageBus, *, artifact: str, company: str,
                       mode: str = Modo.FORENSE.value, domain: str | None = None,
                       artifact_type: str | None = None, context: str = "",
                       thresholds: dict | None = None,
                       correlation_id: str | None = None) -> str:
    """Helper para que un departamento publique opengravity.review_requested y siga (forense).
    Devuelve el decision_id para correlacionar el review_completed que llegará después.
    """
    decision_id = uuid.uuid4().hex
    bus.publish(Event(
        EventType.OPENGRAVITY_REVIEW_REQUESTED, source=domain or "departamento",
        payload={"decision_id": decision_id, "mode": mode, "domain": domain,
                 "artifact": artifact, "artifact_type": artifact_type,
                 "context": context, "thresholds": thresholds or {}},
        company=company, correlation_id=correlation_id, criticality=Criticality.MEDIUM,
    ))
    return decision_id
