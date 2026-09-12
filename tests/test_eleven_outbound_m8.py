"""Tests del Módulo 8 — integración del sistema nervioso con el flujo de voz.

Cubre:
  * PRE-llamada: `dynamic_variables_briefing` y la inyección del briefing en el body
    via `construir_body` / `dry_run` cuando se pasa `company`.
  * POST-llamada: `procesar_transcript_post_llamada` con un transcript sintético
    que contiene un callback pactado, sin tocar la API real (detector inyectado).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from core.lead_schema import Compromiso
from core.pipeline_state_machine import EstadoPipeline, PipelineMachine
from departments.comercial.sdr.voz_conversacional import eleven_outbound as eo


# ─── Fixtures ───────────────────────────────────────────────────────────────


def _lead_seed(**kw) -> dict:
    """Seed con la forma real del knowledge: claves no modeladas viven al raíz y
    `LeadDoc.from_dict` las captura en `metadatos_extra`."""
    base = {
        "id": "lead_m8_test",
        "company": "laboratorio",
        "nombre": "Repostería La Curva",
        "categoria_icp": "panaderia_pasteleria",
        "prioridad_icp": "ALTA",
        "anillo": 1,
        "estado_pipeline": "contacting",
        "ubicacion": {"direccion": "Calle Mayor 12, 02660 Caudete, Albacete"},
        "contacto": {"telefono": "+34666000000"},
        "interacciones": [],
        "compromisos": [],
        "reintentos": {"intentos_realizados": 0, "max_intentos": 3},
        "do_not_call": False,
        "nombre_contacto": "Lidia",                # captured into metadatos_extra
    }
    base.update(kw)
    return base


class _DetectorStub:
    """Detector inyectable: devuelve compromisos fijos sin tocar el LLM."""

    def __init__(self, compromisos: list[Compromiso]) -> None:
        self._compromisos = compromisos

    def detectar(self, transcript: list[dict]) -> list[Compromiso]:
        return list(self._compromisos)


# ─── PRE-llamada — briefing inyectado en dynamic_variables ──────────────────


def test_dynamic_variables_briefing_combina_lead_y_perfil():
    """El briefing devuelve las claves del M5 + nombre/producto_clave del perfil."""
    vs = eo.dynamic_variables_briefing(_lead_seed(), company="laboratorio")
    # Claves del briefing
    assert vs["nombre_lead"] == "Lidia"                      # metadatos_extra.nombre_contacto
    assert vs["negocio"] == "Repostería La Curva"
    assert vs["categoria"] == "panaderia_pasteleria"
    assert vs["razon_llamada"] in {"primer_contacto", "reintento_no_answer",
                                    "reintento", "seguimiento_decisor"}
    # Perfil de empresa cargado desde empresas/laboratorio/perfil.json
    assert vs["empresa_nombre"] == "Laboratorio KAIZEN"
    assert vs["empresa_producto_clave"] == "producto de pruebas del laboratorio"


def test_dynamic_variables_briefing_falla_sin_id():
    with pytest.raises(ValueError):
        eo.dynamic_variables_briefing({"company": "laboratorio"}, company="laboratorio")


def test_dry_run_con_company_inyecta_briefing(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "a")
    monkeypatch.setenv("ELEVENLABS_PHONE_NUMBER_ID", "p")
    out = eo.dry_run(to_number_e164="+34600000000", lead=_lead_seed(),
                     company="laboratorio")
    vs = out["body"]["conversation_initiation_client_data"]["dynamic_variables"]
    # Variables legacy (las usa el agente actual)
    assert vs["lead_nombre"] == "Repostería La Curva"
    assert vs["categoria"] == "panaderia_pasteleria"
    # Variables del briefing añadidas por M8
    assert vs["empresa_nombre"] == "Laboratorio KAIZEN"
    assert vs["razon_llamada"] != ""


def test_dry_run_sin_company_solo_variables_legacy(monkeypatch):
    """Garantiza retrocompatibilidad: sin `company` no se invoca el briefing."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "a")
    monkeypatch.setenv("ELEVENLABS_PHONE_NUMBER_ID", "p")
    out = eo.dry_run(to_number_e164="+34600000000",
                     lead={"id": "x", "nombre": "X"})
    vs = out["body"]["conversation_initiation_client_data"]["dynamic_variables"]
    assert "empresa_nombre" not in vs
    assert "razon_llamada" not in vs


# ─── derivar_resultado_llamada ──────────────────────────────────────────────


def test_derivar_resultado_transcript_vacio_es_no_answer():
    assert eo.derivar_resultado_llamada([], []) == "no_answer"


def test_derivar_resultado_con_callback_es_callback_pactado():
    transcript = [{"hablante": "cliente", "texto": "vale, llámame mañana"}]
    compromisos = [Compromiso(id="c1", tipo="callback",
                              fecha_objetivo="2026-05-29T08:00:00+00:00")]
    assert eo.derivar_resultado_llamada(transcript, compromisos) == "callback_pactado"


def test_derivar_resultado_opt_out_gana_a_callback():
    transcript = [{"hablante": "cliente", "texto": "no me llaméis más"}]
    compromisos = [Compromiso(id="c1", tipo="callback",
                              fecha_objetivo="2026-05-29T08:00:00+00:00")]
    assert eo.derivar_resultado_llamada(transcript, compromisos) == "opt_out"


def test_derivar_resultado_sin_compromiso_es_contacted_no_decisor():
    transcript = [{"hablante": "cliente", "texto": "ahora no puedo hablar"}]
    assert eo.derivar_resultado_llamada(transcript, []) == "contacted_no_decisor"


# ─── POST-llamada — callback pactado (transcript sintético) ─────────────────


