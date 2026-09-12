"""Departamento Inteligencia de Mercado / Estrategia — cubo del catálogo (tesis §3.8).

Observa el exterior —competencia, precios, tendencias— y da al operador visión sin que
tenga que buscarla.

Contrato:
  Consume: feeds externos (registrados con `observar`), datos del Comercial
           (dept.task_completed) y conversaciones de Atención al Cliente
           (cs.churn_alert / cs.upsell_opportunity como señal de mercado).
  Produce: briefings (intel.briefing) y alertas de competencia (intel.competitor_alert).
"""
from __future__ import annotations

import unicodedata

from core.events import Event, EventType, Criticality
from departments.base import Task, TaskResult, PipelineDepartamento
from departments.cubo import CuboDepartamento
from departments.inteligencia import herramientas as h
from departments.inteligencia.especialistas import (
    MarketMonitor, TrendAnalyst, StrategicAdvisor,
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class InteligenciaDepartment(CuboDepartamento):
    name = "inteligencia_mercado"
    consume = (EventType.DEPT_TASK_COMPLETED, EventType.CS_CHURN_ALERT,
               EventType.CS_UPSELL_OPPORTUNITY)
    produce = (EventType.INTEL_BRIEFING, EventType.INTEL_COMPETITOR_ALERT)
    usar_pipeline = True

    def __init__(self, bus, company: str = "default", knowledge=None) -> None:
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()
        self.pipeline = PipelineDepartamento(
            [MarketMonitor(knowledge=self.knowledge), TrendAnalyst(knowledge=self.knowledge),
             StrategicAdvisor(knowledge=self.knowledge)],
            "inteligencia", bus=bus)
        super().__init__(bus, company)

    # ── Contrato: consumo ────────────────────────────────────────────────────
    def _registrar_suscripciones(self) -> None:
        self._suscribir(self._on_cs, [EventType.CS_CHURN_ALERT, EventType.CS_UPSELL_OPPORTUNITY])

    def _on_cs(self, event: Event) -> None:
        # Las conversaciones de CS son señal de mercado (§3.8).
        p = event.payload or {}
        tema = p.get("nombre") or p.get("motivos") or "señal de cliente"
        h.registrar_senal(self.knowledge, event.company, tipo="conversacion",
                          tema=str(tema), fuente="customer_success", relevancia=3)

    # ── Acciones del cubo ────────────────────────────────────────────────────
    def observar(self, *, tipo: str, tema: str, fuente: str = "", relevancia: int = 3,
                 detalle: str = "") -> dict:
        senal = h.registrar_senal(self.knowledge, self.company, tipo=tipo, tema=tema,
                                  fuente=fuente, relevancia=relevancia, detalle=detalle)
        if senal["tipo"] == "competidor" and senal["relevancia"] >= h.RELEVANCIA_ALERTA:
            self._producir(EventType.INTEL_COMPETITOR_ALERT,
                           {"tema": tema, "relevancia": senal["relevancia"], "fuente": fuente},
                           criticality=Criticality.HIGH)
        return senal

    def briefing(self) -> dict:
        material = h.material_briefing(self.knowledge, self.company)
        self._producir(EventType.INTEL_BRIEFING, material, criticality=Criticality.LOW)
        return material

    # ── Pipeline / respuesta por palabras clave ──────────────────────────────
    def _run_legacy(self, task: Task) -> TaskResult:
        q = _norm(task.intent)
        if "competen" in q or "competidor" in q or "rival" in q:
            a = h.alertas_competencia(self.knowledge, task.company)
            return TaskResult(True, f"{len(a)} alerta(s) de competencia.", {"alertas": a})
        if "tendencia" in q or "senal" in q or "mercado" in q:
            t = h.detectar_tendencias(self.knowledge, task.company)
            return TaskResult(True, f"{len(t)} tendencia(s) detectada(s).", {"tendencias": t})
        if "briefing" in q or "resumen" in q or "vision" in q:
            m = self.briefing()
            return TaskResult(True, f"Briefing con {m['n_senales']} señales.", {"briefing": m})
        return TaskResult(True, "Inteligencia operativa. Pídeme competencia, tendencias o briefing.")
