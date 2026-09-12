"""Tests de integración de pipelines (PASO 8). Sin mocks de LLM.

Los que hacen llamadas LLM reales (con coste) están gateados tras KAIZEN_TEST_LLM=1, y
además requieren ANTHROPIC_API_KEY + langchain; si no, se saltan. Así el `pytest` normal no
gasta API. El de fallback corre siempre (offline). Usan una empresa de prueba creada como
fixture y borrada al final.

Para correrlos de verdad:  KAIZEN_TEST_LLM=1 python -m pytest tests/test_pipeline_integracion.py
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from departments.base import Task
from departments.prospeccion import ProspeccionDepartment
from departments.redaccion import RedaccionDepartment
from core.bus import InMemoryBus
from core.events import EventType

ROOT = Path(__file__).parent.parent
EMPRESA = ROOT / "diario" / "test_empresa"


def _tiene_llm() -> bool:
    if os.getenv("KAIZEN_TEST_LLM") != "1":   # opt-in explícito: evita coste en cada `pytest`
        return False
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import langchain_anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _crear_empresa(con_remitente=False, con_lead=False) -> None:
    (EMPRESA / "clientes").mkdir(parents=True, exist_ok=True)
    ctx = "# Contexto\n\n## El negocio\nEmpresa de prueba del sector alimentación gourmet.\n"
    if con_remitente:
        ctx += ("\n## Contacto comercial (remitente)\n"
                "- **Nombre:** Persona Prueba\n- **Email:** prueba@test.com\n")
    (EMPRESA / "CONTEXTO_NEGOCIO.md").write_text(ctx, encoding="utf-8")
    if con_lead:
        (EMPRESA / "clientes" / "test_lead.md").write_text(
            "# Test Lead\n- **Email:** lead@test.com\n- Tipo: tienda gourmet\n", encoding="utf-8")


def _borrar_empresa() -> None:
    if EMPRESA.exists():
        shutil.rmtree(EMPRESA)


def test_prospeccion_pipeline_real():
    if not _tiene_llm():
        pytest.skip("requiere KAIZEN_TEST_LLM=1 + ANTHROPIC_API_KEY + langchain")
    _crear_empresa()
    try:
        bus = InMemoryBus()
        dep = ProspeccionDepartment(bus, simulacion=False)
        dep.usar_pipeline = True
        r = dep.run(Task(intent="busca 3 candidatos de prueba", company="test_empresa",
                         payload={"perfil": "tiendas gourmet"}))
        assert r is not None and isinstance(r.summary, str)   # TaskResult, nunca excepción
        costes = [e for e in bus.history() if e.type is EventType.COST_RECORDED]
        for e in costes:
            assert "departamento" in e.payload and "especialista" in e.payload
    finally:
        _borrar_empresa()


def test_redaccion_pipeline_identidad_desde_contexto():
    if not _tiene_llm():
        pytest.skip("requiere KAIZEN_TEST_LLM=1 + ANTHROPIC_API_KEY + langchain")
    _crear_empresa(con_remitente=True, con_lead=True)
    try:
        bus = InMemoryBus()
        dep = RedaccionDepartment(bus)
        dep.usar_pipeline = True
        r = dep.run(Task(intent="redacta para test_lead", company="test_empresa",
                         payload={"lead": "test_lead", "ficha_lead": "tienda gourmet"}))
        assert r is not None and isinstance(r.summary, str)
    finally:
        _borrar_empresa()


def test_pipeline_fallback_funciona():
    """Si el pipeline lanza, run() cae al legacy y el bus recibe el warning. Offline."""
    bus = InMemoryBus()
    dep = ProspeccionDepartment(bus, simulacion=True)   # legacy = simulación (sin red)
    dep.usar_pipeline = True

    def _boom(task):
        raise RuntimeError("fallo simulado del pipeline")
    dep.pipeline.ejecutar = _boom

    r = dep.run(Task(intent="busca", company="test_empresa", payload={"perfil": "x"}))
    assert r is not None and isinstance(r.summary, str)    # devuelve TaskResult, no lanza
    warnings = [e for e in bus.history() if e.payload.get("warning")]
    assert warnings, "el bus debe recibir el warning con el traceback del fallo"
    assert "Traceback" in warnings[0].payload["warning"]


if __name__ == "__main__":
    # Runner manual: ejecuta solo los que no requieren pytest.skip.
    try:
        test_pipeline_fallback_funciona()
        print("  PASS  test_pipeline_fallback_funciona")
        print("\n1/1 tests OK (los reales requieren pytest + key + langchain)")
    except AssertionError as e:
        print(f"  FAIL  test_pipeline_fallback_funciona: {e}")
        sys.exit(1)
