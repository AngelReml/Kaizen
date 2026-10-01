"""Rendimiento por cubo y grado del director (experto, mejor del mes).

Funciones PURAS: reciben datos ya leidos y devuelven el rendimiento. No leen disco, no escriben,
no inventan: si no hay muestra suficiente el grado es `None` y el motivo lo dice.

Convencion (constantes de abajo; se cambian aqui y en docs/CONTRATO_MUNDO.md):
  * Solo opta quien lleva de alta >= DIAS_ALTA_MIN dias.
  * Comercial y Marketing tienen dinero medible: ROI = valor atribuido 30 d / coste 30 d (pedidos
    ATRIBUIDOS con importe; los pendientes de validacion NO cuentan). Comercial cuenta todos los
    pedidos; Marketing solo los que vienen de un lead con fuente CAMPANA (cadena R-15), asi que
    su valor es un SUBCONJUNTO del de Comercial (el mismo pedido suma en los dos cubos: es lo que
    significa «lo trajo una campana» y «lo cerro Comercial»). El coste de Marketing suma lo que
    cuesta operar el cubo y el gasto de canal reportado en las metricas de sus campanas (30 d).
    Sin valor o sin coste, cae a la metrica de decisiones.
  * Los demas cubos: tasa de acierto = decisiones firmes / (firmes + rechazadas) en 30 d, con
    un minimo de DECISIONES_MIN. Firmes = APROBADA, EJECUTANDO, EJECUTADA; rechazadas =
    DENEGADA, REVOCADA. PENDIENTE, ANULADA y CADUCADA no cuentan.
  * puntuacion = metrica / umbral. Experto si puntuacion >= 1. Mejor del mes: el experto de
    mayor puntuacion (uno solo por empresa; un empate a puntuacion no da a nadie).
  * Puntuaciones de ROI y de acierto no son la misma unidad: es una convencion de comparacion
    por umbral, no una medida universal. Esta dicho en el contrato.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

VENTANA_DIAS = 30
DIAS_ALTA_MIN = 30
ROI_EXPERTO = 2.0          # cada euro gastado devuelve al menos 2 de valor atribuido
ACIERTO_EXPERTO = 0.90
DECISIONES_MIN = 5
FIRMES = ("APROBADA", "EJECUTANDO", "EJECUTADA", "EN_MANOS", "HECHA")
RECHAZADAS = ("DENEGADA", "REVOCADA")
CUBOS_CON_DINERO = ("comercial", "marketing")


def _ts(v) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _en_ventana(v, desde: datetime) -> bool:
    d = _ts(v)
    return d is not None and d >= desde


def valor_de_campanas(leads: list[dict], pedidos: list[dict], ahora: datetime | None = None) -> float:
    """Valor (importe bruto) de los pedidos ATRIBUIDOS de los ultimos 30 d cuyo lead tiene una fuente de tipo CAMPANA."""
    desde = (ahora or datetime.now(timezone.utc)) - timedelta(days=VENTANA_DIAS)
    de_campana = {l.get("id") for l in leads if any(f.get("tipo") == "CAMPANA" for f in (l.get("fuentes") or []))}
    return sum(float(p.get("importe_bruto") or 0) for p in pedidos
               if p.get("estado") == "ATRIBUIDO" and p.get("lead_ref") in de_campana and _en_ventana(p.get("ts"), desde))


def rendimiento_desde(cubos: list[dict], costes: list[dict], pedidos: list[dict],
                      aprobaciones: list[dict], ahora: datetime | None = None, *,
                      valor_cubo: dict | None = None, coste_extra: dict | None = None) -> dict[str, dict]:
    """`cubos`: [{cubo, alta, ts_alta}]; `costes`: [{cubo, ts, coste_eur}];
    `pedidos`: nodos pedido_atribuido; `aprobaciones`: nodos de la cola. Devuelve {cubo: rendimiento}."""
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(days=VENTANA_DIAS)
    coste: dict[str, float] = {}
    for c in costes:
        if _en_ventana(c.get("ts"), desde):
            coste[c.get("cubo", "")] = coste.get(c.get("cubo", ""), 0.0) + float(c.get("coste_eur") or 0)
    valor = sum(float(p.get("importe_bruto") or 0) for p in pedidos
                if p.get("estado") == "ATRIBUIDO" and _en_ventana(p.get("ts"), desde))
    vcubo = {"comercial": valor}
    vcubo.update(valor_cubo or {})
    for k_, v_ in (coste_extra or {}).items():
        coste[k_] = coste.get(k_, 0.0) + float(v_ or 0)
    firmes: dict[str, int] = {}
    rech: dict[str, int] = {}
    for n in aprobaciones:
        if not _en_ventana(n.get("decidida_en") or n.get("creada_en"), desde):
            continue
        k = n.get("cubo", "")
        if n.get("estado") in FIRMES:
            firmes[k] = firmes.get(k, 0) + 1
        elif n.get("estado") in RECHAZADAS:
            rech[k] = rech.get(k, 0) + 1

    out: dict[str, dict] = {}
    for c in cubos:
        k = c["cubo"]
        f, r = firmes.get(k, 0), rech.get(k, 0)
        base = {"rango": None, "metrica": None, "puntuacion": None, "coste_eur": round(coste.get(k, 0.0), 4),
                "valor_eur": None, "roi": None, "decisiones": {"firmes": f, "rechazadas": r},
                "tasa_acierto": round(f / (f + r), 3) if f + r else None, "motivo": ""}
        out[k] = base
        alta = _ts(c.get("ts_alta")) if c.get("alta") else None
        if alta is None:
            base["motivo"] = "sin dar de alta"
            continue
        if ahora - alta < timedelta(days=DIAS_ALTA_MIN):
            base["motivo"] = f"lleva de alta menos de {DIAS_ALTA_MIN} dias"
            continue
        if k in CUBOS_CON_DINERO and coste.get(k, 0) > 0 and vcubo.get(k, 0) > 0:
            base.update(metrica="roi", valor_eur=round(vcubo[k], 2), roi=round(vcubo[k] / coste[k], 3))
            base["puntuacion"] = round(base["roi"] / ROI_EXPERTO, 3)
        elif f + r >= DECISIONES_MIN:
            base["metrica"] = "acierto"
            base["puntuacion"] = round(base["tasa_acierto"] / ACIERTO_EXPERTO, 3)
        else:
            base["motivo"] = (f"muestra insuficiente: {f + r} decisiones en {VENTANA_DIAS} dias "
                              f"(minimo {DECISIONES_MIN})" + ("" if k not in CUBOS_CON_DINERO else " y sin ROI medible"))
            continue
        if base["puntuacion"] >= 1:
            base["rango"] = "experto"
            base["motivo"] = "supera el umbral de su metrica"
        else:
            base["motivo"] = "por debajo del umbral de experto"
    expertos = sorted(((v["puntuacion"], k) for k, v in out.items() if v["rango"] == "experto"), reverse=True)
    if expertos and (len(expertos) == 1 or expertos[0][0] > expertos[1][0]):
        top = out[expertos[0][1]]
        top["rango"] = "mejor_mes"
        top["motivo"] = "el experto de mayor puntuacion del mes"
    return out
