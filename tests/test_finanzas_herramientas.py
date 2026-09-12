"""Tests de las herramientas de Finanzas (Fase 1.3) con datos sembrados."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.finanzas import herramientas as h

NOW = datetime.now(timezone.utc)


def _g(eur, ts=None, modelo="haiku", accion="x"):
    ts = ts or NOW.isoformat()
    return {"id": "x", "ts": ts, "modelo": modelo, "usd": round(eur / 0.92, 6),
            "eur": eur, "tokens_in": 1, "tokens_out": 1, "accion": accion,
            "categoria": "otros", "company": "c"}


def _k(gastos):
    k = InMemoryKnowledge()
    for i, g in enumerate(gastos):
        k.add("c", "gasto", f"g{i}", g)
    return k


def test_consultar_gasto_total_y_desglose():
    k = _k([_g(1.0, modelo="haiku"), _g(2.0, modelo="sonnet")])
    r = h.consultar_gasto(k, "c", "todo")
    assert r["total_eur"] == 3.0 and r["n_acciones"] == 2
    assert r["desglose_por_modelo"]["sonnet"] == 2.0


def test_consultar_gasto_filtra_periodo():
    viejo = (NOW - timedelta(days=40)).isoformat()
    k = _k([_g(1.0), _g(5.0, ts=viejo)])
    assert h.consultar_gasto(k, "c", "hoy")["total_eur"] == 1.0


def test_top_acciones_caras_ordena():
    k = _k([_g(1.0, accion="a"), _g(3.0, accion="b"), _g(2.0, accion="c")])
    top = h.top_acciones_caras(k, "c", n=2, periodo="todo")
    assert [t["accion"] for t in top] == ["b", "c"]


def test_comparar_periodos():
    viejo = (NOW - timedelta(days=40)).isoformat()
    k = _k([_g(2.0), _g(8.0, ts=viejo)])
    r = h.comparar_periodos(k, "c", "hoy", "todo")
    assert r["p1_total"] == 2.0 and r["p2_total"] == 10.0


def test_proyectar_quema_runway():
    # 3 días de 1€/día, presupuesto 30€ -> ~ (30 - gastado_mes) / 1.
    dia = NOW.isoformat()
    ayer = (NOW - timedelta(days=1)).isoformat()
    anteayer = (NOW - timedelta(days=2)).isoformat()
    k = _k([_g(1.0, ts=dia), _g(1.0, ts=ayer), _g(1.0, ts=anteayer)])
    r = h.proyectar_quema(k, "c", presupuesto_mensual=30.0)
    assert r["gasto_diario_medio"] == 1.0
    assert r["dias_runway_si_no_recargas"] is not None


def test_detectar_anomalia():
    k = _k([_g(0.01) for _ in range(8)] + [_g(1.0, accion="caro")])
    an = h.detectar_anomalia(k, "c", sensibilidad=2.0)
    assert len(an) == 1 and an[0]["eur"] == 1.0


def test_sin_anomalia_si_homogeneo():
    k = _k([_g(0.5) for _ in range(5)])
    assert h.detectar_anomalia(k, "c") == []


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
