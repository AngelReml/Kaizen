"""Herramientas deterministas de Inteligencia de Mercado / Estrategia (tesis §3.8).

Estado propio (knowledge), aislado por empresa:
  "senal_mercado" — señales observadas del exterior: movimientos de competencia, precios,
                    tendencias, conversaciones de clientes recogidas por Customer Success.

La síntesis en recomendaciones accionables (Strategic Advisor) usa LLM en el especialista;
aquí vive la agregación y la detección de señales débiles, auditable.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone, timedelta

TIPOS_SENAL = ("competidor", "precio", "tendencia", "conversacion", "regulatorio")
RELEVANCIA_ALERTA = 4         # relevancia >= 4 (de 5) dispara alerta de competencia
VENTANA_TENDENCIA_DIAS = 30
MIN_REPETICIONES_TENDENCIA = 3


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def registrar_senal(knowledge, company: str, *, tipo: str, tema: str, fuente: str = "",
                    relevancia: int = 3, detalle: str = "") -> dict:
    sid = uuid.uuid4().hex[:12]
    senal = {"id": sid, "tipo": tipo if tipo in TIPOS_SENAL else "tendencia",
             "tema": tema, "fuente": fuente, "relevancia": max(1, min(5, int(relevancia))),
             "detalle": detalle, "ts": _iso()}
    knowledge.add(company, "senal_mercado", sid, senal)
    return senal


def senales(knowledge, company: str, *, tipo: str | None = None) -> list[dict]:
    items = list(knowledge.all(company, "senal_mercado").values())
    if tipo:
        items = [s for s in items if s.get("tipo") == tipo]
    return sorted(items, key=lambda s: s.get("ts", ""), reverse=True)


def alertas_competencia(knowledge, company: str) -> list[dict]:
    """Movimientos de competencia relevantes que merecen atención del operador."""
    return [s for s in senales(knowledge, company, tipo="competidor")
            if s.get("relevancia", 0) >= RELEVANCIA_ALERTA]


def detectar_tendencias(knowledge, company: str) -> list[dict]:
    """Señales débiles: temas que se repiten en la ventana reciente (antes de ser obvios)."""
    corte = datetime.now(timezone.utc) - timedelta(days=VENTANA_TENDENCIA_DIAS)
    recientes = []
    for s in senales(knowledge, company):
        try:
            if datetime.fromisoformat(s["ts"]) >= corte:
                recientes.append(s)
        except (ValueError, KeyError):
            continue
    # Agrupa por palabra clave del tema (primera palabra significativa).
    conteo = Counter()
    ejemplos: dict[str, str] = {}
    for s in recientes:
        clave = (s.get("tema", "").lower().split() or ["?"])[0]
        conteo[clave] += 1
        ejemplos.setdefault(clave, s.get("tema", ""))
    return [{"tema": ejemplos[k], "repeticiones": n}
            for k, n in conteo.most_common() if n >= MIN_REPETICIONES_TENDENCIA]


def material_briefing(knowledge, company: str) -> dict:
    """Reúne el material crudo para el briefing del Strategic Advisor."""
    return {"alertas_competencia": alertas_competencia(knowledge, company),
            "tendencias": detectar_tendencias(knowledge, company),
            "n_senales": len(senales(knowledge, company))}
