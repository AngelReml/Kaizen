"""Validador automático de QA (Fase 5.1).

Suscriptor del bus: cuando Redacción completa con un borrador (cuerpo presente), QA lo
valida, guarda un nodo `Validacion` y, si hay problemas, emite un evento de bloqueo visible
en el panel. La validación dura (evitar enviar basura) la fuerza el flujo de envío.
"""
from __future__ import annotations

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from departments.qa import herramientas as h


class QAValidador:
    def __init__(self, bus: MessageBus, knowledge=None) -> None:
        self.bus = bus
        self.knowledge = knowledge
        bus.subscribe(self._on_completado, types=[EventType.DEPT_TASK_COMPLETED])

    def _on_completado(self, event: Event) -> None:
        if event.source != "redaccion":
            return
        p = event.payload
        if "cuerpo" not in p:       # nada que validar (p. ej. simulación sin cuerpo)
            return
        r = h.validar_borrador(p.get("asunto", ""), p.get("cuerpo", ""))
        if self.knowledge is not None:
            self.knowledge.add(event.company, "validacion", event.id, {
                "target": event.id, "ok": r["ok"], "problemas": r["problemas"], "ts": event.ts,
            })
        if not r["ok"]:
            self.bus.publish(Event(
                EventType.GUARDIAN_BLOCKED, source="qa",
                payload={"motivo": "QA: " + "; ".join(r["problemas"]), "lead": p.get("lead")},
                company=event.company, criticality=Criticality.HIGH,
            ))
