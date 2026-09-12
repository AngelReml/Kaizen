"""Reglas duras del departamento de Finanzas (Fase 1.2).

Cada regla es una función pura que devuelve (pasa: bool, motivo: str). Sin LLM.
Se integran en el Guardián central vía `como_regla_guardian`, inyectada como `reglas_extra`.
"""
from __future__ import annotations

from core.guardian import Action, Decision

# Topes de llamadas por minuto por modelo.
TOPES_RATE = {"sonnet": 10, "haiku": 30}
TECHO_COSTE_UNICO_EUR = 2.0


def gasto_diario_supera_porcentaje(eur_hoy: float, presupuesto_mensual: float,
                                   umbral: float = 0.8, dias_mes: int = 30) -> tuple[bool, str]:
    """Bloquea si el gasto del día supera `umbral` del límite diario (presupuesto/días)."""
    if presupuesto_mensual <= 0:
        return True, "sin presupuesto definido"
    limite_diario = presupuesto_mensual / dias_mes
    if eur_hoy > limite_diario * umbral:
        return False, (f"Gasto de hoy {eur_hoy:.2f}€ supera el {umbral*100:.0f}% del "
                       f"límite diario ({limite_diario:.2f}€)")
    return True, "ok"


def tasa_llamadas_por_minuto(modelo: str, llamadas_ultimo_minuto: int,
                             n_max: int | None = None) -> tuple[bool, str]:
    """Rate limit por modelo. Sonnet 10/min, Haiku 30/min (configurable)."""
    tope = n_max or next((v for k, v in TOPES_RATE.items() if k in modelo.lower()), 60)
    if llamadas_ultimo_minuto >= tope:
        return False, f"Rate limit: {llamadas_ultimo_minuto} llamadas/min para {modelo} (máx {tope})"
    return True, "ok"


def coste_unico_supera_techo(eur_estimado: float, techo: float = TECHO_COSTE_UNICO_EUR) -> tuple[bool, str]:
    """Cualquier acción con coste estimado > techo requiere aprobación humana."""
    if eur_estimado > techo:
        return False, f"Coste único {eur_estimado:.2f}€ supera el techo {techo:.2f}€; requiere aprobación humana"
    return True, "ok"


def como_regla_guardian(action: Action) -> tuple[Decision, str]:
    """Adaptador para inyectar las reglas de Finanzas en el Guardián central.

    Lee campos relevantes del payload de la acción. Mantiene a `core` sin depender de
    `departments` (la dependencia va en el sentido correcto: departamento -> core).
    """
    p = action.payload
    if "eur_estimado" in p:
        ok, motivo = coste_unico_supera_techo(float(p["eur_estimado"]))
        if not ok:
            return Decision.ESCALATED, motivo   # coste alto -> aprobación humana
    return Decision.APPROVED, "ok"
