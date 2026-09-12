"""Departamento Marketing / Contenido — cubo del catálogo (tesis §3.3).

Genera demanda, construye presencia, atrae leads inbound para alimentar al Comercial.

Contrato:
  Consume: posicionamiento del Brand (brand.review_completed) y objeciones reales del
           Comercial (dept.task_completed con objeciones en payload).
  Produce: leads inbound (marketing.lead_inbound), contenido publicado
           (marketing.content_published) y métricas de alcance (en la respuesta).
"""
from __future__ import annotations

import unicodedata

from core.events import Event, EventType, Criticality
from departments.base import Task, TaskResult, PipelineDepartamento
from departments.cubo import CuboDepartamento
from departments.marketing import herramientas as h
from departments.marketing.especialistas import (
    EstrategaContenido, Redactor, SEOSEM, Analista,
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class MarketingDepartment(CuboDepartamento):
    name = "marketing"
    consume = (EventType.BRAND_REVIEW_COMPLETED, EventType.DEPT_TASK_COMPLETED)
    produce = (EventType.MARKETING_LEAD_INBOUND, EventType.MARKETING_CONTENT_PUBLISHED)
    usar_pipeline = True

    def __init__(self, bus, company: str = "default", knowledge=None) -> None:
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()
        self._posicionamiento = ""
        self._objeciones: list[str] = []
        self.pipeline = PipelineDepartamento(
            [EstrategaContenido(knowledge=self.knowledge), Redactor(knowledge=self.knowledge),
             SEOSEM(knowledge=self.knowledge), Analista(knowledge=self.knowledge)],
            "marketing", bus=bus)
        super().__init__(bus, company)

    # ── Contrato: consumo ────────────────────────────────────────────────────
    def _registrar_suscripciones(self) -> None:
        self._suscribir(self._on_brand, [EventType.BRAND_REVIEW_COMPLETED])
        self._suscribir(self._on_comercial, [EventType.DEPT_TASK_COMPLETED])

    def _on_brand(self, event: Event) -> None:
        # El posicionamiento aprobado por Brand alimenta el plan editorial.
        p = event.payload or {}
        if p.get("aprobado"):
            self._posicionamiento = p.get("asunto") or self._posicionamiento

    def _on_comercial(self, event: Event) -> None:
        if event.source == "comercial":
            objs = (event.payload or {}).get("objeciones")
            if objs:
                self._objeciones = list(objs)

    # ── Acciones del cubo ────────────────────────────────────────────────────
    def publicar_pieza(self, *, tema: str, formato: str = "post", canal: str = "blog",
                       cuerpo: str = "") -> dict:
        pieza = h.registrar_pieza(self.knowledge, self.company, tema=tema, formato=formato,
                                  canal=canal, cuerpo=cuerpo, estado="publicada")
        self._producir(EventType.MARKETING_CONTENT_PUBLISHED,
                       {"pieza_id": pieza["id"], "tema": tema, "canal": canal,
                        "keywords": pieza["keywords"]})
        return pieza

    def captar_inbound(self, *, nombre: str, canal: str, origen_pieza: str | None = None,
                       contacto: dict | None = None) -> dict:
        lead = h.registrar_lead_inbound(self.knowledge, self.company, nombre=nombre,
                                        canal=canal, origen_pieza=origen_pieza, contacto=contacto)
        # El lead inbound alimenta el pipeline del Comercial (§3.3).
        self._producir(EventType.MARKETING_LEAD_INBOUND,
                       {"lead_id": lead["id"], "nombre": nombre, "canal": canal,
                        "origen_pieza": origen_pieza}, criticality=Criticality.MEDIUM)
        return lead

    def plan(self, *, n: int = 5) -> list[dict]:
        return h.planificar_contenido(self._posicionamiento, self._objeciones, n=n)

    # ── Pipeline / respuesta por palabras clave ──────────────────────────────
    def _run_con_pipeline(self, task: Task) -> TaskResult:
        task.payload.setdefault("posicionamiento", self._posicionamiento)
        task.payload.setdefault("objeciones", self._objeciones)
        return super()._run_con_pipeline(task)

    def _run_legacy(self, task: Task) -> TaskResult:
        q = _norm(task.intent)
        if "plan" in q or "calendario" in q or "editorial" in q:
            plan = self.plan()
            return TaskResult(True, f"Plan editorial con {len(plan)} ideas.", {"plan": plan})
        if "alcance" in q or "metric" in q or "rendimiento" in q:
            m = h.metricas_alcance(self.knowledge, task.company)
            return TaskResult(True, f"{m['piezas_publicadas']} piezas · "
                              f"{m['leads_inbound']} leads inbound.", {"metricas": m})
        return TaskResult(True, "Marketing operativo. Pídeme un plan o métricas de alcance.",
                          {"posicionamiento": self._posicionamiento})
