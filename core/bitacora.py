"""Diario de bitácora del sistema (Capa 2, pieza de logging de Fase 1).

Suscriptor del bus que registra cada evento de forma append-only, aislado por empresa.
En fases posteriores la bitácora pasará a ser una vista-resumen sobre el grafo Neo4j;
de momento es el log funcional de eventos que exige la Fase 1.
"""
from __future__ import annotations

from pathlib import Path

from core.bus import MessageBus
from core.events import Event

def _bitacora_dir() -> Path:
    """R-TENANT: la bitacora es DATO, vive en la raiz de datos."""
    from core.rutas import dir_bitacora
    return dir_bitacora()


def log_event(event: Event) -> None:
    """Append de un evento a la bitácora de su empresa."""
    base = _bitacora_dir()
    base.mkdir(parents=True, exist_ok=True)
    line = f"{event.ts}  [{event.type.value}]  {event.source}  {event.payload}\n"
    with (base / f"{event.company}.log").open("a", encoding="utf-8") as f:
        f.write(line)


def attach(bus: MessageBus) -> None:
    """Conecta la bitácora al bus: registrará todos los eventos que circulen."""
    bus.subscribe(log_event)
