"""Anthropic wrapper con seguimiento de coste por sesión y por día."""
import os
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

from core.bloqueo import bloqueo_exclusivo, escribir_atomico

load_dotenv(Path(__file__).parent / ".env")

ROOT = Path(__file__).parent
COST_FILE = ROOT / ".kaizen_cost.json"

# USD por millón de tokens (tarifas oficiales).
RATES = {
    "claude-haiku-4-5-20251001": {"in": 1.00,  "out": 5.00},
    "claude-haiku-4-5":          {"in": 1.00,  "out": 5.00},
    "claude-sonnet-4-6":         {"in": 3.00,  "out": 15.00},
}
# Modelo sin tarifa: se presume caro (tier Opus) en vez de barato. Presuponer
# barato hacía que el techo de gasto no viese el gasto real (B-01).
_TARIFA_DESCONOCIDA = {"in": 5.00, "out": 25.00}

DAILY_BUDGET_EUR = float(os.environ.get("LIMITE_COSTE_DIARIO_EUR", "16.0") or 16.0)
EUR_PER_USD      = 0.92


def _hoy() -> str:
    """Frontera de día en UTC — misma que usan core/ledger.py y core/techos.py. Antes este
    módulo usaba date.today() (hora local): con hora local, el ledger y los techos ya
    habían cruzado a un día nuevo mientras este tope diario seguía en el de ayer (o
    viceversa), dos fronteras de día distintas para el mismo gasto."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

_client_instance: Anthropic | None = None
_session_usd = 0.0

# Lock que serializa la contabilidad de coste (sesión + fichero diario). El panel ejecuta
# llamadas concurrentes (asyncio.to_thread); sin esto el read-modify-write pierde gasto.
_cost_lock = threading.Lock()

# Integración con el bus del Sistema Operativo Empresarial (opcional, no rompe la CLI).
_bus = None
_alerted_levels: set[int] = set()
_alerted_date: str = ""


def set_bus(bus) -> None:
    """Conecta la contabilidad al bus para emitir eventos de coste."""
    global _bus
    _bus = bus


def cost_alert_level(eur: float, limit: float, already: set[int]) -> int | None:
    """Umbral (80 o 50) a alertar si se cruza por primera vez; None si no toca."""
    pct = (eur / limit * 100) if limit else 0
    for level in (80, 50):
        if pct >= level and level not in already:
            return level
    return None


def _emit_cost(model: str, usd: float, tok_in: int, tok_out: int, company: str) -> None:
    if _bus is None:
        return
    from core.events import Event, EventType, Criticality
    _bus.publish(Event(
        EventType.COST_RECORDED, source="contabilidad",
        payload={"model": model, "usd": round(usd, 6), "in": tok_in, "out": tok_out},
        company=company,
    ))
    eur = daily_cost_eur()
    global _alerted_date
    hoy = _hoy()
    if _alerted_date != hoy:           # nuevo día → vuelven a poder dispararse las alertas
        _alerted_date = hoy
        _alerted_levels.clear()
    level = cost_alert_level(eur, DAILY_BUDGET_EUR, _alerted_levels)
    if level is not None:
        _alerted_levels.add(level)
        _bus.publish(Event(
            EventType.COST_ALERT, source="contabilidad",
            payload={"level": level, "eur": round(eur, 3)},
            company=company, criticality=Criticality.HIGH,
        ))


def _client() -> Anthropic:
    global _client_instance
    if not _client_instance:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY no encontrada en .env")
        _client_instance = Anthropic(api_key=key)
    return _client_instance


def _leer_estado() -> dict:
    """{'usd': gasto liquidado, 'reservado': importe apartado y aún sin liquidar}."""
    if COST_FILE.exists():
        try:
            d = json.loads(COST_FILE.read_text(encoding="utf-8"))
            if d.get("date") == _hoy():
                return {"usd": float(d.get("usd", 0) or 0),
                        "reservado": float(d.get("reservado", 0) or 0)}
        except Exception:
            pass
    return {"usd": 0.0, "reservado": 0.0}


def _guardar_estado(estado: dict) -> None:
    escribir_atomico(COST_FILE, json.dumps({
        "date": _hoy(),
        "usd": round(float(estado.get("usd", 0)), 6),
        "reservado": round(max(0.0, float(estado.get("reservado", 0))), 6),
    }))


def _load_daily() -> float:
    """Gasto del día en USD: liquidado + reservado. Lo reservado ya cuenta contra
    el techo — si no, dos procesos se autorizan el mismo hueco."""
    e = _leer_estado()
    return e["usd"] + e["reservado"]


def _reservar(usd_estimado: float) -> float:
    """Aparta presupuesto ANTES de llamar. Lanza RuntimeError si no cabe.

    Comprobar y gastar iban por separado, con un `threading.Lock` que no protege
    entre procesos: el CLI y el panel escriben el MISMO `.kaizen_cost.json`, así
    que ambos leían el mismo total, ambos decidían que cabía y ambos gastaban —
    perdiendo además gasto por last-writer-wins (auditoría 2026-08-02, B-03).
    """
    with _cost_lock, bloqueo_exclusivo(COST_FILE):
        estado = _leer_estado()
        eur = (estado["usd"] + estado["reservado"] + usd_estimado) * EUR_PER_USD
        if eur > DAILY_BUDGET_EUR:
            raise RuntimeError(
                f"Límite diario alcanzado ({eur:.2f}€ / {DAILY_BUDGET_EUR:.2f}€ "
                f"incluyendo la estimación de esta llamada). Sistema detenido hasta mañana.")
        estado["reservado"] += usd_estimado
        _guardar_estado(estado)
        return usd_estimado


def _liquidar(usd_reservado: float, usd_real: float) -> None:
    """Cierra la reserva con el coste real."""
    with _cost_lock, bloqueo_exclusivo(COST_FILE):
        estado = _leer_estado()
        estado["reservado"] = max(0.0, estado["reservado"] - usd_reservado)
        estado["usd"] += usd_real
        _guardar_estado(estado)


def _liberar(usd_reservado: float) -> None:
    """Devuelve la reserva: la llamada no llegó a hacerse."""
    with _cost_lock, bloqueo_exclusivo(COST_FILE):
        estado = _leer_estado()
        estado["reservado"] = max(0.0, estado["reservado"] - usd_reservado)
        _guardar_estado(estado)


def estimar_usd(model: str, messages: list, system: str | None, max_tokens: int) -> float:
    """Estimación CONSERVADORA: ~4 caracteres por token de entrada y `max_tokens`
    de salida (el peor caso, que es lo que hay que reservar)."""
    texto = (system or "") + "".join(
        str(m.get("content", "")) if isinstance(m, dict) else str(m) for m in (messages or []))
    r = RATES.get(model, _TARIFA_DESCONOCIDA)
    return ((len(texto) / 4.0) * r["in"] + float(max_tokens) * r["out"]) / 1_000_000


def session_cost_eur() -> float:
    return _session_usd * EUR_PER_USD


def daily_cost_eur() -> float:
    return _load_daily() * EUR_PER_USD


def budget_status() -> tuple[bool, str | None]:
    """Devuelve (ok, aviso). Lanza RuntimeError si se superó el límite."""
    eur = daily_cost_eur()
    pct = eur / DAILY_BUDGET_EUR
    if pct >= 1.0:
        raise RuntimeError(
            f"Límite diario alcanzado ({eur:.2f}€ / {DAILY_BUDGET_EUR:.2f}€). "
            "Sistema detenido hasta mañana."
        )
    if pct >= 0.8:
        return True, f"⚠  Alerta: {pct*100:.0f}% del límite diario ({eur:.2f}€ / {DAILY_BUDGET_EUR:.2f}€)"
    if pct >= 0.5:
        return True, f"⚡ {pct*100:.0f}% del límite diario usado ({eur:.2f}€)"
    return True, None


def chat(
    messages: list,
    *,
    model: str = "claude-haiku-4-5-20251001",
    system: str | None = None,
    max_tokens: int = 2048,
    company: str = "default",
    temperature: float | None = None,
) -> str:
    """Llama a Claude, registra el coste y devuelve el texto de respuesta.

    `temperature` es opcional para no romper a los llamadores existentes. El comité de
    OpenGravity (tesis §6.2) lo fija a 0 desde el registro de roles: un comité para
    detectar alucinaciones que corre a temperatura alta es contradictorio.
    """
    global _session_usd

    kw: dict = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system:
        kw["system"] = system
    if temperature is not None:
        kw["temperature"] = temperature

    # Reserva ANTES de llamar (hard stop atómico entre procesos); se liquida con
    # el coste real al volver y se libera si la llamada no llega a hacerse.
    reservado = _reservar(estimar_usd(model, messages, system, max_tokens))
    try:
        resp = _client().messages.create(**kw)
    except BaseException:
        _liberar(reservado)
        raise

    tok_in  = resp.usage.input_tokens
    tok_out = resp.usage.output_tokens
    r = RATES.get(model, _TARIFA_DESCONOCIDA)
    cost_usd = (tok_in * r["in"] + tok_out * r["out"]) / 1_000_000

    _liquidar(reservado, cost_usd)
    with _cost_lock:
        _session_usd += cost_usd
    _emit_cost(model, cost_usd, tok_in, tok_out, company)

    return _text_de(resp)


def _text_de(resp) -> str:
    """Extrae el texto de la respuesta sin asumir que content[0] existe y es texto.
    Una respuesta vacía o con un bloque no-texto (p. ej. tool_use) ya no provoca
    IndexError/AttributeError; devuelve "" para que el llamador lo gestione."""
    for bloque in getattr(resp, "content", None) or []:
        if getattr(bloque, "type", None) == "text":
            return bloque.text
    return ""
