"""Herramientas de consulta de Finanzas (Fase 1.3).

Cálculos deterministas (sin LLM) sobre los nodos `Gasto` de la memoria de conocimiento.
El agente conversacional las orquesta; los números salen de aquí, no del modelo.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from core.knowledge import KnowledgeStore


def _gastos(knowledge: KnowledgeStore, company: str) -> list[dict]:
    return list(knowledge.all(company, "gasto").values())


def _dt(ts: str) -> datetime:
    d = datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _en_periodo(ts: str, periodo: str, ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now(timezone.utc)
    t = _dt(ts)
    if periodo == "todo":
        return True
    if periodo == "hoy":
        return t.date() == ahora.date()
    if periodo == "semana":
        return t >= ahora - timedelta(days=7)
    if periodo == "semana_anterior":   # ventana disjunta de "semana", para comparaciones homólogas
        return ahora - timedelta(days=14) <= t < ahora - timedelta(days=7)
    if periodo == "mes":
        return (t.year, t.month) == (ahora.year, ahora.month)
    return True


def consultar_gasto(knowledge, company: str, periodo: str = "mes",
                    categoria: str | None = None) -> dict:
    gs = [g for g in _gastos(knowledge, company) if _en_periodo(g["ts"], periodo)]
    if categoria:
        gs = [g for g in gs if g.get("categoria") == categoria]
    desglose: dict[str, float] = {}
    for g in gs:
        desglose[g["modelo"]] = round(desglose.get(g["modelo"], 0) + g["eur"], 6)
    return {
        "total_eur": round(sum(g["eur"] for g in gs), 6),
        "total_usd": round(sum(g["usd"] for g in gs), 6),
        "n_acciones": len(gs),
        "desglose_por_modelo": desglose,
    }


def proyectar_quema(knowledge, company: str, dias: int = 30,
                    presupuesto_mensual: float | None = None) -> dict:
    gs = _gastos(knowledge, company)
    if not gs:
        return {"gasto_diario_medio": 0.0, "dias_proyectados": 0.0, "dias_runway_si_no_recargas": None}
    fechas = sorted(_dt(g["ts"]) for g in gs)
    span_dias = max((fechas[-1] - fechas[0]).days + 1, 1)
    total = sum(g["eur"] for g in gs)
    diario = total / span_dias
    runway = None
    if presupuesto_mensual:
        gastado_mes = consultar_gasto(knowledge, company, "mes")["total_eur"]
        restante = presupuesto_mensual - gastado_mes
        runway = round(restante / diario, 1) if diario > 0 else None
    return {
        "gasto_diario_medio": round(diario, 6),
        "dias_proyectados": round(diario * dias, 6),
        "dias_runway_si_no_recargas": runway,
    }


def comparar_periodos(knowledge, company: str, p1: str, p2: str) -> dict:
    t1 = consultar_gasto(knowledge, company, p1)["total_eur"]
    t2 = consultar_gasto(knowledge, company, p2)["total_eur"]
    variacion = round((t2 - t1) / t1 * 100, 1) if t1 else None
    return {"p1_total": t1, "p2_total": t2, "variacion_pct": variacion}


def top_acciones_caras(knowledge, company: str, n: int = 5, periodo: str = "semana") -> list[dict]:
    gs = [g for g in _gastos(knowledge, company) if _en_periodo(g["ts"], periodo)]
    gs.sort(key=lambda g: g["eur"], reverse=True)
    return [{"accion": g["accion"], "eur": g["eur"], "timestamp": g["ts"]} for g in gs[:n]]


def detectar_anomalia(knowledge, company: str, sensibilidad: float = 3.0) -> list[dict]:
    """Anomalía simple: gasto que supera la media + sensibilidad * desviación estándar."""
    gs = _gastos(knowledge, company)
    if len(gs) < 3:
        return []
    valores = [g["eur"] for g in gs]
    media = statistics.mean(valores)
    sd = statistics.pstdev(valores)
    if sd == 0:
        return []
    umbral = media + sensibilidad * sd
    return [
        {"tipo": "gasto_atipico", "descripcion": f"{g['accion']} ({g['eur']:.4f}€) supera el umbral {umbral:.4f}€",
         "eur": g["eur"], "timestamp": g["ts"]}
        for g in gs if g["eur"] > umbral
    ]
