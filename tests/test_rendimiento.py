"""Rendimiento por cubo y grado: reglas puras, sin inventar."""
from datetime import datetime, timedelta, timezone

from panel_mando import rendimiento as R

AHORA = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
def iso(dias): return (AHORA - timedelta(days=dias)).isoformat()
def cubo(k, dias_alta=60, alta=True): return {"cubo": k, "alta": alta, "ts_alta": iso(dias_alta) if alta else None}
def nodos(k, firmes, rech): return [{"cubo": k, "estado": "EJECUTADA", "decidida_en": iso(3)}] * firmes + [{"cubo": k, "estado": "DENEGADA", "decidida_en": iso(3)}] * rech


def test_sin_datos_nadie_tiene_grado():
    r = R.rendimiento_desde([cubo("legal"), cubo("comercial")], [], [], [], AHORA)
    assert all(v["rango"] is None for v in r.values())
    assert "insuficiente" in r["legal"]["motivo"]


def test_no_opta_quien_lleva_poco_de_alta_ni_quien_no_esta_dado_de_alta():
    r = R.rendimiento_desde([cubo("legal", 5), cubo("qa", alta=False)], [], [], nodos("legal", 20, 0), AHORA)
    assert r["legal"]["rango"] is None and "menos de 30" in r["legal"]["motivo"]
    assert r["qa"]["motivo"] == "sin dar de alta"


def test_acierto_experto_y_umbral():
    r = R.rendimiento_desde([cubo("legal"), cubo("qa")], [], [], nodos("legal", 9, 1) + nodos("qa", 8, 2), AHORA)
    assert r["legal"]["rango"] == "mejor_mes" and r["legal"]["metrica"] == "acierto"   # 0,90 llega al umbral y es el unico experto
    assert r["qa"]["rango"] is None and "por debajo" in r["qa"]["motivo"]


def test_roi_solo_en_comercial_y_solo_con_pedidos_atribuidos():
    pedidos = [{"estado": "ATRIBUIDO", "importe_bruto": 1000, "ts": iso(2)},
               {"estado": "PENDIENTE_VALIDACION", "importe_bruto": 99999, "ts": iso(2)},      # no cuenta
               {"estado": "ATRIBUIDO", "importe_bruto": 5000, "ts": iso(90)}]                 # fuera de ventana
    costes = [{"cubo": "comercial", "ts": iso(1), "coste_eur": 100}, {"cubo": "marketing", "ts": iso(1), "coste_eur": 1}]
    r = R.rendimiento_desde([cubo("comercial"), cubo("marketing")], costes, pedidos, [], AHORA)
    assert r["comercial"]["roi"] == 10.0 and r["comercial"]["valor_eur"] == 1000.0 and r["comercial"]["rango"] == "mejor_mes"
    assert r["marketing"]["roi"] is None and r["marketing"]["rango"] is None


def test_mejor_del_mes_es_uno_y_el_empate_no_premia():
    ap = nodos("legal", 10, 0) + nodos("qa", 10, 0)
    r = R.rendimiento_desde([cubo("legal"), cubo("qa")], [], [], ap, AHORA)
    assert sorted(v["rango"] for v in r.values()) == ["experto", "experto"]                  # empate: nadie es «el mejor»
    r = R.rendimiento_desde([cubo("legal"), cubo("qa")], [], [], nodos("legal", 10, 0) + nodos("qa", 9, 1), AHORA)
    assert r["legal"]["rango"] == "mejor_mes" and r["qa"]["rango"] == "experto"


def test_pendientes_y_anuladas_no_cuentan_y_lo_viejo_tampoco():
    ap = [{"cubo": "legal", "estado": "PENDIENTE", "creada_en": iso(1)}] * 9 + [{"cubo": "legal", "estado": "ANULADA", "decidida_en": iso(1)}] * 9 \
        + [{"cubo": "legal", "estado": "EJECUTADA", "decidida_en": iso(80)}] * 9
    r = R.rendimiento_desde([cubo("legal")], [], [], ap, AHORA)
    assert r["legal"]["decisiones"] == {"firmes": 0, "rechazadas": 0} and r["legal"]["rango"] is None


def test_marketing_mide_roi_solo_con_pedidos_de_leads_de_campana():
    leads = [{"id": "a", "fuentes": [{"tipo": "CAMPANA", "ref": "c1"}]}, {"id": "b", "fuentes": [{"tipo": "WEB"}]}]
    pedidos = [{"estado": "ATRIBUIDO", "lead_ref": "a", "importe_bruto": 600, "ts": iso(2)},
               {"estado": "ATRIBUIDO", "lead_ref": "b", "importe_bruto": 9999, "ts": iso(2)},      # no vino de una campana
               {"estado": "PENDIENTE_VALIDACION", "lead_ref": "a", "importe_bruto": 5000, "ts": iso(2)}]
    v = R.valor_de_campanas(leads, pedidos, AHORA)
    assert v == 600
    r = R.rendimiento_desde([cubo("marketing"), cubo("comercial")], [{"cubo": "marketing", "ts": iso(1), "coste_eur": 50}], pedidos, [], AHORA,
                            valor_cubo={"marketing": v}, coste_extra={"marketing": 50})
    assert r["marketing"]["roi"] == 6.0 and r["marketing"]["coste_eur"] == 100.0      # 50 del cubo + 50 de canal
    assert r["comercial"]["roi"] is None                                              # sin coste propio no hay ROI inventado


def test_tarjetas_en_manos_y_hechas_cuentan_como_firmes():
    """Una tarjeta aprobada que pasa a las manos del operador (C1) sigue siendo un SI: no puede
    desaparecer del acierto del cubo."""
    from panel_mando import rendimiento as R
    assert {"EN_MANOS", "HECHA"} <= set(R.FIRMES)
