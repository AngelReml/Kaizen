"""Especialistas del departamento de Ops (Bloque 3). Todos FUNCION (sobre la memoria)."""
from __future__ import annotations

from datetime import datetime

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.ops import herramientas as h


class _OpsBase(Especialista):
    departamento = "ops"
    clase = ClaseTarea.FUNCION

    def __init__(self, bus=None, knowledge=None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()   # backend activo (singleton)


class ConsultorDeCapacidad(_OpsBase):
    nombre = "ConsultorDeCapacidad"
    descripcion = "Lee la ocupación de capacidad de un periodo."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        fecha = input.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        cap = h.consultar_capacidad(self.knowledge, company, fecha)
        return {"ocupada_pct": cap["ocupada_pct"], "libres": cap["libre"], "capacidad": cap}


class GestorDePedidos(_OpsBase):
    nombre = "GestorDePedidos"
    descripcion = "CRUD de pedidos (crear/consultar)."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        op = input.get("operacion", "consultar")
        if op == "crear":
            d = input.get("datos_pedido", {})
            r = h.agendar_pedido(self.knowledge, company, d.get("cliente", "?"),
                                 d.get("productos", []), d.get("fecha", ""))
            return {"ok": r["ok"], "pedido": r}
        return {"ok": True, "pedido": {"pendientes": len(self.knowledge.all(company, "pedido"))}}


class AlertadorDeStock(_OpsBase):
    nombre = "AlertadorDeStock"
    descripcion = "Compara stock con mínimos de seguridad."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        faltan = h.alerta_stock(self.knowledge, company)
        return {"alertas": [f"{m['material']}: {m['stock']} (mín. {m['seguridad']})" for m in faltan]}
