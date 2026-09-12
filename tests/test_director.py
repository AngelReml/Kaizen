"""Tests del Director y la orquestación de departamentos. Runnable con python o pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import EventType
from core.director import Director
from departments.base import Department, Task, TaskResult


class StubDept(Department):
    def __init__(self, bus, name, *, result=None, raise_exc=False):
        super().__init__(bus)
        self.name = name
        self._result = result or TaskResult(True, "ok")
        self._raise = raise_exc
        self.called = False

    def run(self, task: Task) -> TaskResult:
        self.called = True
        if self._raise:
            raise RuntimeError("boom")
        return self._result


def _tipos(bus):
    return [e.type for e in bus.history()]


def test_enruta_y_ejecuta_prospeccion():
    bus = InMemoryBus()
    dept = StubDept(bus, "prospeccion", result=TaskResult(True, "2 leads"))
    d = Director(bus, {"prospeccion": dept})
    r = d.handle_intent("busca leads de tiendas gourmet en Murcia", company="laboratorio")
    assert r.ok and dept.called
    assert _tipos(bus) == [
        EventType.INTENT_RECEIVED, EventType.INTENT_ROUTED,
        EventType.DEPT_TASK_STARTED, EventType.DEPT_TASK_COMPLETED,
        EventType.RESULT_CONSOLIDATED,
    ]


def test_intent_sin_departamento():
    bus = InMemoryBus()
    d = Director(bus, {"prospeccion": StubDept(bus, "prospeccion")})
    r = d.handle_intent("hola, qué tal")
    assert not r.ok
    assert EventType.INTENT_ROUTED not in _tipos(bus)


def test_reflexion_bloquea_si_humano_deniega():
    bus = InMemoryBus()
    dept = StubDept(bus, "redaccion")
    d = Director(bus, {"redaccion": dept}, confirm=lambda _: False)
    r = d.handle_intent("envía un correo al cliente")   # alta criticidad
    assert not r.ok and not dept.called
    tipos = _tipos(bus)
    assert EventType.APPROVAL_REQUESTED in tipos and EventType.APPROVAL_DENIED in tipos
    assert EventType.DEPT_TASK_STARTED not in tipos


def test_reflexion_continua_si_humano_aprueba():
    bus = InMemoryBus()
    dept = StubDept(bus, "redaccion")
    d = Director(bus, {"redaccion": dept}, confirm=lambda _: True)
    r = d.handle_intent("envía un correo al cliente")
    assert r.ok and dept.called
    assert EventType.APPROVAL_GRANTED in _tipos(bus)


def test_departamento_en_simulacion():
    from departments.prospeccion import ProspeccionDepartment
    bus = InMemoryBus()
    d = Director(bus, {"prospeccion": ProspeccionDepartment(bus, simulacion=True)})
    r = d.handle_intent("busca leads gourmet en Murcia")
    assert r.ok and r.data.get("simulado") is True
    assert EventType.DEPT_TASK_COMPLETED in _tipos(bus)


def test_fallo_de_departamento_se_propaga():
    bus = InMemoryBus()
    dept = StubDept(bus, "prospeccion", raise_exc=True)
    d = Director(bus, {"prospeccion": dept})
    r = d.handle_intent("busca leads")
    assert not r.ok
    assert EventType.DEPT_TASK_FAILED in _tipos(bus)


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
