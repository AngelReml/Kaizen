"""Tests del CompromisoDetector (parsing) y del AccountExecutive (escalado)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.account_executive import AccountExecutive
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.sdr.compromiso import CompromisoDetector, DecisionCompromiso


# ── CompromisoDetector — parsing del JSON del LLM ────────────────────────────
def _chat_que_devuelve(respuesta):
    def _chat(messages, system=None, **kw): return respuesta
    return _chat


def test_detector_parsea_json_limpio():
    d = CompromisoDetector(chat=_chat_que_devuelve(
        '{"es_compromiso": true, "confianza": 0.85, '
        '"senales_detectadas": ["puedo tomar una muestra"], '
        '"motivo": "petición explícita", "recomendacion": "escalar_account_executive"}'
    ))
    r = d.evaluar("Sí, puedo tomar una muestra para probarlas.")
    assert r.es_compromiso is True
    assert r.confianza == 0.85
    assert r.senales_detectadas == ["puedo tomar una muestra"]
    assert r.recomendacion == "escalar_account_executive"


def test_detector_extrae_json_de_bloque_markdown():
    d = CompromisoDetector(chat=_chat_que_devuelve(
        '```json\n{"es_compromiso": false, "confianza": 0.2, '
        '"senales_detectadas": [], "motivo": "cortesía", "recomendacion": "descartar"}\n```'
    ))
    r = d.evaluar("Gracias, suerte con eso.")
    assert r.es_compromiso is False
    assert r.recomendacion == "descartar"


def test_detector_respuesta_vacia_no_llama_al_llm():
    invocado = []
    def chat(*a, **kw):
        invocado.append(1)
        return ""
    d = CompromisoDetector(chat=chat)
    r = d.evaluar("")
    assert r.es_compromiso is False
    assert "vacía" in r.motivo
    assert invocado == []


def test_detector_devuelve_falso_si_llm_no_devuelve_json():
    d = CompromisoDetector(chat=_chat_que_devuelve("Lo siento, no lo sé"))
    r = d.evaluar("Tal vez...")
    assert r.es_compromiso is False
    assert "parseable" in r.motivo


# ── AccountExecutive — gate de confianza y máquina de estados ───────────────
def _ae_con_lead_en_contacto():
    """LeadStore con un lead en estado EN_CONTACTO (después de envío)."""
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    store.crear("lead_x", {"nombre": "Lead X"})
    for st in (EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO, EstadoLead.EN_CONTACTO):
        store.transicionar("lead_x", st, razon="seed")
    return AccountExecutive(lead_store=store), store


def test_escala_lead_si_compromiso_con_confianza_suficiente():
    ae, store = _ae_con_lead_en_contacto()
    dec = DecisionCompromiso(es_compromiso=True, confianza=0.85,
                             senales_detectadas=["volumen prometido"],
                             motivo="dijo X cajas/semana", recomendacion="escalar_account_executive")
    r = ae.gestionar_compromiso("lead_x", dec, respuesta_texto="Te compro 10 cajas/semana.")
    assert r.ok is True
    assert store.get("lead_x")["estado"] == EstadoLead.COMPROMISO_RECIPROCO.value
    # Operación registrada.
    ops = ae.listar_operaciones()
    assert len(ops) == 1
    assert ops[0]["lead_id"] == "lead_x"
    assert ops[0]["estado"] == "preparada"


def test_no_escala_si_confianza_baja():
    ae, store = _ae_con_lead_en_contacto()
    dec = DecisionCompromiso(es_compromiso=True, confianza=0.3,
                             senales_detectadas=["quizá"], motivo="duda", recomendacion="nurturing")
    r = ae.gestionar_compromiso("lead_x", dec)
    assert r.ok is False
    assert "confianza" in r.motivo
    assert store.get("lead_x")["estado"] == EstadoLead.EN_CONTACTO.value


def test_no_escala_si_decision_no_es_compromiso():
    ae, _ = _ae_con_lead_en_contacto()
    dec = DecisionCompromiso(es_compromiso=False, confianza=0.9, motivo="cortesía")
    r = ae.gestionar_compromiso("lead_x", dec)
    assert r.ok is False


def test_no_escala_si_lead_no_esta_en_contacto():
    """Lead en CUALIFICADO no debería poder saltar a COMPROMISO_RECIPROCO."""
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    store.crear("lead_y", {"nombre": "Y"})
    store.transicionar("lead_y", EstadoLead.CUALIFICADO, razon="seed")
    ae = AccountExecutive(lead_store=store)
    dec = DecisionCompromiso(es_compromiso=True, confianza=0.9, motivo="ok")
    r = ae.gestionar_compromiso("lead_y", dec)
    assert r.ok is False
    assert "transición" in r.motivo.lower() or "transicion" in r.motivo.lower()
