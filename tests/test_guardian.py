"""Tests del Guardián (reglas duras, nivel 1). Runnable con python o pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import EventType
from core.guardian import Guardian, Action, Context, Decision


def test_accion_benigna_aprobada():
    g = Guardian()
    v = g.evaluate(Action("buscar_leads", payload={"perfil": "tiendas gourmet"}))
    assert v.decision is Decision.APPROVED


def test_irreversible_escala_a_humano():
    g = Guardian()
    v = g.evaluate(Action("send_email", payload={"to": "x@y.com"}))
    assert v.decision is Decision.ESCALATED


def test_presupuesto_agotado_bloquea():
    g = Guardian(cost_provider=lambda company: 20.0, limit_eur=16.0)
    v = g.evaluate(Action("buscar_leads"))
    assert v.decision is Decision.BLOCKED
    assert "Presupuesto" in v.reason


def test_credenciales_bloqueadas():
    g = Guardian()
    v = g.evaluate(Action("read_file", payload={"path": "C:/proj/.env"}))
    assert v.decision is Decision.BLOCKED


def test_comando_local_destructivo_bloqueado():
    g = Guardian()
    v = g.evaluate(Action("shell", payload={"cmd": "rm -rf /"}, context=Context.LOCAL))
    assert v.decision is Decision.BLOCKED


def test_veredicto_se_emite_al_bus():
    bus = InMemoryBus()
    eventos = []
    bus.subscribe(eventos.append)
    g = Guardian(bus=bus)
    g.evaluate(Action("send_email", payload={"to": "x@y.com"}, company="laboratorio"))
    assert len(eventos) == 1
    assert eventos[0].type is EventType.GUARDIAN_ESCALATED
    assert eventos[0].company == "laboratorio"


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
