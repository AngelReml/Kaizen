"""Tests de la consulta natural (Módulo 6)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from core.consulta_natural import (
    ConsultaNatural, Consulta, FiltroConsulta,
    CAMPOS_CONSULTABLES, TIPOS_RESPUESTA,
    _aplicar_filtro,
)
from core.lead_schema import (
    LeadDoc, Ubicacion, Contacto, Interaccion, Compromiso, PoliticaReintentos,
)


CLOCK = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)


def _lead(**kw) -> LeadDoc:
    base = dict(
        id="lead_X",
        company="laboratorio",
        nombre="Test Lead",
        categoria_icp="panaderia_pasteleria",
        prioridad_icp="ALTA",
        anillo=0,
        estado_pipeline="cold",
        ubicacion=Ubicacion(direccion="Calle X, 30001 Murcia"),
        contacto=Contacto(telefono="+34666000000"),
        interacciones=[],
        compromisos=[],
        reintentos=PoliticaReintentos(intentos_realizados=0, max_intentos=3),
        do_not_call=False,
        tipo_detectado="restaurante",
    )
    base.update(kw)
    return LeadDoc(**base)


def _stub_chat(salida: str):
    def _chat(messages, **kwargs):
        return salida
    return _chat


# --- Parser puro ----------------------------------------------------------

def test_parser_acepta_json_limpio():
    salida = json.dumps({
        "filtros": [{"campo": "estado_pipeline", "op": "eq", "valor": "queued"}],
        "tipo_respuesta": "count", "limite": 20, "agrupar_por": None,
    })
    c = ConsultaNatural._parsear_consulta(salida)
    assert c.error == ""
    assert len(c.filtros) == 1
    assert c.filtros[0].campo == "estado_pipeline"
    assert c.tipo_respuesta == "count"


def test_parser_descarta_campo_inventado():
    salida = json.dumps({
        "filtros": [
            {"campo": "campo_inventado", "op": "eq", "valor": "x"},
            {"campo": "estado_pipeline", "op": "eq", "valor": "queued"}],
        "tipo_respuesta": "count",
    })
    c = ConsultaNatural._parsear_consulta(salida)
    assert len(c.filtros) == 1
    assert c.filtros[0].campo == "estado_pipeline"


def test_parser_descarta_operador_invalido():
    """`contains` no es válido para `do_not_call` (solo eq)."""
    salida = json.dumps({
        "filtros": [{"campo": "do_not_call", "op": "contains", "valor": True}],
        "tipo_respuesta": "count",
    })
    c = ConsultaNatural._parsear_consulta(salida)
    assert len(c.filtros) == 0


def test_parser_acepta_error_explicito_llm():
    salida = json.dumps({"error": "no_interpretable", "razon": "pregunta abstracta"})
    c = ConsultaNatural._parsear_consulta(salida)
    assert "no_interpretable" in c.error


def test_parser_json_invalido():
    c = ConsultaNatural._parsear_consulta("blablabla sin json")
    assert c.error.startswith("no_json")


def test_parser_tolera_markdown():
    salida = '```json\n{"filtros":[],"tipo_respuesta":"summary","agrupar_por":"estado_pipeline"}\n```'
    c = ConsultaNatural._parsear_consulta(salida)
    assert c.tipo_respuesta == "summary"
    assert c.agrupar_por == "estado_pipeline"


def test_parser_tipo_invalido_cae_a_count():
    salida = json.dumps({"filtros": [], "tipo_respuesta": "ranking"})
    c = ConsultaNatural._parsear_consulta(salida)
    assert c.tipo_respuesta == "count"


# --- Aplicador filtros sobre lead --------------------------------------------

def test_filtro_estado_pipeline_eq():
    lead = _lead(estado_pipeline="queued")
    f = FiltroConsulta("estado_pipeline", "eq", "queued")
    assert _aplicar_filtro(lead, f, CLOCK) is True
    f = FiltroConsulta("estado_pipeline", "eq", "cold")
    assert _aplicar_filtro(lead, f, CLOCK) is False


def test_filtro_categoria_contains():
    lead = _lead(categoria_icp="hotel_boutique_con_desayuno")
    f = FiltroConsulta("categoria_icp", "contains", "hotel")
    assert _aplicar_filtro(lead, f, CLOCK) is True


def test_filtro_intentos_gte():
    lead = _lead(reintentos=PoliticaReintentos(intentos_realizados=3, max_intentos=5))
    assert _aplicar_filtro(lead, FiltroConsulta("intentos_realizados", "gte", 2), CLOCK)
    assert not _aplicar_filtro(lead, FiltroConsulta("intentos_realizados", "gte", 5), CLOCK)


def test_filtro_ciudad_contains():
    lead = _lead(ubicacion=Ubicacion(direccion="C. Real 12, 30550 Abarán, Murcia"))
    assert _aplicar_filtro(lead, FiltroConsulta("ciudad", "contains", "Murcia"), CLOCK)


def test_filtro_do_not_call():
    lead = _lead(do_not_call=True)
    assert _aplicar_filtro(lead, FiltroConsulta("do_not_call", "eq", True), CLOCK)
    assert not _aplicar_filtro(lead, FiltroConsulta("do_not_call", "eq", False), CLOCK)


def test_filtro_tiene_compromiso_tipo():
    lead = _lead(compromisos=[
        Compromiso(id="c1", tipo="callback", cumplido=False),
        Compromiso(id="c2", tipo="muestra", cumplido=True),
    ])
    assert _aplicar_filtro(lead, FiltroConsulta("tiene_compromiso", "tiene", "callback"), CLOCK)
    # muestra está cumplido → no pendiente
    assert not _aplicar_filtro(lead, FiltroConsulta("tiene_compromiso", "tiene", "muestra"), CLOCK)
    # cualquiera pendiente
    assert _aplicar_filtro(lead, FiltroConsulta("tiene_compromiso", "tiene", "*"), CLOCK)


def test_filtro_tiene_compromiso_sin_compromisos():
    lead = _lead(compromisos=[])
    assert not _aplicar_filtro(lead, FiltroConsulta("tiene_compromiso", "tiene", "*"), CLOCK)


def test_filtro_dias_desde_ultima_interaccion_gte():
    # interacción hace 10 días
    lead = _lead(interacciones=[Interaccion(
        ts="2026-05-17T12:00:00+00:00", tipo="llamada", resultado="no_answer")])
    assert _aplicar_filtro(lead,
        FiltroConsulta("dias_desde_ultima_interaccion", "gte", 5), CLOCK)
    assert not _aplicar_filtro(lead,
        FiltroConsulta("dias_desde_ultima_interaccion", "gte", 15), CLOCK)


def test_filtro_dias_sin_interacciones_no_pasa():
    lead = _lead(interacciones=[])
    assert not _aplicar_filtro(lead,
        FiltroConsulta("dias_desde_ultima_interaccion", "gte", 0), CLOCK)


# --- Pipeline aplicar() ----------------------------------------------------

def _nlq():
    return ConsultaNatural(clock=lambda: CLOCK)


def test_aplicar_count():
    leads = [_lead(estado_pipeline="queued"), _lead(estado_pipeline="cold"),
             _lead(estado_pipeline="queued")]
    consulta = Consulta(
        filtros=[FiltroConsulta("estado_pipeline", "eq", "queued")],
        tipo_respuesta="count")
    out = _nlq().aplicar(consulta, leads)
    assert out["tipo"] == "count"
    assert out["total"] == 2


def test_aplicar_list_respeta_limite():
    leads = [_lead(id=f"L{i}", estado_pipeline="cold") for i in range(50)]
    consulta = Consulta(filtros=[], tipo_respuesta="list", limite=5)
    out = _nlq().aplicar(consulta, leads)
    assert out["total"] == 50
    assert len(out["items"]) == 5


def test_aplicar_summary_groupby():
    leads = [_lead(id="A", estado_pipeline="cold"),
             _lead(id="B", estado_pipeline="cold"),
             _lead(id="C", estado_pipeline="queued"),
             _lead(id="D", estado_pipeline="customer")]
    consulta = Consulta(filtros=[], tipo_respuesta="summary",
                        agrupar_por="estado_pipeline")
    out = _nlq().aplicar(consulta, leads)
    assert out["tipo"] == "summary"
    assert out["buckets"]["cold"] == 2
    assert out["buckets"]["queued"] == 1
    assert out["buckets"]["customer"] == 1


def test_aplicar_filtros_encadenados_son_AND():
    leads = [
        _lead(id="A", estado_pipeline="queued", categoria_icp="hotel_boutique_con_desayuno"),
        _lead(id="B", estado_pipeline="queued", categoria_icp="panaderia_pasteleria"),
        _lead(id="C", estado_pipeline="cold", categoria_icp="hotel_boutique_con_desayuno"),
    ]
    consulta = Consulta(filtros=[
        FiltroConsulta("estado_pipeline", "eq", "queued"),
        FiltroConsulta("categoria_icp", "contains", "hotel"),
    ], tipo_respuesta="count")
    out = _nlq().aplicar(consulta, leads)
    assert out["total"] == 1


# --- Pipeline completo con chat mock --------------------------------------

def test_responder_pipeline_completo():
    salida = json.dumps({
        "filtros": [{"campo": "estado_pipeline", "op": "eq", "valor": "queued"}],
        "tipo_respuesta": "count", "limite": 20, "agrupar_por": None,
    })
    leads = [_lead(estado_pipeline="queued"), _lead(estado_pipeline="cold")]
    nlq = ConsultaNatural(chat=_stub_chat(salida), clock=lambda: CLOCK)
    out = nlq.responder("¿cuántos en queued?", leads=leads)
    assert "Total: 1" in out


def test_responder_pregunta_vacia():
    nlq = ConsultaNatural(chat=_stub_chat("{}"))
    out = nlq.responder("", leads=[])
    assert "❌" in out


def test_responder_sin_loader_y_sin_leads_da_error():
    nlq = ConsultaNatural(
        chat=_stub_chat(json.dumps({"filtros": [], "tipo_respuesta": "count"})))
    out = nlq.responder("¿cuántos leads tengo?")
    assert "knowledge_loader" in out


def test_formatear_summary():
    res = {"tipo": "summary", "agrupar_por": "estado_pipeline", "total": 5,
           "buckets": {"cold": 3, "queued": 2}}
    nlq = ConsultaNatural()
    out = nlq.formatear(res, Consulta(tipo_respuesta="summary",
                                       agrupar_por="estado_pipeline"))
    assert "estado_pipeline" in out
    assert "cold: 3" in out
    assert "queued: 2" in out


# --- Schema invariants ----------------------------------------------------

def test_campos_consultables_son_los_esperados():
    assert "estado_pipeline" in CAMPOS_CONSULTABLES
    assert "tiene_compromiso" in CAMPOS_CONSULTABLES
    assert "dias_desde_ultima_interaccion" in CAMPOS_CONSULTABLES
    assert "ciudad" in CAMPOS_CONSULTABLES
    assert TIPOS_RESPUESTA == {"count", "list", "summary"}


# --- Opt-in: LLM REAL ----

@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("KAIZEN_TEST_LLM_REAL")),
    reason="Requiere ANTHROPIC_API_KEY + KAIZEN_TEST_LLM_REAL=1",
)
def test_llm_real_pregunta_hoteles_queued():
    nlq = ConsultaNatural(clock=lambda: CLOCK)
    consulta = nlq.interpretar("¿cuántos hoteles boutique tengo en queued?")
    assert consulta.error == "", f"esperaba consulta limpia, salió: {consulta}"
    assert consulta.tipo_respuesta == "count"
    campos = {f.campo for f in consulta.filtros}
    assert "categoria_icp" in campos or "tipo_detectado" in campos
    assert "estado_pipeline" in campos
