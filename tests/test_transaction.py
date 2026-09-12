"""Tests de transacciones y compensación (Fase 4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.guardian import Guardian, Action, Decision
from core.transaction import Transaction, Step


# Guardián que bloquea (vía semántica) los pasos marcados con payload {"malo": True}.
def _guardian():
    sem = lambda a: (Decision.BLOCKED, "paso vetado") if a.payload.get("malo") else (Decision.APPROVED, "ok")
    return Guardian(InMemoryBus(), semantic=sem)


def _step(name, log, *, compensable=True, malo=False):
    payload = {"paso": name}
    if malo:
        payload["malo"] = True
    return Step(
        name=name,
        action=Action("paso", payload=payload),
        do=lambda: log.append(("do", name)),
        compensate=(lambda: log.append(("undo", name))) if compensable else None,
    )


def test_transaccion_completa():
    log = []
    bus = InMemoryBus()
    steps = [_step("A", log), _step("B", log), _step("C", log)]
    r = Transaction(bus, _guardian(), steps).execute()
    assert r.ok and r.ejecutados == ["A", "B", "C"]
    assert log == [("do", "A"), ("do", "B"), ("do", "C")]


def test_veto_tardio_compensa_en_orden_inverso():
    log = []
    steps = [_step("A", log), _step("B", log), _step("C", log, malo=True)]
    r = Transaction(InMemoryBus(), _guardian(), steps).execute()
    assert not r.ok and r.vetado_en == "C"
    assert r.ejecutados == ["A", "B"]
    assert r.compensados == ["B", "A"]                 # orden inverso
    assert log == [("do", "A"), ("do", "B"), ("undo", "B"), ("undo", "A")]


def test_paso_no_compensable_se_escala():
    log = []
    steps = [
        _step("A", log, compensable=False),            # no se puede deshacer
        _step("B", log),
        _step("C", log, malo=True),
    ]
    r = Transaction(InMemoryBus(), _guardian(), steps).execute()
    assert not r.ok
    assert r.compensados == ["B"]
    assert r.sin_compensar == ["A"]                    # parcialmente ejecutada -> escala


def test_veto_en_primer_paso_no_compensa_nada():
    log = []
    steps = [_step("A", log, malo=True), _step("B", log)]
    r = Transaction(InMemoryBus(), _guardian(), steps).execute()
    assert not r.ok and r.vetado_en == "A"
    assert r.ejecutados == [] and r.compensados == [] and log == []


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
