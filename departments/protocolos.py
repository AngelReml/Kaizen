"""Protocolos automáticos interdepartamentales (Fase 3).

Reglas que reaccionan a eventos del bus para encadenar departamentos SIN que el
Director intervenga. El Director solo enruta la intención inicial; a partir de ahí,
los departamentos se coordinan solos por el bus.
"""
from __future__ import annotations

from core.bus import MessageBus
from core.events import Event, EventType
from departments.base import Department, Task


class ProspeccionARedaccion:
    """Cuando Prospección completa y devuelve leads, dispara Redacción para cada uno.

    Es un suscriptor del bus: no hay Director de por medio. Solo reacciona a las
    finalizaciones de 'prospeccion', así que las de 'redaccion' no lo retroalimentan
    (no hay bucle infinito).
    """

    def __init__(self, bus: MessageBus, redaccion: Department) -> None:
        self.bus = bus
        self.redaccion = redaccion
        bus.subscribe(self._on_event, types=[EventType.DEPT_TASK_COMPLETED])

    def _on_event(self, event: Event) -> None:
        if event.source != "prospeccion":
            return
        for lead in event.payload.get("leads") or []:
            self.redaccion.handle(Task(
                intent=f"redacta primer contacto para {lead}",
                payload={"lead": lead},
                company=event.company,
                correlation_id=event.correlation_id,
            ))
