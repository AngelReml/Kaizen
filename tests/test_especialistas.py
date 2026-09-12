"""Tests de los departamentos especialistas y su enrutado (Fase 5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import EventType
from core.director import Director
from departments.especialistas import crear_departamentos, PERSONAS


def _director_completo():
    bus = InMemoryBus()
    deps = crear_departamentos(bus, simulacion=True)
    return bus, Director(bus, deps)


def test_se_crean_los_seis():
    deps = crear_departamentos(InMemoryBus(), simulacion=True)
    assert set(deps) == set(PERSONAS) == {"legal", "desarrollo", "qa", "finanzas", "ops", "rrhh"}


def test_enrutado_a_cada_departamento():
    casos = {
        "revisa el contrato y la cláusula RGPD": "legal",
        "arregla el bug del código en el despliegue": "desarrollo",
        "valida la calidad de este resultado": "qa",
        "analiza el presupuesto y el margen": "finanzas",
        "coordina el pedido con el proveedor": "ops",
        "contrata personal para la plantilla": "rrhh",
    }
    for intent, esperado in casos.items():
        bus, d = _director_completo()
        d.handle_intent(intent, company="laboratorio")
        rutados = [e.payload.get("departamento") for e in bus.history()
                   if e.type is EventType.INTENT_ROUTED]
        assert rutados == [esperado], f"{intent!r} -> {rutados}, esperaba {esperado}"


def test_ejecucion_en_simulacion():
    bus, d = _director_completo()
    r = d.handle_intent("analiza el presupuesto del trimestre", company="laboratorio")
    assert r.ok and r.data.get("simulado") is True
    assert EventType.DEPT_TASK_COMPLETED in [e.type for e in bus.history()]


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
