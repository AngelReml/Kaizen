"""Tests del orquestador post-call. Mockea el análisis para no llamar al LLM real."""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.account_executive import AccountExecutive, ResultadoEscalado
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.sdr.compromiso import DecisionCompromiso
from departments.comercial.sdr.voz_conversacional import transcripts as _t
from departments.comercial.sdr.voz_conversacional.analisis_calidad import (
    DictamenCalidad, DictamenTono,
)
from departments.comercial.sdr.voz_conversacional.post_call import (
    PostCallOrchestrator, EVENTOS_REQUERIDOS,
)


# ── Doubles ─────────────────────────────────────────────────────────────────
class _AnalisisFake:
    """Devuelve un DictamenCalidad pre-fabricado sin llamar al LLM."""
    def __init__(self, dictamen):
        self.dictamen = dictamen
        self.llamadas = 0
    def analizar(self, **kw):
        self.llamadas += 1
        return self.dictamen


def _dictamen(es_compromiso=False, confianza=0.7):
    return DictamenCalidad(
        call_sid="CA1", lead_id="lead_x", agente_config_version="v1",
        compromiso=DecisionCompromiso(es_compromiso=es_compromiso, confianza=confianza,
                                       motivo="test"),
        tono=DictamenTono(ok=True),
        objeciones=[], mejoras=["foo"],
        puntuacion_global=8 if es_compromiso else 4,
        duracion_s=120.0, turnos_agente=4, turnos_cliente=3,
    )


def _setup(*, lead_estado=EstadoLead.ENRIQUECIDO):
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    store.crear("lead_x", {"nombre": "Hotel X"})
    if lead_estado != EstadoLead.IDENTIFICADO:
        for st in (EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO):
            store.transicionar("lead_x", st, razon="seed")
            if st == lead_estado: break
    return k, store


def _llamada_completa(k, *, recording_path=True, transcript_len=4,
                      aviso_legal_version="v1"):
    """Crea un nodo llamada con los 3 eventos completados."""
    _t.crear_llamada(k, "laboratorio",
                     call_sid="CA1", lead_id="lead_x", pendiente_id="pid1",
                     agente_config_version="v1",
                     aviso_legal_version=aviso_legal_version)
    transcript = [
        {"hablante": "agente", "ts": 0, "texto": f"agente {i}"} if i % 2 == 0
        else {"hablante": "cliente", "ts": i, "texto": f"cliente {i}"}
        for i in range(transcript_len)
    ]
    _t.persistir_transcript(k, "laboratorio", "CA1", transcript)
    _t.marcar_evento_completado(k, "laboratorio", "CA1", "status_completed")
    # El webhook de recording SIEMPRE llega; el recording_path puede no existir si la
    # descarga MP3 falló (R1 violado). Por eso evento != path persistido.
    _t.marcar_evento_completado(k, "laboratorio", "CA1", "recording")
    parches = {"duracion_s": 120.0}
    if recording_path:
        parches["recording_path"] = "/tmp/CA1.mp3"
    _t.actualizar_llamada(k, "laboratorio", "CA1", **parches)


# ── No dispara si faltan eventos ────────────────────────────────────────────
def test_no_dispara_si_faltan_eventos():
    k, store = _setup()
    _t.crear_llamada(k, "laboratorio", call_sid="CA1", lead_id="lead_x", pendiente_id="p",
                     agente_config_version="v1")
    _t.marcar_evento_completado(k, "laboratorio", "CA1", "status_completed")    # falta 2
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA1")
    assert not r.analizado and "faltan eventos" in r.razon_no_analizado


def test_no_dispara_si_llamada_no_existe():
    k, store = _setup()
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA_inexistente")
    assert not r.analizado
    assert "no existe" in r.razon_no_analizado


# ── No conforme bloquea análisis ────────────────────────────────────────────
def test_no_conforme_si_recording_falta(monkeypatch):
    k, store = _setup()
    _llamada_completa(k, recording_path=False)
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA1")
    assert not r.analizado
    assert "recording_no_descargado" in r.no_conforme_motivos
    # Llamada marcada no_conforme
    llamada = _t.get_llamada(k, "laboratorio", "CA1")
    assert llamada["estado"] == "no_conforme"


def test_no_conforme_si_aviso_legal_falta():
    k, store = _setup()
    _llamada_completa(k, aviso_legal_version="")
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA1")
    assert not r.analizado
    assert "aviso_legal_no_registrado" in (r.no_conforme_motivos or [])


def test_no_conforme_si_transcript_muy_corto():
    k, store = _setup()
    _llamada_completa(k, transcript_len=1)
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA1")
    assert not r.analizado
    assert any("transcript" in m for m in r.no_conforme_motivos or [])


# ── Camino feliz ────────────────────────────────────────────────────────────
def test_dispara_analisis_y_transiciona_a_en_contacto():
    k, store = _setup(lead_estado=EstadoLead.ENRIQUECIDO)
    _llamada_completa(k)
    pc = PostCallOrchestrator(lead_store=store, analisis=_AnalisisFake(_dictamen()))
    r = pc.tal_vez_disparar_analisis("CA1")
    assert r.analizado
    assert store.get("lead_x")["estado"] == EstadoLead.EN_CONTACTO.value
    # llamada referencia el análisis
    llamada = _t.get_llamada(k, "laboratorio", "CA1")
    assert llamada["analisis_id"] == r.analisis_id
    assert llamada["estado"] == "completada"


def test_idempotente_no_repite_si_ya_analizado():
    k, store = _setup()
    _llamada_completa(k)
    an = _AnalisisFake(_dictamen())
    pc = PostCallOrchestrator(lead_store=store, analisis=an)
    pc.tal_vez_disparar_analisis("CA1")
    pc.tal_vez_disparar_analisis("CA1")
    assert an.llamadas == 1                        # solo se analizó una vez


def test_escala_account_executive_si_compromiso_y_confianza_alta():
    k, store = _setup()
    _llamada_completa(k)
    ae_calls = []
    class FakeAE:
        def gestionar_compromiso(self, lead_id, dec, *, respuesta_texto=""):
            ae_calls.append((lead_id, dec.confianza, respuesta_texto[:40]))
            return ResultadoEscalado(True, lead_id, operacion_id="op1")
    pc = PostCallOrchestrator(lead_store=store,
                               analisis=_AnalisisFake(_dictamen(es_compromiso=True, confianza=0.9)),
                               account_executive=FakeAE())
    pc.tal_vez_disparar_analisis("CA1")
    assert len(ae_calls) == 1
    assert ae_calls[0][1] == 0.9


def test_no_escala_si_compromiso_pero_confianza_baja():
    k, store = _setup()
    _llamada_completa(k)
    ae_calls = []
    class FakeAE:
        def gestionar_compromiso(self, lead_id, dec, *, respuesta_texto=""):
            ae_calls.append((lead_id,))
            return ResultadoEscalado(False, lead_id, motivo="confianza baja")
    pc = PostCallOrchestrator(lead_store=store,
                               analisis=_AnalisisFake(_dictamen(es_compromiso=True, confianza=0.4)),
                               account_executive=FakeAE())
    pc.tal_vez_disparar_analisis("CA1")
    # confianza < 0.6 → orchestrator no llama a AE
    assert ae_calls == []
