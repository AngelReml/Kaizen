"""Autorizacion de gasto DELANTE de cada invocacion de especialista — R-05 (F2).

Auditoria 2026-07-20: `departments/base._chat` invocaba el LLM (hasta Opus) sin
comprobar presupuesto antes, y su coste solo se acumulaba en memoria; el tope de
16 EUR/dia no lo veia ni lo frenaba. Un bucle de especialistas podia gastar sin
limite. Esto cablea el hard-stop del sustrato (B4) al camino de los especialistas:

  - `autorizar_gasto(company, previsto_eur)` va DELANTE de cada invoke. Si el gasto
    del dia + lo previsto rebasa el tope, lanza `CosteNoAutorizado` y el invoke NO
    ocurre (CORRECCIONES R2: hard stop delante, nunca contabilidad posterior).
  - `registrar_gasto(...)` persiste el coste real en el MISMO ledger unico que leen
    el panel (R-07) y el hard-stop — no en un contador de memoria que nadie consulta.

El ledger es el `core.ledger.LedgerCoste` persistente. La ruta y el tope se toman
del entorno del operador; en tests sin configurar, el guardia queda INERTE (no rompe
la suite) — el operador real siempre lo tiene activo via .env.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from core.ledger import LedgerCoste

_RAIZ = Path(__file__).resolve().parent.parent
_lock = threading.Lock()
_ledger_singleton: LedgerCoste | None = None


class CosteNoAutorizado(RuntimeError):
    """Hard stop: el invoke previsto rebasaria el tope diario. NO se ejecuta (R-05/R2)."""


def _tope_diario_eur() -> float:
    try:
        return float(os.environ.get("LIMITE_COSTE_DIARIO_EUR", "16.0"))
    except ValueError:
        return 16.0


def _ruta_ledger() -> Path | None:
    """Ruta del ledger persistente. KAIZEN_LEDGER_PATH la fija; por defecto,
    state/coste/ledger.jsonl bajo la raiz del repo (misma que usa el panel)."""
    p = os.environ.get("KAIZEN_LEDGER_PATH")
    if p:
        return Path(p)
    from core.rutas import dir_state
    return dir_state() / "coste" / "ledger.jsonl"


def ledger() -> LedgerCoste:
    global _ledger_singleton
    with _lock:
        if _ledger_singleton is None:
            _ledger_singleton = LedgerCoste(_ruta_ledger(),
                                            legacy_json=_RAIZ / ".kaizen_cost.json")
        return _ledger_singleton


def _activo() -> bool:
    """El guardia solo frena si hay un tope y un ledger escribible/legible. En un
    entorno de test que no lo configura, queda inerte (fail-open explicito documentado)."""
    return os.environ.get("KAIZEN_AUTORIZACION_GASTO", "true").lower() == "true"


def autorizar_gasto(company: str, previsto_eur: float, *, tope_eur: float | None = None) -> dict:
    """DELANTE de cada invoke. Lanza CosteNoAutorizado si el dia + previsto rebasa el tope."""
    if not _activo():
        return {"permitido": True, "inerte": True}
    tope = tope_eur if tope_eur is not None else _tope_diario_eur()
    if tope <= 0:
        return {"permitido": True, "tope": tope}
    led = ledger()
    gasto = led.gasto_dia(company)
    if gasto + max(0.0, previsto_eur) > tope:
        raise CosteNoAutorizado(
            f"tope diario alcanzado: gasto {gasto:.4f} + previsto {previsto_eur:.4f} > "
            f"{tope:.2f} EUR. El especialista NO se invoca (hard stop delante, R-05).")
    # Control ADICIONAL: el freno por tenant no sustituye el agregado global (varios
    # tenants pequenos podrian, entre todos, rebasar el tope global sin que ninguno
    # individualmente lo rebase).
    gasto_global = led.gasto_global_dia()
    if gasto_global + max(0.0, previsto_eur) > tope:
        raise CosteNoAutorizado(
            f"tope diario GLOBAL alcanzado: gasto {gasto_global:.4f} + previsto "
            f"{previsto_eur:.4f} > {tope:.2f} EUR. El especialista NO se invoca "
            "(hard stop delante, R-05).")
    return {"permitido": True, "gasto_dia": gasto, "tope": tope}


def registrar_gasto(company: str, *, cubo: str, rol: str, modelo: str = "",
                    proveedor: str = "", coste_eur: float = 0.0,
                    clase: str = "ESTANDAR", causa_id: str | None = None) -> dict:
    """DESPUES del invoke: persiste el coste real en el ledger unico (lo ven panel + hard-stop)."""
    if not _activo():
        return {"registrado": False, "inerte": True}
    return ledger().asentar(company, cubo=cubo, rol=rol, clase=clase, proveedor=proveedor,
                            modelo=modelo, coste_eur=coste_eur, causa_id=causa_id)


def _reset_para_tests() -> None:                       # pragma: no cover
    global _ledger_singleton
    with _lock:
        _ledger_singleton = None
