"""Departamento Atención al Cliente / Customer Success — cubo del catálogo (tesis §3.4).

Cuida al cliente tras la venta. Retener vale más que captar. Detecta oportunidades de
crecimiento.

Contrato:
  Consume: historial de clientes del Comercial (dept.task_completed), tono del Brand
           (brand.review_completed), contratos del Legal (legal.contract_validated si
           existe; se ignora con elegancia si Legal está apagado).
  Produce: alertas de churn (cs.churn_alert), renovaciones (cs.renewal), oportunidades de
           upselling (cs.upsell_opportunity).
"""
from __future__ import annotations

import unicodedata

from core.events import Event, EventType, Criticality
from departments.base import Task, TaskResult, PipelineDepartamento
from departments.cubo import CuboDepartamento
from departments.customer_success import herramientas as h
from departments.customer_success.especialistas import (
    SupportAgent, CustomerSuccessManager, ChurnDetector,
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class CustomerSuccessDepartment(CuboDepartamento):
    name = "customer_success"
    consume = (EventType.DEPT_TASK_COMPLETED, EventType.BRAND_REVIEW_COMPLETED)
    produce = (EventType.CS_CHURN_ALERT, EventType.CS_RENEWAL, EventType.CS_UPSELL_OPPORTUNITY)
    usar_pipeline = True

    def __init__(self, bus, company: str = "default", knowledge=None) -> None:
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()
        self._tono_marca = "cálido, profesional, sobrio"
        self.pipeline = PipelineDepartamento(
            [ChurnDetector(knowledge=self.knowledge),
             CustomerSuccessManager(knowledge=self.knowledge),
             SupportAgent(knowledge=self.knowledge)],
            "customer_success", bus=bus)
        super().__init__(bus, company)

    # ── Contrato: consumo ────────────────────────────────────────────────────
    def _registrar_suscripciones(self) -> None:
        self._suscribir(self._on_comercial, [EventType.DEPT_TASK_COMPLETED])
        self._suscribir(self._on_brand, [EventType.BRAND_REVIEW_COMPLETED])

    def _on_comercial(self, event: Event) -> None:
        # Un cliente que el Comercial cierra entra en la cartera de CS.
        if event.source == "comercial":
            p = event.payload or {}
            cliente = p.get("cliente_nuevo")
            if cliente:
                h.alta_cliente(self.knowledge, event.company,
                               nombre=cliente.get("nombre", "?"),
                               valor_mensual=cliente.get("valor_mensual", 0.0))

    def _on_brand(self, event: Event) -> None:
        detalle = (event.payload or {}).get("detalle_llm")
        if detalle:
            self._tono_marca = "según guía de marca"

    # ── Acciones del cubo ────────────────────────────────────────────────────
    def barrido_churn(self) -> list[dict]:
        """Detecta clientes en riesgo y emite una alerta por cada uno (§3.4)."""
        riesgo = h.detectar_churn(self.knowledge, self.company)
        for r in riesgo:
            self._producir(EventType.CS_CHURN_ALERT, r, criticality=Criticality.HIGH)
        return riesgo

    def renovar(self, cliente_id: str) -> dict | None:
        ficha = h.registrar_renovacion(self.knowledge, self.company, cliente_id)
        if ficha:
            self._producir(EventType.CS_RENEWAL,
                           {"cliente_id": cliente_id, "renovaciones": ficha["renovaciones"]},
                           criticality=Criticality.MEDIUM)
        return ficha

    def barrido_upsell(self) -> list[dict]:
        ops = h.detectar_upsell(self.knowledge, self.company)
        for o in ops:
            self._producir(EventType.CS_UPSELL_OPPORTUNITY, o, criticality=Criticality.MEDIUM)
        return ops

    # ── Pipeline / respuesta por palabras clave ──────────────────────────────
    def _run_con_pipeline(self, task: Task) -> TaskResult:
        task.payload.setdefault("tono_marca", self._tono_marca)
        return super()._run_con_pipeline(task)

    def _run_legacy(self, task: Task) -> TaskResult:
        q = _norm(task.intent)
        if "churn" in q or "abandon" in q or "riesgo" in q or "fuga" in q:
            r = self.barrido_churn()
            return TaskResult(True, f"{len(r)} cliente(s) en riesgo de churn.", {"en_riesgo": r})
        if "upsell" in q or "crecer" in q or "ampliar" in q:
            o = self.barrido_upsell()
            return TaskResult(True, f"{len(o)} oportunidad(es) de upsell.", {"upsell": o})
        if "salud" in q or "cartera" in q or "estado" in q:
            s = h.salud_cartera(self.knowledge, task.company)
            return TaskResult(True, f"{s['clientes_activos']} activos · {s['en_riesgo']} en riesgo.",
                              {"salud": s})
        return TaskResult(True, "Customer Success operativo. Pídeme churn, upsell o salud de cartera.")
