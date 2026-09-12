"""Sin dependencia de arranque (tesis §7.1).

Propiedad a garantizar: encender un cubo cualquiera sin que existan otros cubos no produce
fallo. El operador puede arrancar Legal solo, o Brand solo, o cualquier combinación, y cada
cubo se inicializa, registra sus suscripciones, expone sus servicios y opera con los
consumidores presentes —cero, en el caso límite— sin lanzar excepción ni consumir CPU en
bucles de espera.

El criterio fuerte (§7.1): un cubo no menciona a otros cubos por nombre en su arranque. Si
Legal cita a Comercial en su inicialización hay acoplamiento por nombre. El desacoplamiento
debe ser total: un cubo conoce eventos, no conoce cubos.

Las tres reglas de diseño:
  1. Imports: un cubo nunca importa código de otro cubo. Lo compartido vive en core/.
  2. Configuración: la config de un cubo declara qué eventos consume y produce, no con qué
     cubos habla. La lista de cubos activos por empresa la lee el ORQUESTADOR, no el cubo.
  3. Inicialización: cargar config, registrar sub-agentes, suscribirse por tipo de evento,
     declarar qué emitirá, y marcarse ready publicando cube.started. En toda la secuencia,
     el cubo nunca pregunta por el estado de otro cubo. Cero health-checks tipo "¿está Y?".
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import combinations

from core.bus import MessageBus
from core.events import Event, EventType, Criticality

# Catálogo de los diez cubos (§3). Solo NOMBRES — ningún cubo importa a otro.
CUBOS_CATALOGO = (
    "comercial", "brand", "marketing", "customer_success", "finanzas",
    "legal", "operaciones", "inteligencia_mercado", "rrhh", "opengravity",
)


class Cubo:
    """Base de un cubo desacoplado. Subclasear y declarar `name`, `consume`, `produce`.

    `arrancar()` ejecuta la secuencia de §7.1 sin preguntar por ningún otro cubo.
    """
    name = "cubo"
    consume: tuple[EventType, ...] = ()       # tipos de evento que escucha
    produce: tuple[EventType, ...] = ()       # tipos de evento que emitirá

    def __init__(self, bus: MessageBus, company: str = "default") -> None:
        self.bus = bus
        self.company = company
        self._ready = False

    # Subclases sobreescriben para registrar sus handlers; NO deben referenciar otros cubos.
    def registrar_suscripciones(self) -> None:
        ...

    def arrancar(self) -> None:
        """Secuencia de arranque desacoplada. Idempotente."""
        if self._ready:
            return
        self.registrar_suscripciones()
        # Declarar qué emitirá y marcarse ready. Cero health-checks de otros cubos.
        self.bus.publish(Event(
            EventType.CUBE_STARTED, source=self.name,
            payload={"cube": self.name, "empresa": self.company,
                     "consume": [t.value for t in self.consume],
                     "produce": [t.value for t in self.produce]},
            company=self.company, criticality=Criticality.LOW,
        ))
        self._ready = True

    @property
    def listo(self) -> bool:
        return self._ready


class Orquestador:
    """Lee qué cubos están activos por empresa y los arranca. El cubo individual no conoce
    esta lista (regla 2 de §7.1)."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._fabricas: dict[str, Callable[[MessageBus, str], Cubo]] = {}
        self._activos: dict[str, list[Cubo]] = {}

    def registrar_fabrica(self, nombre: str, fabrica: Callable[[MessageBus, str], Cubo]) -> None:
        self._fabricas[nombre] = fabrica

    def arrancar(self, company: str, cubos: Iterable[str]) -> list[Cubo]:
        """Arranca la combinación de cubos pedida para una empresa. Cualquier combinación no
        vacía debe arrancar (la propiedad de §7.1)."""
        arrancados: list[Cubo] = []
        for nombre in cubos:
            fabrica = self._fabricas.get(nombre)
            if fabrica is None:
                continue
            cubo = fabrica(self.bus, company)
            # Un cubo puede arrancar en su construcción (CuboDepartamento, factorías del
            # catálogo) o exponer arrancar() explícito (Cubo base). Soportamos ambos.
            arrancar = getattr(cubo, "arrancar", None)
            if callable(arrancar):
                arrancar()
            arrancados.append(cubo)
        self._activos.setdefault(company, []).extend(arrancados)
        return arrancados

    def activos(self, company: str) -> list[str]:
        return [c.name for c in self._activos.get(company, [])]


def verificar_combinaciones(fabricas: dict[str, Callable[[MessageBus, str], Cubo]],
                            bus_factory: Callable[[], MessageBus],
                            *, company: str = "test") -> list[tuple[str, ...]]:
    """Matriz de combinaciones soportadas (§7.1): toda combinación NO VACÍA de los cubos
    dados debe arrancar sin excepción. Devuelve la lista de combinaciones que FALLARON
    (vacía si todas arrancan, que es la propiedad deseada).

    Si una no arranca, el bug está en el cubo que asumió la presencia de otro.
    """
    nombres = list(fabricas)
    fallidas: list[tuple[str, ...]] = []
    for r in range(1, len(nombres) + 1):
        for combo in combinations(nombres, r):
            bus = bus_factory()
            orq = Orquestador(bus)
            for n in combo:
                orq.registrar_fabrica(n, fabricas[n])
            try:
                orq.arrancar(company, combo)
            except Exception:  # noqa: BLE001 — cualquier excepción es una violación de §7.1
                fallidas.append(combo)
    return fallidas
