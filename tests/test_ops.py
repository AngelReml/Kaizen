"""Tests del departamento de Ops (Fase 5.2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.knowledge import InMemoryKnowledge
from departments.ops import reglas, herramientas as h
from departments.ops.agente import OpsDepartment


# ── reglas ──────────────────────────────────────────────────────────────────
def test_capacidad_supera_umbral():
    assert reglas.capacidad_supera_umbral(0.95)[0] is False
    assert reglas.capacidad_supera_umbral(0.5)[0] is True


def test_stock_bajo_seguridad():
    assert reglas.stock_bajo_seguridad(2, 5)[0] is False
    assert reglas.stock_bajo_seguridad(8, 5)[0] is True


# ── herramientas ────────────────────────────────────────────────────────────
def test_agendar_pedido_y_conflicto():
    k = InMemoryKnowledge()
    r1 = h.agendar_pedido(k, "c", "Cliente A", ["torta"], "2026-06-01", capacidad_diaria=2)
    r2 = h.agendar_pedido(k, "c", "Cliente B", ["pastel"], "2026-06-01", capacidad_diaria=2)
    r3 = h.agendar_pedido(k, "c", "Cliente C", ["dulce"], "2026-06-01", capacidad_diaria=2)
    assert r1["ok"] and r2["ok"] and r3["ok"] is False and "conflicto" in r3


def test_consultar_capacidad():
    k = InMemoryKnowledge()
    h.agendar_pedido(k, "c", "A", ["x"], "2026-06-01", capacidad_diaria=10)
    cap = h.consultar_capacidad(k, "c", "2026-06-01", capacidad_diaria=10)
    assert cap["ocupada"] == 1 and cap["libre"] == 9


def test_alerta_stock():
    k = InMemoryKnowledge()
    k.add("c", "inventario", "harina", {"material": "harina", "stock": 2, "stock_seguridad": 5, "company": "c"})
    k.add("c", "inventario", "azucar", {"material": "azucar", "stock": 20, "stock_seguridad": 5, "company": "c"})
    al = h.alerta_stock(k, "c")
    assert len(al) == 1 and al[0]["material"] == "harina"


# ── agente ──────────────────────────────────────────────────────────────────
def test_agente_elige_herramienta():
    k = InMemoryKnowledge()
    d = OpsDepartment(InMemoryBus(), k)
    assert d.responder("¿cómo está la capacidad hoy?", "c")[1] == "consultar_capacidad"
    assert d.responder("¿qué materias primas están bajo stock?", "c")[1] == "alerta_stock"


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
