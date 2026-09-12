"""Eventos tipados del bus de mensajes.

El roadmap exige "eventos tipados con schema definido". Este módulo es el catálogo
canónico de tipos de evento y el modelo serializable que viaja por el bus.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class Criticality(str, Enum):
    """Criticidad de una acción. Alimenta el umbral del Director y del Guardián."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Catálogo canónico de eventos del sistema."""
    # Ciclo de vida del sistema
    SYSTEM_STARTED = "system.started"

    # Director / orquestación
    INTENT_RECEIVED = "director.intent_received"
    INTENT_ROUTED = "director.intent_routed"
    RESULT_CONSOLIDATED = "director.result_consolidated"

    # Departamentos
    DEPT_TASK_STARTED = "dept.task_started"
    DEPT_TASK_COMPLETED = "dept.task_completed"
    DEPT_TASK_FAILED = "dept.task_failed"

    # Guardián
    GUARDIAN_APPROVED = "guardian.approved"
    GUARDIAN_BLOCKED = "guardian.blocked"
    GUARDIAN_ESCALATED = "guardian.escalated"

    # Aprobación humana
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"

    # Contabilidad de coste
    COST_RECORDED = "cost.recorded"
    COST_ALERT = "cost.alert"

    # OpenGravity — capa de verificación por comité (tesis §6.3)
    # El contrato de tres eventos: el departamento solicita, OpenGravity responde,
    # y si la confianza no llega, escala al humano.
    OPENGRAVITY_REVIEW_REQUESTED = "opengravity.review_requested"
    OPENGRAVITY_REVIEW_COMPLETED = "opengravity.review_completed"
    OPENGRAVITY_ESCALATION_REQUESTED = "opengravity.escalation_requested"

    # Brand — el segundo cubo, primero en invocar comités (tesis §6.4)
    BRAND_REVIEW_REQUESTED = "brand.review_requested"
    BRAND_REVIEW_COMPLETED = "brand.review_completed"

    # Ciclo de vida de los cubos (resiliencia, tesis §7.1)
    # Un cubo se marca listo publicando esto; nunca pregunta por el estado de otro.
    CUBE_STARTED = "cube.started"

    # Salud del sistema nervioso / umbral de migración (tesis §7.4)
    # ABRE la decisión de migrar SQLite→Redis; nunca la ejecuta.
    BUS_MIGRATION_THRESHOLD_OPEN = "bus.migration_threshold_open"

    # ── Contratos inter-departamentales del catálogo (tesis §3) ──────────────
    # Marketing (§3.3): alimenta el pipeline del Comercial con inbound.
    MARKETING_LEAD_INBOUND = "marketing.lead_inbound"
    MARKETING_CONTENT_PUBLISHED = "marketing.content_published"

    # Atención al Cliente / Customer Success (§3.4): retiene y detecta churn.
    CS_CHURN_ALERT = "cs.churn_alert"
    CS_RENEWAL = "cs.renewal"
    CS_UPSELL_OPPORTUNITY = "cs.upsell_opportunity"

    # Inteligencia de Mercado / Estrategia (§3.8): visión externa.
    INTEL_BRIEFING = "intel.briefing"
    INTEL_COMPETITOR_ALERT = "intel.competitor_alert"

    # RRHH / gestión de agentes (§3.9): introspección del sistema sobre sí mismo.
    HR_CAPABILITY_MAP = "hr.capability_map"
    HR_PERFORMANCE_ALERT = "hr.performance_alert"


@dataclass
class Event:
    """Mensaje que viaja por el bus. Aislado por empresa (`company`)."""
    type: EventType
    source: str                              # departamento o componente emisor
    payload: dict = field(default_factory=dict)
    company: str = "default"                 # aislamiento estricto entre empresas
    criticality: Criticality = Criticality.LOW
    correlation_id: str | None = None        # encadena pasos de una acción compuesta
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        d = asdict(self)
        d["type"] = self.type.value
        d["criticality"] = self.criticality.value
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Event":
        d = json.loads(raw)
        return cls(
            type=EventType(d["type"]),
            source=d["source"],
            payload=d.get("payload", {}),
            company=d.get("company", "default"),
            criticality=Criticality(d.get("criticality", "low")),
            correlation_id=d.get("correlation_id"),
            id=d.get("id", uuid.uuid4().hex),
            ts=d.get("ts", datetime.now(timezone.utc).isoformat()),
        )
