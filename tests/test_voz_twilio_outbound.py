"""Tests del POST a Twilio Calls.json — TwiML correcto, Record=true SIEMPRE."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional import twilio_outbound as out
from departments.comercial.sdr.voz_conversacional import agente_config_v1 as v1


def _entorno_completo(monkeypatch):
    for n, val in {
        "TWILIO_ACCOUNT_SID": "AC_test",
        "TWILIO_API_KEY_SID": "SK_test",
        "TWILIO_API_KEY_SECRET": "secret_test",
        "TWILIO_FROM_NUMBER": "+34999000000",
        "ELEVENLABS_AGENT_ID": "agent_X",
        "PUBLIC_MEDIA_BASE_URL": "https://ngrok.test",
    }.items():
        monkeypatch.setenv(n, val)


class _PostResp:
    def __init__(self, status=201, json_data=None, text=""):
        self.status_code = status
        self._json = json_data or {"sid": "CA_test", "status": "queued"}
        self.text = text
    def json(self): return self._json


# ── construir_twiml ──────────────────────────────────────────────────────────
def test_twiml_contiene_aviso_legal_y_stream():
    lead = {"id": "x", "nombre": "Hotel La Parra", "categoria_icp": "hotel_boutique_con_desayuno",
            "prioridad_icp": "ALTA", "anillo": 0, "ubicacion": {"direccion": "Cieza"}}
    twiml = out.construir_twiml(aviso_legal="Atención, esta llamada es comercial.",
                                 agent_id="agent_X", lead=lead, pendiente_id="pid1")
    assert "<Say " in twiml
    assert "Atención, esta llamada es comercial." in twiml
    assert "Polly.Conchita" in twiml
    assert 'language="es-ES"' in twiml
    assert "<Connect>" in twiml and "<Stream" in twiml
    assert "agent_id=agent_X" in twiml
    # Custom parameters del lead presentes
    assert 'name="lead_id"' in twiml and "value=\"x\"" in twiml
    assert 'name="categoria"' in twiml
    assert 'name="anillo"' in twiml
    assert 'name="pendiente_id"' in twiml


def test_twiml_escapa_caracteres_xml_peligrosos():
    """Si el nombre del lead lleva < > & ", no debe romper el TwiML."""
    lead = {"id": "x", "nombre": 'Hotel "La Llave & Co. <gourmet>'}
    twiml = out.construir_twiml(aviso_legal="Aviso & test", agent_id="aX", lead=lead)
    # Caracteres peligrosos escapados
    assert "&amp;" in twiml or 'Hotel "La Llave & Co. <gourmet>' not in twiml
    # No quedan tags abiertos por accidente
    assert twiml.count("<Response>") == 1
    assert twiml.count("</Response>") == 1


def test_twiml_incluye_pause_entre_say_y_connect():
    twiml = out.construir_twiml(aviso_legal="aviso", agent_id="aX", lead={"id": "x"})
    # Pause garantiza margen para colgar tras el aviso legal (compliance).
    assert "<Pause" in twiml


# ── colocar_llamada ──────────────────────────────────────────────────────────
def test_colocar_llamada_falla_sin_env_vars(monkeypatch):
    for v in ("TWILIO_ACCOUNT_SID", "TWILIO_FROM_NUMBER", "ELEVENLABS_AGENT_ID",
              "PUBLIC_MEDIA_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    res = out.colocar_llamada(telefono_destino_e164="+34600000000",
                               lead={"id": "x"}, pendiente_id="p1")
    assert not res.ok
    assert "faltan en .env" in res.motivo


def test_colocar_llamada_envia_record_true_y_callbacks(monkeypatch):
    """R1: Record=true en CADA llamada. Y los 3 callbacks (status x4 eventos + recording)."""
    _entorno_completo(monkeypatch)
    posts = []
    def _post(url, **kw):
        posts.append((url, kw))
        return _PostResp(201)
    monkeypatch.setattr(requests, "post", _post)
    res = out.colocar_llamada(telefono_destino_e164="+34600000000",
                               lead={"id": "x", "nombre": "X"}, pendiente_id="p1")
    assert res.ok
    assert res.call_sid == "CA_test"

    url, kw = posts[0]
    assert "/Calls.json" in url
    # data es lista de tuplas (param, valor)
    data = dict(kw["data"]) if isinstance(kw["data"], list) and not any(
        k == "StatusCallbackEvent" for k, _ in kw["data"]) else None
    # Cuando hay StatusCallbackEvent múltiple, dict() pisaría; recogemos manualmente.
    data_pairs = kw["data"]
    nombres = [k for k, _ in data_pairs]
    assert "Record" in nombres
    record_val = next(v for k, v in data_pairs if k == "Record")
    assert record_val == "true"
    # Recording callback presente
    rec_cb = next(v for k, v in data_pairs if k == "RecordingStatusCallback")
    assert rec_cb.endswith("/comercial/voz/twilio/recording")
    # Status callback presente con los 4 eventos
    eventos = [v for k, v in data_pairs if k == "StatusCallbackEvent"]
    assert set(eventos) >= {"initiated", "ringing", "answered", "completed"}
    # Twiml viaja con <Stream> a ElevenLabs
    twiml = next(v for k, v in data_pairs if k == "Twiml")
    assert "elevenlabs.io/v1/convai/conversation" in twiml
    assert "agent_id=agent_X" in twiml


def test_colocar_llamada_propaga_error_de_twilio(monkeypatch):
    _entorno_completo(monkeypatch)
    monkeypatch.setattr(requests, "post",
                        lambda url, **kw: _PostResp(400, {"code": 21215},
                                                    "Account not authorized"))
    res = out.colocar_llamada(telefono_destino_e164="+34600000000",
                               lead={"id": "x"}, pendiente_id="p1")
    assert not res.ok
    assert "Twilio 400" in res.motivo
    assert res.detalle["status"] == 400


def test_colocar_llamada_recoge_excepcion_de_red(monkeypatch):
    _entorno_completo(monkeypatch)
    def _post(*a, **kw): raise requests.ConnectionError("DNS")
    monkeypatch.setattr(requests, "post", _post)
    res = out.colocar_llamada(telefono_destino_e164="+34600000000",
                               lead={"id": "x"}, pendiente_id="p1")
    assert not res.ok
    assert "excepción de red" in res.motivo
