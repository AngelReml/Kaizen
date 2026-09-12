"""Tests de comunicación interdepartamental (Fase 3). Runnable con python o pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import EventType
from core.director import Director
from departments.prospeccion import ProspeccionDepartment
from departments.redaccion import RedaccionDepartment
from departments.protocolos import ProspeccionARedaccion


def _eventos_de(bus, source):
    return [e for e in bus.history() if e.source == source]


def test_prospeccion_dispara_redaccion_sin_director():
    """Criterio de salida Fase 3: el flujo cruza dos departamentos sin mediación humana."""
    bus = InMemoryBus()
    prospeccion = ProspeccionDepartment(bus, simulacion=True)   # devuelve 2 leads de ejemplo
    redaccion = RedaccionDepartment(bus, simulacion=True)
    ProspeccionARedaccion(bus, redaccion)                       # protocolo automático
    director = Director(bus, {"prospeccion": prospeccion})

    director.handle_intent("busca leads de tiendas gourmet en Murcia", company="laboratorio")

    # Redacción se ejecutó automáticamente, una vez por cada lead, sin que el Director la enrutara.
    redaccion_completadas = [e for e in _eventos_de(bus, "redaccion")
                             if e.type is EventType.DEPT_TASK_COMPLETED]
    assert len(redaccion_completadas) == 2


def test_no_hay_bucle_infinito():
    """Las finalizaciones de redaccion no se retroalimentan al protocolo."""
    bus = InMemoryBus()
    redaccion = RedaccionDepartment(bus, simulacion=True)
    ProspeccionARedaccion(bus, redaccion)
    director = Director(bus, {"prospeccion": ProspeccionDepartment(bus, simulacion=True)})

    director.handle_intent("busca leads gourmet", company="laboratorio")

    # 2 leads -> exactamente 2 ejecuciones de redaccion, ni una más.
    iniciadas = [e for e in _eventos_de(bus, "redaccion") if e.type is EventType.DEPT_TASK_STARTED]
    assert len(iniciadas) == 2


def test_protocolo_ignora_otras_fuentes():
    """Un completado que no venga de prospeccion no dispara redaccion."""
    from departments.base import Task
    bus = InMemoryBus()
    redaccion = RedaccionDepartment(bus, simulacion=True)
    ProspeccionARedaccion(bus, redaccion)
    # un departamento cualquiera (no prospeccion) completa con 'leads' en el payload
    otro = RedaccionDepartment(bus, simulacion=True)
    otro.name = "marketing"
    otro.handle(Task(intent="x", payload={"lead": "X"}, company="laboratorio"))

    iniciadas = [e for e in _eventos_de(bus, "redaccion") if e.type is EventType.DEPT_TASK_STARTED]
    assert len(iniciadas) == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
