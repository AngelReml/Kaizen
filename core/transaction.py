"""Acciones compuestas transaccionales con compensación (Fase 4).

Una transacción es una secuencia de pasos. Antes de ejecutar cada paso, el Guardián
lo evalúa. Si veta un paso (BLOCKED o ESCALATED no concedido), la transacción compensa
los pasos ya ejecutados en orden inverso. Los pasos sin compensación posible se marcan
como parcialmente ejecutados y se escalan al humano.

"Las acciones externas son transaccionales: se ejecutan completas o se compensan."
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from core.guardian import Guardian, Action, Decision


@dataclass
class Step:
    name: str
    action: Action                              # lo que evalúa el Guardián
    do: Callable[[], None]                       # ejecuta el paso
    compensate: Callable[[], None] | None = None  # deshace el paso (si es posible)


@dataclass
class TxResult:
    ok: bool
    vetado_en: str | None = None
    ejecutados: list[str] = field(default_factory=list)
    compensados: list[str] = field(default_factory=list)
    sin_compensar: list[str] = field(default_factory=list)   # escalados al humano


class Transaction:
    def __init__(self, bus: MessageBus, guardian: Guardian, steps: Sequence[Step],
                 *, company: str = "default", correlation_id: str | None = None) -> None:
        self.bus = bus
        self.guardian = guardian
        self.steps = list(steps)
        self.company = company
        self.correlation_id = correlation_id

    def execute(self) -> TxResult:
        ejecutados: list[Step] = []
        for step in self.steps:
            verdict = self.guardian.evaluate(step.action)
            if verdict.decision is not Decision.APPROVED:
                compensados, sin_comp = self._compensar(ejecutados)
                etype = EventType.GUARDIAN_ESCALATED if sin_comp else EventType.GUARDIAN_BLOCKED
                self._emit(etype, {
                    "transaccion": "vetada", "vetado_en": step.name, "motivo": verdict.reason,
                    "compensados": compensados, "sin_compensar": sin_comp,
                }, Criticality.HIGH)
                return TxResult(False, step.name, [s.name for s in ejecutados], compensados, sin_comp)
            step.do()
            ejecutados.append(step)

        self._emit(EventType.RESULT_CONSOLIDATED,
                   {"transaccion": "completa", "pasos": [s.name for s in ejecutados]})
        return TxResult(True, None, [s.name for s in ejecutados])

    def _compensar(self, ejecutados: list[Step]) -> tuple[list[str], list[str]]:
        compensados: list[str] = []
        sin_comp: list[str] = []
        for step in reversed(ejecutados):       # compensación en orden inverso
            if step.compensate is not None:
                step.compensate()
                compensados.append(step.name)
            else:
                sin_comp.append(step.name)       # no compensable -> escala a humano
        return compensados, sin_comp

    def _emit(self, etype: EventType, payload: dict, crit: Criticality = Criticality.LOW) -> None:
        self.bus.publish(Event(
            etype, source="transaccion", payload=payload,
            company=self.company, correlation_id=self.correlation_id, criticality=crit,
        ))
