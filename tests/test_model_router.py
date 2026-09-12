"""Tests del router de modelos y el cost_tracker (Bloque 1)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.model_router as mr
import core.cost_tracker as ct
from core.bus import InMemoryBus
from core.events import EventType


_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "GLM_API_KEY",
         "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "HF_TOKEN", "OPENROUTER_API_KEY"]


def _sin_keys():
    return {k: os.environ.pop(k, None) for k in _KEYS}


def _restaurar(saved):
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


def test_chain_disponibilidad_sin_keys():
    saved = _sin_keys()
    try:
        assert all(not e.available() for e in mr.CHAIN)
        assert mr.get_cheap_model() is None and mr.get_heavy_model() is None
    finally:
        _restaurar(saved)


def test_is_retriable_patrones():
    assert mr.is_retriable(Exception("Error 429: rate limit exceeded"))
    assert mr.is_retriable(Exception("HTTP 402 Payment Required"))
    assert mr.is_retriable(Exception("error 1113 余额不足"))
    assert mr.is_retriable(Exception("context_length_exceeded"))
    assert not mr.is_retriable(Exception("NameError: x is not defined"))


def test_get_cheap_model_fallback_solo_anthropic():
    saved = _sin_keys()
    os.environ["ANTHROPIC_API_KEY"] = "sk-test"
    try:
        e = mr.get_cheap_model()
        assert e is not None and e.provider == "anthropic"   # cae a 'cualquiera'
    finally:
        _restaurar(saved)


def test_get_heavy_model_prefiere_anthropic():
    saved = _sin_keys()
    os.environ["ANTHROPIC_API_KEY"] = "sk-test"
    os.environ["GROQ_API_KEY"] = "gsk-test"
    try:
        assert mr.get_heavy_model().provider == "anthropic"
    finally:
        _restaurar(saved)


def test_cadena_24_modelos():
    assert len(mr.CHAIN) == 24


def test_cost_tracker_record_specialist():
    ct.reset_run()
    bus = InMemoryBus()
    ct.set_bus(bus)
    eur = ct.record_specialist("finanzas", "InterpreteDeTendencias", "SINTETIZAR",
                               "glm-4-flash", 1000, 500, provider="glm", company="laboratorio")
    assert eur >= 0
    evs = [e for e in bus.history() if e.type is EventType.COST_RECORDED]
    assert len(evs) == 1
    assert evs[0].payload["departamento"] == "finanzas"
    assert evs[0].payload["clase_tarea"] == "SINTETIZAR"
    ct.set_bus(None)


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
