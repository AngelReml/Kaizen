"""Tracking de coste (port de Swarm IDE cost_tracker.py) extendido para KAIZEN.

Acumula coste a nivel de run y de sesión. `record_specialist` añade tracking por
departamento / especialista / clase de tarea y emite COST_RECORDED al bus con el payload
extendido.
"""
from __future__ import annotations

import sys
import threading

# Tarifas Anthropic: se reutilizan las de claude_client.py (fuente única de precio real
# por model_id) en vez de mantener una tabla separada — dos tablas con el mismo model_id
# y precios distintos (p. ej. claude-haiku-4-5) engañaban al techo de gasto (B-04). Import
# sin ciclo: claude_client.py no importa core.cost_tracker.
from claude_client import RATES as _ANTHROPIC_RATES

# Precios USD por 1M tokens (input, output).
_PRICING = {
    "anthropic": {
        **{modelo: (r["in"], r["out"]) for modelo, r in _ANTHROPIC_RATES.items()},
        # model_id que solo existen en la cadena multi-proveedor (core/model_router.py),
        # no en claude_client.RATES: mantienen aquí su propia tarifa.
        "claude-opus-4-5": (15.0, 75.0),
        "claude-sonnet-4-5": (3.0, 15.0),
    },
    "openai": {"gpt-4o": (2.50, 10.0), "gpt-4o-mini": (0.15, 0.60)},
    "groq": {"llama-3.3-70b-versatile": (0.59, 0.79), "llama-3.1-8b-instant": (0.05, 0.08)},
    "gemini": {"gemini-2.5-flash": (0.0, 0.0), "gemini-2.5-pro": (1.25, 10.0), "gemini-2.0-flash": (0.10, 0.40)},
    "deepseek": {"deepseek-chat": (0.27, 1.10), "deepseek-reasoner": (0.55, 2.19)},
    "glm": {"glm-4-plus": (0.70, 0.70), "glm-4-air": (0.10, 0.10), "glm-4-flash": (0.01, 0.01)},
    "huggingface": {},   # gratis
    "openrouter": {},    # varía; 0 para modelos free
}

EUR_PER_USD = 0.92

# Proveedores cuyo coste 0 es legítimo (gratuitos), para no avisar de tarifa ausente.
_FREE_PROVIDERS = frozenset({"huggingface", "openrouter"})

_bus = None
_run = {"usd": 0.0, "tokens_in": 0, "tokens_out": 0}
_session = {"usd": 0.0, "tokens_in": 0, "tokens_out": 0}
_lock = threading.Lock()       # protege los acumuladores globales (especialistas concurrentes)
_unpriced_avisados: set[tuple[str, str]] = set()


def set_bus(bus) -> None:
    global _bus
    _bus = bus


def reset_run() -> None:
    global _run
    with _lock:
        _run = {"usd": 0.0, "tokens_in": 0, "tokens_out": 0}


def precio(provider: str, modelo: str, tokens_in: int, tokens_out: int) -> float:
    tabla = _PRICING.get(provider, {})
    if modelo not in tabla and provider not in _FREE_PROVIDERS:
        # Un modelo de pago sin tarifa se contabilizaría como 0 € y engañaría al techo
        # de gasto. Avisamos una vez por (provider, modelo) en vez de fingir gratis.
        clave = (provider, modelo)
        if clave not in _unpriced_avisados:
            _unpriced_avisados.add(clave)
            print(f"[cost_tracker] sin tarifa para {provider}/{modelo}; coste contado como 0 €.",
                  file=sys.stderr)
    pin, pout = tabla.get(modelo, (0.0, 0.0))
    return (tokens_in * pin + tokens_out * pout) / 1_000_000


def record(provider: str, modelo: str, tokens_in: int, tokens_out: int) -> float:
    usd = precio(provider, modelo, tokens_in, tokens_out)
    with _lock:
        for acc in (_run, _session):
            acc["usd"] += usd
            acc["tokens_in"] += tokens_in
            acc["tokens_out"] += tokens_out
    return usd


def record_specialist(departamento: str, especialista: str, clase_tarea: str, modelo: str,
                      tokens_in: int, tokens_out: int, coste_eur: float | None = None,
                      provider: str = "", company: str = "default") -> float:
    """Registra coste de un especialista y emite COST_RECORDED con payload extendido."""
    usd = record(provider, modelo, tokens_in, tokens_out)
    eur = coste_eur if coste_eur is not None else round(usd * EUR_PER_USD, 6)
    if _bus is not None:
        from core.events import Event, EventType
        _bus.publish(Event(
            EventType.COST_RECORDED, source="contabilidad",
            payload={
                "model": modelo, "usd": round(usd, 6), "eur": eur,
                "in": tokens_in, "out": tokens_out,
                "departamento": departamento, "especialista": especialista,
                "clase_tarea": clase_tarea, "accion": especialista,
            },
            company=company,
        ))
    return eur


def run_cost() -> dict:
    return dict(_run)


def session_cost() -> dict:
    return dict(_session)
