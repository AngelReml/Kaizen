"""Agente de Ops (Fase 5.2). Responde sobre capacidad e inventario; reemplaza el cascarón."""
from __future__ import annotations

import unicodedata
from datetime import datetime

from departments.base import Department, Task, TaskResult
from departments.ops import herramientas as h


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class OpsDepartment(Department):
    name = "ops"

    def __init__(self, bus, knowledge=None, *, capacidad_diaria: int = 10) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()
        self.capacidad_diaria = capacidad_diaria
        from departments.base import PipelineDepartamento
        from departments.ops.especialistas import (
            ConsultorDeCapacidad, GestorDePedidos, AlertadorDeStock,
        )
        self.pipeline = PipelineDepartamento(
            [ConsultorDeCapacidad(), GestorDePedidos(), AlertadorDeStock()], "ops", bus=bus,
        )

    def _run_legacy(self, task: Task) -> TaskResult:
        respuesta, herramienta = self.responder(task.intent, task.company)
        return TaskResult(True, respuesta[:200], {"respuesta": respuesta, "herramienta": herramienta})

    def responder(self, pregunta: str, company: str) -> tuple[str, str]:
        q = _norm(pregunta)
        if "stock" in q or "materia" in q or "inventario" in q:
            faltan = h.alerta_stock(self.knowledge, company)
            if not faltan:
                return "Todo el stock está por encima del mínimo de seguridad.", "alerta_stock"
            lineas = "\n".join(f"- {m['material']}: {m['stock']} (mín. {m['seguridad']})" for m in faltan)
            return f"Materias por debajo del stock de seguridad:\n{lineas}", "alerta_stock"
        # por defecto: capacidad de hoy
        hoy = datetime.now().strftime("%Y-%m-%d")
        cap = h.consultar_capacidad(self.knowledge, company, hoy, self.capacidad_diaria)
        return (f"Capacidad de hoy ({hoy}): {cap['ocupada']}/{cap['capacidad_diaria']} "
                f"({cap['ocupada_pct']*100:.0f}% ocupada, {cap['libre']} libres).", "consultar_capacidad")