def test_post_llamada_callback_pactado_persiste_compromiso_y_queued():
    """Transcript sintético con callback → lead pasa CONTACTING → CONTACTED → QUEUED.

    El detector está mockeado: simula que el LLM identificó un callback para
    mañana a las 10 (08:00 UTC). El motor de reintentos debe encadenar la
    transición final y dejar `proxima_accion_ts` apuntando a la fecha del
    callback.
    """
    kstore = InMemoryKnowledge()
    seed = _lead_seed()
    kstore.add("laboratorio", "lead", seed["id"], seed)

    callback_iso = "2026-05-29T08:00:00+00:00"
    detector = _DetectorStub([
        Compromiso(id="c_stub", tipo="callback", fecha_objetivo=callback_iso,
                   tolerancia_min=15, contexto="cliente pidió mañana 10:00"),
    ])
    transcript = [
        {"hablante": "agente",  "ts": 1.0,
         "texto": "Buenos días, ¿hablo con la responsable de pastelería?"},
        {"hablante": "cliente", "ts": 3.0,
         "texto": "Sí, soy yo. Ahora estoy liada, ¿me llamas mañana a las 10?"},
        {"hablante": "agente",  "ts": 6.0,
         "texto": "Perfecto, te llamo mañana a las 10. Buen día."},
    ]

    res = eo.procesar_transcript_post_llamada(
        lead_id=seed["id"], company="laboratorio",
        transcript=transcript,
        knowledge=kstore, detector=detector,
        call_sid="CA_test_001", conversation_id="conv_001",
        duracion_s=42.0,
        clock=lambda: datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc),
    )

    # Camino feliz: callback detectado, lead queued con próxima acción agendada.
    assert res.ok, res.motivo
    assert res.resultado_derivado == "callback_pactado"
    assert res.estado_anterior == "contacting"
    assert res.estado_intermedio == "contacted"
    assert res.estado_final == "queued"
    assert res.proxima_accion_tipo == "llamar"
    assert res.proxima_accion_ts == callback_iso

    # El lead persistido refleja todos los cambios.
    persistido = kstore.get("laboratorio", "lead", seed["id"])
    assert persistido["estado_pipeline"] == "queued"
    callbacks = [c for c in persistido["compromisos"] if c["tipo"] == "callback"]
    assert len(callbacks) == 1
    assert callbacks[0]["fecha_objetivo"] == callback_iso
    assert callbacks[0]["origen_interaccion_id"] == res.interaccion_id

    # Interacción registrada con el resultado derivado.
    assert len(persistido["interacciones"]) == 1
    inter = persistido["interacciones"][0]
    assert inter["resultado"] == "callback_pactado"
    assert inter["canal_id"] == "CA_test_001"
    assert inter["duracion_s"] == 42.0

    # Callback no incrementa intentos (es continuación de la misma conversación).
    assert persistido["reintentos"]["intentos_realizados"] == 0


def test_post_llamada_no_answer_incrementa_intentos_y_reagenda():
    """Sin transcript (no contestó) → CONTACTING → NO_ANSWER → QUEUED con intentos+1."""
    kstore = InMemoryKnowledge()
    seed = _lead_seed()
    kstore.add("laboratorio", "lead", seed["id"], seed)

    res = eo.procesar_transcript_post_llamada(
        lead_id=seed["id"], company="laboratorio",
        transcript=[],
        knowledge=kstore,
        detector=_DetectorStub([]),
        call_sid="CA_noanswer",
        clock=lambda: datetime(2026, 5, 28, 11, 0, tzinfo=timezone.utc),
    )

    assert res.ok, res.motivo
    assert res.resultado_derivado == "no_answer"
    assert res.estado_final == "queued"
    persistido = kstore.get("laboratorio", "lead", seed["id"])
    assert persistido["reintentos"]["intentos_realizados"] == 1
    assert persistido["reintentos"]["proxima_accion_tipo"] == "llamar"
    assert persistido["reintentos"]["proxima_accion_ts"]                   # agendada


def test_post_llamada_lead_inexistente_devuelve_error():
    kstore = InMemoryKnowledge()
    res = eo.procesar_transcript_post_llamada(
        lead_id="no_existe", company="laboratorio",
        transcript=[], knowledge=kstore, detector=_DetectorStub([]),
    )
    assert not res.ok
    assert "no existe" in res.motivo


def test_post_llamada_compromiso_no_duplica_si_ya_existe():
    """Si el lead ya tiene el mismo callback (tipo+fecha), el detector no duplica."""
    kstore = InMemoryKnowledge()
    seed = _lead_seed()
    callback_iso = "2026-05-29T08:00:00+00:00"
    seed["compromisos"] = [{"id": "previo", "tipo": "callback",
                            "fecha_objetivo": callback_iso, "tolerancia_min": 15,
                            "contexto": "ya estaba", "cumplido": False}]
    kstore.add("laboratorio", "lead", seed["id"], seed)

    detector = _DetectorStub([
        Compromiso(id="c_dup", tipo="callback", fecha_objetivo=callback_iso,
                   tolerancia_min=15, contexto="dup"),
    ])
    res = eo.procesar_transcript_post_llamada(
        lead_id=seed["id"], company="laboratorio",
        transcript=[{"hablante": "cliente", "texto": "vale, mañana"}],
        knowledge=kstore, detector=detector,
        clock=lambda: datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc),
    )
    persistido = kstore.get("laboratorio", "lead", seed["id"])
    callbacks = [c for c in persistido["compromisos"] if c["tipo"] == "callback"]
    assert len(callbacks) == 1                                  # idempotente
    assert res.compromisos_nuevos == []                         # no se añadió ninguno
