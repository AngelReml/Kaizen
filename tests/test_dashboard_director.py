"""Tests del Dashboard del Director Comercial (Módulo 7)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from departments.comercial.dashboard_director import (
    DashboardDirector, ORDEN_ESTADOS,
)
from core.lead_schema import (
    LeadDoc, Ubicacion, Contacto, Interaccion, Compromiso, PoliticaReintentos,
)


CLOCK = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)


def _lead(**kw) -> LeadDoc:
    base = dict(
        id="lead_X", company="laboratorio",
        nombre="Test Lead", categoria_icp="panaderia_pasteleria",
        estado_pipeline="cold",
        ubicacion=Ubicacion(direccion="Calle X, 30001 Murcia"),
        contacto=Contacto(telefono="+34666000000"),
        interacciones=[], compromisos=[],
        reintentos=PoliticaReintentos(intentos_realizados=0, max_intentos=3),
        do_not_call=False,
    )
    base.update(kw)
    return LeadDoc(**base)


def _dash(leads: list) -> DashboardDirector:
    return DashboardDirector(
        knowledge_loader=lambda: leads,
        empresa="laboratorio",
        clock=lambda: CLOCK,
    )


# --- datos_para_dashboard --------------------------------------------------

def test_buckets_pipeline_siempre_12_estados():
    leads = [_lead(estado_pipeline="cold")]
    d = _dash(leads).datos_para_dashboard()
    assert set(d["estado_pipeline"].keys()) == set(ORDEN_ESTADOS)
    assert len(d["estado_pipeline"]) == 12


def test_buckets_cuenta_correctamente():
    leads = [
        _lead(id="A", estado_pipeline="cold"),
        _lead(id="B", estado_pipeline="cold"),
        _lead(id="C", estado_pipeline="queued"),
        _lead(id="D", estado_pipeline="customer"),
    ]
    d = _dash(leads).datos_para_dashboard()
    assert d["estado_pipeline"]["cold"] == 2
    assert d["estado_pipeline"]["queued"] == 1
    assert d["estado_pipeline"]["customer"] == 1
    assert d["estado_pipeline"]["lost"] == 0
    assert d["total_leads"] == 4


def test_proximas_acciones_24h_filtro_correcto():
    # Próximas dentro de 24h: A (en 3h), B (en 25h - fuera), C (hace 1h - pasado)
    leads = [
        _lead(id="A", reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-27T15:00:00+00:00",  # +3h
            proxima_accion_tipo="llamar", intentos_realizados=1, max_intentos=3)),
        _lead(id="B", reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-28T13:00:00+00:00",  # +25h fuera
            proxima_accion_tipo="llamar", intentos_realizados=1, max_intentos=3)),
        _lead(id="C", reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-27T11:00:00+00:00",  # -1h pasado
            proxima_accion_tipo="llamar", intentos_realizados=1, max_intentos=3)),
    ]
    d = _dash(leads).datos_para_dashboard()
    ids = [p["lead_id"] for p in d["proximas_acciones_24h"]]
    assert ids == ["A"]


def test_proximas_acciones_ordenadas_por_ts():
    leads = [
        _lead(id="tarde", reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-27T18:00:00+00:00",
            proxima_accion_tipo="llamar", intentos_realizados=0, max_intentos=3)),
        _lead(id="pronto", reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-27T14:00:00+00:00",
            proxima_accion_tipo="llamar", intentos_realizados=0, max_intentos=3)),
    ]
    d = _dash(leads).datos_para_dashboard()
    ids = [p["lead_id"] for p in d["proximas_acciones_24h"]]
    assert ids == ["pronto", "tarde"]


def test_compromisos_proximos_vs_vencidos():
    leads = [
        _lead(id="prox", compromisos=[Compromiso(
            id="c1", tipo="callback",
            fecha_objetivo="2026-05-28T09:00:00+00:00", cumplido=False)]),
        _lead(id="venc", compromisos=[Compromiso(
            id="c2", tipo="muestra",
            fecha_objetivo="2026-05-20T09:00:00+00:00", cumplido=False)]),
        _lead(id="cumplido", compromisos=[Compromiso(
            id="c3", tipo="callback",
            fecha_objetivo="2026-05-25T09:00:00+00:00", cumplido=True)]),
    ]
    d = _dash(leads).datos_para_dashboard()
    prox_ids = [c["lead_id"] for c in d["compromisos_proximos"]]
    venc_ids = [c["lead_id"] for c in d["compromisos_vencidos"]]
    assert prox_ids == ["prox"]
    assert venc_ids == ["venc"]
    # Cumplidos no aparecen en ningún lado
    assert "cumplido" not in prox_ids and "cumplido" not in venc_ids


def test_interacciones_recientes_ventana_7_dias_y_orden_desc():
    leads = [
        _lead(id="A", interacciones=[Interaccion(
            ts="2026-05-26T18:00:00+00:00", tipo="llamada",
            resultado="contacted", duracion_s=89)]),
        _lead(id="B", interacciones=[Interaccion(
            ts="2026-05-25T10:00:00+00:00", tipo="llamada",
            resultado="no_answer", duracion_s=12)]),
        _lead(id="viejo", interacciones=[Interaccion(
            ts="2026-05-15T10:00:00+00:00", tipo="llamada",
            resultado="contacted", duracion_s=30)]),
    ]
    d = _dash(leads).datos_para_dashboard()
    ids = [i["lead_id"] for i in d["interacciones_recientes"]]
    # A más reciente que B; "viejo" fuera de ventana
    assert ids == ["A", "B"]


def test_embudo_calcula_tasas():
    leads = (
        [_lead(estado_pipeline="cold") for _ in range(100)] +
        [_lead(estado_pipeline="contacted") for _ in range(20)] +
        [_lead(estado_pipeline="engaged") for _ in range(10)] +
        [_lead(estado_pipeline="customer") for _ in range(2)]
    )
    d = _dash(leads).datos_para_dashboard()
    e = d["embudo"]
    # cold/queued/contacting/no_answer = 100
    assert e["cold"] == 100
    # contacted+engaged+sample_*+trial+customer = 20+10+2 = 32
    assert e["contacted_o_mas"] == 32
    # engaged+sample_*+trial+customer = 10+2 = 12
    assert e["engaged_o_mas"] == 12
    assert e["customer"] == 2
    # tasas
    assert e["tasa_contact"] == round(32 / 100, 3)
    assert e["tasa_engaged"] == round(12 / 32, 3)
    assert e["tasa_customer"] == round(2 / 12, 3)


def test_embudo_division_por_cero_da_0():
    leads = [_lead(estado_pipeline="cold") for _ in range(5)]
    d = _dash(leads).datos_para_dashboard()
    e = d["embudo"]
    assert e["tasa_engaged"] == 0.0
    assert e["tasa_customer"] == 0.0


def test_knowledge_vacio_no_crashea():
    d = _dash([]).datos_para_dashboard()
    assert d["total_leads"] == 0
    assert all(v == 0 for v in d["estado_pipeline"].values())
    assert d["proximas_acciones_24h"] == []
    assert d["compromisos_proximos"] == []
    assert d["compromisos_vencidos"] == []
    assert d["interacciones_recientes"] == []
    assert d["embudo"]["tasa_contact"] == 0.0


def test_lead_sin_reintentos_no_crashea():
    leads = [_lead(reintentos=None)]
    d = _dash(leads).datos_para_dashboard()
    assert d["proximas_acciones_24h"] == []


def test_proxima_accion_ts_invalida_se_ignora():
    leads = [_lead(reintentos=PoliticaReintentos(
        proxima_accion_ts="no es una fecha", proxima_accion_tipo="llamar",
        intentos_realizados=0, max_intentos=3))]
    d = _dash(leads).datos_para_dashboard()
    assert d["proximas_acciones_24h"] == []


# --- renderizar markdown ---------------------------------------------------

def test_renderizar_secciones_presentes():
    leads = [_lead(estado_pipeline="cold")]
    out = _dash(leads).renderizar()
    assert "Director Comercial" in out
    assert "Estado del pipeline" in out
    assert "Próximas acciones (24h)" in out
    assert "Compromisos pendientes" in out
    assert "vencidos" in out
    assert "Histórico reciente" in out
    assert "Embudo de conversión" in out


def test_renderizar_secciones_vacias_dicen_ninguno():
    leads = [_lead(estado_pipeline="cold")]
    out = _dash(leads).renderizar()
    # Lead sin compromisos ni interacciones ni proxima accion
    assert "_ninguna_" in out  # próximas acciones
    assert "_ninguno_" in out


def test_renderizar_con_datos_pinta_todo():
    leads = [_lead(
        id="lead_A", nombre="Hotel X",
        estado_pipeline="engaged",
        reintentos=PoliticaReintentos(
            proxima_accion_ts="2026-05-27T15:00:00+00:00",
            proxima_accion_tipo="llamar", intentos_realizados=1, max_intentos=3),
        compromisos=[Compromiso(id="c1", tipo="callback",
                                fecha_objetivo="2026-05-28T08:00:00+00:00",
                                tolerancia_min=60, contexto="Hablar con encargado")],
        interacciones=[Interaccion(
            ts="2026-05-26T18:00:00+00:00", tipo="llamada",
            resultado="contacted_no_decisor", duracion_s=89)],
    )]
    out = _dash(leads).renderizar()
    assert "Hotel X" in out
    assert "callback" in out
    assert "contacted_no_decisor" in out
    assert "89s" in out
    assert "Hablar con encargado" in out
