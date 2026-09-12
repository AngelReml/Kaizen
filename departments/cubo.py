"""Base común de los departamentos del catálogo como CUBOS (tesis §2.1, §7.1).

Une la plantilla de departamento existente (`Department`: ciclo de vida de tarea + pipeline
de especialistas) con las semánticas de cubo de la tesis:

  * Contrato declarado: cada cubo declara qué eventos CONSUME y qué eventos PRODUCE
    (§2.2), no con qué cubos habla.
  * Sin dependencia de arranque (§7.1): al construirse, el cubo registra sus suscripciones
    y se marca listo publicando `cube.started`. Nunca pregunta por el estado de otro cubo.
  * Comunicación solo por eventos: el helper `_producir` publica un evento de salida del
    contrato; los consumidores reaccionan si están activos y les interesa.

Los departamentos ya existentes (Comercial, Finanzas, Legal, Ops, QA) siguen usando
`Department` directamente; los nuevos del catálogo (Marketing, Customer Success,
Inteligencia, RRHH) heredan de aquí para cumplir el contrato de cubo sin reescribir nada.
"""
from __future__ import annotations

from collections.abc import Iterable

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from departments.base import Department


class CuboDepartamento(Department):
    """Departamento con contrato de cubo. Subclasear y declarar `name`, `consume`, `produce`."""

    consume: tuple[EventType, ...] = ()
    produce: tuple[EventType, ...] = ()

    def __init__(self, bus: MessageBus, company: str = "default") -> None:
        super().__init__(bus)
        self.company = company
        self._ready = False
        self._registrar_suscripciones()
        self._marcar_listo()

    # Las subclases sobreescriben para suscribirse a sus eventos de consumo.
    # NUNCA deben referenciar otros cubos por nombre (criterio fuerte de §7.1).
    def _registrar_suscripciones(self) -> None:
        ...

    def _suscribir(self, handler, tipos: Iterable[EventType]) -> None:
        self.bus.subscribe(handler, types=list(tipos))

    def _marcar_listo(self) -> None:
        if self._ready:
            return
        self.bus.publish(Event(
            EventType.CUBE_STARTED, source=self.name,
            payload={"cube": self.name, "empresa": self.company,
                     "consume": [t.value for t in self.consume],
                     "produce": [t.value for t in self.produce]},
            company=self.company, criticality=Criticality.LOW,
        ))
        self._ready = True

    def _producir(self, etype: EventType, payload: dict, *,
                  criticality: Criticality = Criticality.LOW,
                  correlation_id: str | None = None) -> Event:
        """Publica un evento de salida del contrato. Solo se permiten los tipos declarados
        en `produce` (disciplina del contrato; un assert barato evita fugas silenciosas)."""
        assert etype in self.produce, (
            f"{self.name} intentó producir {etype.value}, no declarado en su contrato produce")
        ev = Event(etype, source=self.name, payload=payload, company=self.company,
                   criticality=criticality, correlation_id=correlation_id)
        self.bus.publish(ev)
        return ev

    @property
    def listo(self) -> bool:
        return self._ready
