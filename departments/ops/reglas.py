"""Reglas duras de Ops (Fase 5.2). Funciones puras (pasa: bool, motivo: str)."""
from __future__ import annotations


def capacidad_supera_umbral(ocupada_pct: float, umbral: float = 0.9) -> tuple[bool, str]:
    if ocupada_pct >= umbral:
        return False, f"Capacidad al {ocupada_pct*100:.0f}% (≥{umbral*100:.0f}%); alerta antes de aceptar más pedidos"
    return True, "ok"


def stock_bajo_seguridad(stock: float, seguridad: float) -> tuple[bool, str]:
    if stock < seguridad:
        return False, f"Stock {stock} por debajo del mínimo de seguridad {seguridad}"
    return True, "ok"
