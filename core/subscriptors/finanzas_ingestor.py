"""Ingestor de Finanzas (Fase 1.1).

Suscriptor del bus que escucha eventos COST_RECORDED y crea un nodo `Gasto` por cada uno
en la memoria de conocimiento, aislado por empresa. Categoriza por modelo (categorización
fina por departamento origen queda pendiente: el evento de coste no lleva el origen — ver
docs/DEUDA_TECNICA.md #13).
"""
from __future__ import annotations

from core.bus import MessageBus
from core.events import Event, EventType
from core.knowledge import KnowledgeStore

EUR_PER_USD = 0.92

# Categorías por modelo (categorización automática mínima).
_CATEGORIAS = {"haiku": "tareas-ligeras", "sonnet": "analisis", "opus": "analisis-profundo"}


def categoria_de_modelo(modelo: str) -> str:
    return next((c for k, c in _CATEGORIAS.items() if k in (modelo or "").lower()), "otros")


def gasto_desde_evento(event: Event) -> dict:
    """Convierte un evento COST_RECORDED en un dict Gasto."""
    p = event.payload
    usd = float(p.get("usd", 0))
    modelo = p.get("model", "?")
    return {
        "id": event.id,
        "ts": event.ts,
        "modelo": modelo,
        "usd": round(usd, 6),
        "eur": round(usd * EUR_PER_USD, 6),
        "tokens_in": int(p.get("in", 0)),
        "tokens_out": int(p.get("out", 0)),
        "accion": p.get("accion", modelo),
        "categoria": categoria_de_modelo(modelo),
        "company": event.company,
    }


class FinanzasIngestor:
    """Conecta el bus con la memoria: cada COST_RECORDED -> nodo Gasto."""

    def __init__(self, bus: MessageBus, knowledge: KnowledgeStore) -> None:
        self.knowledge = knowledge
        bus.subscribe(self._on_cost, types=[EventType.COST_RECORDED])

    def _on_cost(self, event: Event) -> None:
        gasto = gasto_desde_evento(event)
        self.knowledge.add(event.company, "gasto", event.id, gasto)
