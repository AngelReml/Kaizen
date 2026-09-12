"""Tests de las clases de tarea y el routing por clase (Bloque 2)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task_classes import ClaseTarea, PRESUPUESTO_POR_CLASE, get_model_for_class

_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "GLM_API_KEY",
         "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "HF_TOKEN", "OPENROUTER_API_KEY"]


def _sin_keys():
    return {k: os.environ.pop(k, None) for k in _KEYS}


def _restaurar(saved):
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


def test_presupuesto_asignado_correctamente():
    assert set(PRESUPUESTO_POR_CLASE) == set(ClaseTarea)
    assert PRESUPUESTO_POR_CLASE[ClaseTarea.CLASIFICACION] == "cheap"
    assert PRESUPUESTO_POR_CLASE[ClaseTarea.REDACCION] == "medium"
    assert PRESUPUESTO_POR_CLASE[ClaseTarea.RAZONAMIENTO] == "heavy"
    assert PRESUPUESTO_POR_CLASE[ClaseTarea.FUNCION] is None


def test_funcion_no_instancia_modelo():
    assert get_model_for_class(ClaseTarea.FUNCION) is None


def test_fallback_medium_a_cheap():
    saved = _sin_keys()
    os.environ["GROQ_API_KEY"] = "gsk-test"   # solo barato disponible, ningún medium de la lista
    try:
        e = get_model_for_class(ClaseTarea.REDACCION)
        assert e is not None and e.provider == "groq"
    finally:
        _restaurar(saved)


def test_medium_prefiere_haiku():
    saved = _sin_keys()
    os.environ["ANTHROPIC_API_KEY"] = "sk-test"
    try:
        assert get_model_for_class(ClaseTarea.REDACCION).model_id == "claude-haiku-4-5"
    finally:
        _restaurar(saved)


def test_sin_keys_lanza_error_claro():
    saved = _sin_keys()
    try:
        import pytest
        with pytest.raises(RuntimeError, match="No hay modelo disponible"):
            get_model_for_class(ClaseTarea.CLASIFICACION)
    finally:
        _restaurar(saved)


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
