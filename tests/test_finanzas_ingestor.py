"""Tests del ingestor de Finanzas (Fase 1.1)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import Event, EventType
from core.knowledge import InMemoryKnowledge
from core.subscriptors.finanzas_ingestor import FinanzasIngestor, categoria_de_modelo


def test_ingiere_diez_eventos_de_coste():
    bus = InMemoryBus()
    k = InMemoryKnowledge()
    FinanzasIngestor(bus, k)
    for i in range(10):
        bus.publish(Event(EventType.COST_RECORDED, source="contabilidad",
                          payload={"model": "claude-haiku-4-5", "usd": 0.001, "in": 100, "out": 50},
                          company="laboratorio"))
    assert len(k.all("laboratorio", "gasto")) == 10


def test_aislamiento_por_empresa():
    bus = InMemoryBus()
    k = InMemoryKnowledge()
    FinanzasIngestor(bus, k)
    bus.publish(Event(EventType.COST_RECORDED, source="contabilidad",
                      payload={"model": "sonnet", "usd": 0.01}, company="laboratorio"))
    bus.publish(Event(EventType.COST_RECORDED, source="contabilidad",
                      payload={"model": "sonnet", "usd": 0.01}, company="demo-soft"))
    assert len(k.all("laboratorio", "gasto")) == 1
    assert len(k.all("demo-soft", "gasto")) == 1


def test_categoria_por_modelo():
    assert categoria_de_modelo("claude-haiku-4-5") == "tareas-ligeras"
    assert categoria_de_modelo("claude-sonnet-4-6") == "analisis"
    assert categoria_de_modelo("gpt-4") == "otros"


def test_solo_escucha_cost_recorded():
    bus = InMemoryBus()
    k = InMemoryKnowledge()
    FinanzasIngestor(bus, k)
    bus.publish(Event(EventType.DEPT_TASK_STARTED, source="x", company="laboratorio"))
    assert len(k.all("laboratorio", "gasto")) == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
