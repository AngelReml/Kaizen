"""Tests adversariales de las reglas duras de Finanzas (Fase 1.2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.guardian import Guardian, Action, Decision
from departments.finanzas import reglas


def test_bloquea_si_gasto_diario_alto():
    # presupuesto 30€/mes -> límite diario 1€; 0,9€ supera el 80% (0,8€).
    ok, motivo = reglas.gasto_diario_supera_porcentaje(0.9, 30.0)
    assert ok is False and "supera" in motivo


def test_no_bloquea_si_gasto_diario_normal():
    ok, _ = reglas.gasto_diario_supera_porcentaje(0.5, 30.0)
    assert ok is True


def test_rate_limit_sonnet():
    ok, motivo = reglas.tasa_llamadas_por_minuto("claude-sonnet-4-6", 10)
    assert ok is False and "Rate limit" in motivo


def test_rate_limit_haiku_mas_permisivo():
    assert reglas.tasa_llamadas_por_minuto("haiku", 10)[0] is True   # haiku permite 30
    assert reglas.tasa_llamadas_por_minuto("haiku", 30)[0] is False


def test_escala_coste_unico_alto():
    g = Guardian(reglas_extra=[reglas.como_regla_guardian])
    v = g.evaluate(Action("ejecutar_tarea", payload={"eur_estimado": 5.0}))
    assert v.decision is Decision.ESCALATED


def test_coste_unico_bajo_pasa():
    g = Guardian(reglas_extra=[reglas.como_regla_guardian])
    v = g.evaluate(Action("ejecutar_tarea", payload={"eur_estimado": 0.5}))
    assert v.decision is Decision.APPROVED


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
