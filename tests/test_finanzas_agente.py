"""Tests del agente conversacional de Finanzas (Fase 1.4): elección de herramienta."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.knowledge import InMemoryKnowledge
from departments.finanzas.agente import FinanzasDepartment


def _dept():
    k = InMemoryKnowledge()
    ts = datetime.now(timezone.utc).isoformat()
    for i, eur in enumerate([0.5, 1.0, 0.3]):
        k.add("c", "gasto", f"g{i}",
              {"id": "x", "ts": ts, "modelo": "haiku", "usd": eur, "eur": eur,
               "tokens_in": 1, "tokens_out": 1, "accion": f"a{i}", "categoria": "otros", "company": "c"})
    return FinanzasDepartment(InMemoryBus(), k, presupuesto_mensual=16.0)


def test_elige_herramienta_correcta():
    d = _dept()
    casos = {
        "¿Cuánto llevamos gastado este mes?": "consultar_gasto",
        "¿Cuántos días aguantamos al ritmo actual?": "proyectar_quema",
        "¿Qué acción nos ha costado más esta semana?": "top_acciones_caras",
        "¿Ha habido algún gasto raro últimamente?": "detectar_anomalia",
        "Compara el gasto de esta semana con la anterior.": "comparar_periodos",
    }
    for pregunta, esperada in casos.items():
        _, herr = d.responder(pregunta, "c")
        assert herr == esperada, f"{pregunta!r} -> {herr}, esperaba {esperada}"


def test_respuesta_contiene_datos_reales():
    d = _dept()
    respuesta, _ = d.responder("¿cuánto gastado este mes?", "c")
    assert "1.8" in respuesta or "1.80" in respuesta   # 0.5+1.0+0.3 = 1.8€


def test_run_emite_resultado():
    d = _dept()
    from departments.base import Task
    r = d.handle(Task(intent="¿cuánto gastado?", company="c"))
    assert r.ok and r.data.get("herramienta") == "consultar_gasto"


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
