"""Tests de la contabilidad de coste (umbrales de alerta). Runnable con python o pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_client import cost_alert_level


def test_sin_alerta_por_debajo_del_50():
    assert cost_alert_level(4.0, 16.0, set()) is None


def test_alerta_50():
    assert cost_alert_level(8.0, 16.0, set()) == 50


def test_alerta_80():
    assert cost_alert_level(13.0, 16.0, set()) == 80   # 13/16 = 81%


def test_no_repite_80_pero_da_50_si_falta():
    assert cost_alert_level(13.0, 16.0, {80}) == 50


def test_no_repite_alertas_ya_dadas():
    assert cost_alert_level(13.0, 16.0, {80, 50}) is None


def test_limite_cero_no_revienta():
    assert cost_alert_level(5.0, 0.0, set()) is None


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
