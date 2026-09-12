"""Tests del generador de briefing pre-call (Módulo 5)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.briefing import (
    GeneradorBriefing,
    _ciudad_desde_direccion,
    _razon_llamada,
    _decisor_conocido,
)
from core.lead_schema import (
    LeadDoc, Ubicacion, Contacto, Interaccion, Compromiso, PoliticaReintentos,
)


def _lead(**kw) -> LeadDoc:
    """Helper con los nombres REALES del schema M1 (nombre, categoria_icp).

    `nombre_contacto` no es un campo del schema; se guarda en metadatos_extra
    (TODO en docs/TODO.md: añadir como campo de primera clase)."""
    nombre_contacto = kw.pop("nombre_contacto", "Lidia")
    metadatos_extra = kw.pop("metadatos_extra", None) or {}
    if nombre_contacto:
        metadatos_extra.setdefault("nombre_contacto", nombre_contacto)
    base = dict(
        id="lead_test_001",
        company="laboratorio",
        nombre="Repostería La Curva",
        categoria_icp="panaderia_pasteleria",
        estado_pipeline="cold",
        ubicacion=Ubicacion(direccion="Calle Mayor 12, 02660 Caudete, Albacete"),
        contacto=Contacto(telefono="+34666000000"),
        interacciones=[],
        compromisos=[],
        reintentos=PoliticaReintentos(intentos_realizados=0, max_intentos=3),
        do_not_call=False,
        metadatos_extra=metadatos_extra,
    )
    base.update(kw)
    return LeadDoc(**base)


# --- helpers puros ---------------------------------------------------------

def test_ciudad_desde_direccion_completa():
    assert _ciudad_desde_direccion("Calle Mayor 12, 02660 Caudete, Albacete") == "Albacete"


def test_ciudad_desde_direccion_solo_ciudad():
    assert _ciudad_desde_direccion("Caudete") == "Caudete"


def test_ciudad_desde_direccion_vacia():
    assert _ciudad_desde_direccion("") == ""
    assert _ciudad_desde_direccion(None) == ""


def test_ciudad_descarta_codigo_postal():
    assert _ciudad_desde_direccion("Calle X, 28001, Madrid") == "Madrid"


# --- razon_llamada ---------------------------------------------------------

def test_razon_lead_nuevo_es_primer_contacto():
    assert _razon_llamada(_lead()) == "primer_contacto"


def test_razon_callback_pendiente_gana():
    """Si hay compromiso de callback, es la razón aunque el estado sea otro."""
    lead = _lead(
        estado_pipeline="queued",
        compromisos=[Compromiso(id="c1", tipo="callback",
                                fecha_objetivo="2026-05-28T08:00:00+00:00",
                                cumplido=False)],
    )
    assert _razon_llamada(lead) == "callback_pactado"


def test_razon_callback_cumplido_no_cuenta():
    lead = _lead(
        estado_pipeline="queued",
        compromisos=[Compromiso(id="c1", tipo="callback", cumplido=True)],
        reintentos=PoliticaReintentos(intentos_realizados=1, max_intentos=3),
    )
    assert _razon_llamada(lead) == "reintento_no_answer"


def test_razon_engaged_es_cierre_muestra():
    assert _razon_llamada(_lead(estado_pipeline="engaged")) == "cierre_muestra"


def test_razon_customer_es_fidelizacion():
    assert _razon_llamada(_lead(estado_pipeline="customer")) == "fidelizacion"


def test_razon_no_answer_es_reintento():
    assert _razon_llamada(_lead(estado_pipeline="no_answer")) == "reintento_no_answer"


# --- decisor_conocido ------------------------------------------------------

def test_decisor_extrae_de_resumen():
    lead = _lead(interacciones=[
        Interaccion(ts="2026-05-26T18:00:00+00:00", tipo="llamada",
                    resumen_llm="Hablé con Lidia, dependienta. Pidió callback para "
                                "hablar con el encargado."),
    ])
    assert _decisor_conocido(lead) == "encargado"


def test_decisor_no_mencionado():
    lead = _lead(interacciones=[
        Interaccion(ts="2026-05-26T18:00:00+00:00", tipo="llamada",
                    resumen_llm="No respondió nadie."),
    ])
    assert _decisor_conocido(lead) == ""


def test_decisor_sin_interacciones():
    assert _decisor_conocido(_lead()) == ""


# --- dynamic_variables ----------------------------------------------------

def _brief():
    return GeneradorBriefing(
        empresa_meta={"nombre": "Repostería Laboratorio",
                      "producto_clave": "rollicos artesanos"},
        clock=lambda: datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
    )


def test_dynamic_vars_todos_strings():
    """Requisito CAI: todas las dynamic_variables deben ser strings."""
    lead = _lead(
        compromisos=[Compromiso(id="c1", tipo="callback",
                                fecha_objetivo="2026-05-28T08:00:00+00:00",
                                tolerancia_min=60)],
        reintentos=PoliticaReintentos(intentos_realizados=2, max_intentos=3),
    )
    v = _brief().generar_dynamic_variables(lead)
    for k, val in v.items():
        assert isinstance(val, str), f"{k} no es str: {type(val).__name__}"


def test_dynamic_vars_lead_nuevo():
    v = _brief().generar_dynamic_variables(_lead())
    assert v["nombre_lead"] == "Lidia"
    assert v["negocio"] == "Repostería La Curva"
    assert v["categoria"] == "panaderia_pasteleria"
    assert v["ciudad"] == "Albacete"
    assert v["intentos_previos"] == "0"
    assert v["razon_llamada"] == "primer_contacto"
    assert v["compromisos_pendientes"] == ""
    assert v["empresa_nombre"] == "Repostería Laboratorio"
    assert v["empresa_producto_clave"] == "rollicos artesanos"


def test_dynamic_vars_con_interaccion_y_compromiso():
    lead = _lead(
        estado_pipeline="queued",
        interacciones=[Interaccion(
            ts="2026-05-26T18:16:00+00:00",
            tipo="llamada", resultado="contacted_no_decisor",
            resumen_llm="Hablé con Lidia, dependienta. Pide callback con el encargado.",
            duracion_s=89,
        )],
        compromisos=[Compromiso(id="c1", tipo="callback",
                                fecha_objetivo="2026-05-28T08:00:00+00:00",
                                tolerancia_min=60, contexto="callback Lidia")],
        reintentos=PoliticaReintentos(intentos_realizados=1, max_intentos=3),
    )
    v = _brief().generar_dynamic_variables(lead)
    assert v["razon_llamada"] == "callback_pactado"
    assert v["intentos_previos"] == "1"
    assert "callback" in v["compromisos_pendientes"]
    assert "2026-05-28" in v["compromisos_pendientes"]
    assert "Madrid" in v["compromisos_pendientes"]
    assert "Lidia" in v["ultima_interaccion_resumen"]
    assert v["ultima_interaccion_dias_atras"] == "0"  # clock dice 12:00, inter 18:00 → -1 día → 0 floor
    assert v["decisor_conocido"] == "encargado"


def test_dynamic_vars_sin_empresa_meta_no_crashea():
    brief = GeneradorBriefing(empresa_meta=None)
    v = brief.generar_dynamic_variables(_lead())
    assert v["empresa_nombre"] == ""
    assert v["empresa_producto_clave"] == ""


def test_dynamic_vars_sin_ubicacion():
    lead = _lead(ubicacion=Ubicacion(direccion=""))
    v = _brief().generar_dynamic_variables(lead)
    assert v["ciudad"] == ""


def test_dynamic_vars_compromiso_cumplido_no_aparece():
    lead = _lead(compromisos=[
        Compromiso(id="c1", tipo="callback", cumplido=True),
        Compromiso(id="c2", tipo="muestra",
                   fecha_objetivo="2026-06-01T08:00:00+00:00", cumplido=False),
    ])
    v = _brief().generar_dynamic_variables(lead)
    assert "muestra" in v["compromisos_pendientes"]
    assert "callback" not in v["compromisos_pendientes"]


def test_dynamic_vars_nombre_lead_fallback_a_negocio():
    """Sin nombre_contacto en metadatos_extra → cae al nombre del negocio."""
    lead = _lead(nombre_contacto="")
    v = _brief().generar_dynamic_variables(lead)
    assert v["nombre_lead"] == "Repostería La Curva"
    assert v["nombre_contacto"] == ""


# --- resumen markdown -----------------------------------------------------

def test_resumen_markdown_lead_nuevo_es_breve():
    out = _brief().generar_resumen(_lead())
    assert "# Briefing — Repostería La Curva (Albacete)" in out
    assert "primer_contacto" in out
    assert "Compromisos pendientes" not in out  # no hay compromisos
    assert "Histórico" not in out               # no hay interacciones
    assert "Repostería Laboratorio" in out           # footer empresa


def test_resumen_markdown_con_todo():
    lead = _lead(
        estado_pipeline="queued",
        interacciones=[Interaccion(
            ts="2026-05-26T18:16:00+00:00",
            tipo="llamada", resultado="contacted_no_decisor",
            resumen_llm="Hablé con Lidia, dependienta. Pide callback con el encargado.",
            duracion_s=89,
        )],
        compromisos=[Compromiso(id="c1", tipo="callback",
                                fecha_objetivo="2026-05-28T08:00:00+00:00",
                                tolerancia_min=60, contexto="callback Lidia")],
        reintentos=PoliticaReintentos(intentos_realizados=1, max_intentos=3),
    )
    out = _brief().generar_resumen(lead)
    assert "callback_pactado" in out
    assert "encargado" in out
    assert "Compromisos pendientes" in out
    assert "callback" in out and "±60min" in out
    assert "Histórico" in out
    assert "contacted_no_decisor" in out
    assert "89s" in out


def test_resumen_compromisos_ordenados_por_fecha():
    lead = _lead(compromisos=[
        Compromiso(id="c2", tipo="muestra",
                   fecha_objetivo="2026-06-10T08:00:00+00:00", cumplido=False),
        Compromiso(id="c1", tipo="callback",
                   fecha_objetivo="2026-05-28T08:00:00+00:00", cumplido=False),
    ])
    out = _brief().generar_resumen(lead)
    pos_callback = out.find("callback")
    pos_muestra = out.find("muestra")
    assert pos_callback < pos_muestra, "callback (más temprano) debería aparecer antes"


def test_resumen_no_crashea_con_lead_minimo():
    lead = LeadDoc(id="lead_minimo", company="laboratorio", estado_pipeline="cold")
    out = GeneradorBriefing().generar_resumen(lead)
    assert "lead_minimo" in out
    assert "cold" in out  # estado default cuando vacío
