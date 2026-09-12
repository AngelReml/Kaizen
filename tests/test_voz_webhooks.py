"""Tests de los 3 endpoints webhook (Twilio status, Twilio recording, ElevenLabs transcript)."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["KAIZEN_VOICE_SIG_BYPASS"] = "true"   # los tests no verifican firma HMAC

# Set ANTES de importar api.server (el módulo crea Knowledge en import-time).
os.environ.setdefault("KAIZEN_KNOWLEDGE_INMEMORY", "1")

from api.server import app, knowledge
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.sdr.voz_conversacional import transcripts as _t


@pytest.fixture
def cliente_y_lead():
    client = TestClient(app)
    store = LeadStore(knowledge, "laboratorio")
    # Limpiar leads previos
    for lid in list(knowledge.all("laboratorio", "lead").keys()):
        knowledge.delete("laboratorio", "lead", lid) if hasattr(knowledge, "delete") else None
    for cid in list(knowledge.all("laboratorio", "llamada").keys()):
        knowledge.delete("laboratorio", "llamada", cid) if hasattr(knowledge, "delete") else None
    # Crear lead y llamada
    if store.get("lead_test") is None:
        store.crear("lead_test", {"nombre": "Test Hotel"})
        for st in (EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO):
            store.transicionar("lead_test", st, razon="seed")
    _t.crear_llamada(knowledge, "laboratorio",
                     call_sid="CA_test_1", lead_id="lead_test", pendiente_id="pid_test",
                     agente_config_version="v1", aviso_legal_version="v1")
    yield client, store


# ── /comercial/voz/twilio/status ─────────────────────────────────────────────
def test_status_webhook_actualiza_estado_twilio(cliente_y_lead):
    client, _ = cliente_y_lead
    r = client.post("/comercial/voz/twilio/status",
                    data={"CallSid": "CA_test_1", "CallStatus": "ringing"})
    assert r.status_code == 200
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert nodo["twilio_status"] == "ringing"


def test_status_completed_marca_evento(cliente_y_lead):
    client, _ = cliente_y_lead
    r = client.post("/comercial/voz/twilio/status",
                    data={"CallSid": "CA_test_1", "CallStatus": "completed",
                          "CallDuration": "127"})
    assert r.status_code == 200
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert "status_completed" in nodo["eventos_completados"]
    assert nodo["duracion_s"] == 127.0


def test_status_webhook_acepta_call_sid_huerfano(cliente_y_lead):
    client, _ = cliente_y_lead
    # CallSid que NO existe en Knowledge — el endpoint no debe fallar.
    r = client.post("/comercial/voz/twilio/status",
                    data={"CallSid": "CA_huerfano", "CallStatus": "completed"})
    assert r.status_code == 200


# ── /comercial/voz/twilio/recording ──────────────────────────────────────────
def test_recording_webhook_intenta_descarga_y_marca_evento(cliente_y_lead, monkeypatch):
    client, _ = cliente_y_lead
    # Mockeamos descargar_recording para no salir a red real
    from departments.comercial.sdr.voz_conversacional import grabaciones as g
    ruta_fake = Path("/tmp") / "CA_test_1.mp3"     # se normaliza al separador del SO
    monkeypatch.setattr(g, "descargar_recording",
        lambda **kw: g.ResultadoDescarga(ok=True, ruta=ruta_fake,
                                          bytes=50000, sha256="abc"))
    # api.server importó descargar_recording en el endpoint; el patch debe alcanzar.
    import api.server as srv
    # Como el endpoint hace `from ... import descargar_recording` dentro de la función,
    # el monkeypatch al módulo `grabaciones` aplica.
    r = client.post("/comercial/voz/twilio/recording",
                    data={"CallSid": "CA_test_1",
                          "RecordingUrl": "https://api.twilio.com/.../RE_test",
                          "RecordingDuration": "120"})
    assert r.status_code == 200
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert "recording" in nodo["eventos_completados"]
    assert nodo["recording_path"].endswith("CA_test_1.mp3")
    assert nodo["recording_bytes"] == 50000


def test_recording_webhook_descarga_fallida_marca_no_conforme(cliente_y_lead, monkeypatch):
    client, _ = cliente_y_lead
    from departments.comercial.sdr.voz_conversacional import grabaciones as g
    monkeypatch.setattr(g, "descargar_recording",
        lambda **kw: g.ResultadoDescarga(ok=False, motivo="404 not found"))
    r = client.post("/comercial/voz/twilio/recording",
                    data={"CallSid": "CA_test_1",
                          "RecordingUrl": "https://api.twilio.com/.../RE_404",
                          "RecordingDuration": "5"})
    assert r.status_code == 200
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert any("descarga_recording_fallo" in m for m in nodo["no_conforme_motivos"])
    # Aún así marcamos el evento "recording" como recibido (la decisión ya está tomada)
    assert "recording" in nodo["eventos_completados"]


# ── /comercial/voz/eleven/transcript ────────────────────────────────────────
def test_transcript_webhook_persiste_turnos(cliente_y_lead):
    client, _ = cliente_y_lead
    payload = {
        "conversation_id": "conv_abc",
        "metadata": {"custom_data": {"call_sid": "CA_test_1"}},
        "transcript": [
            {"role": "agent",  "time_in_call_secs": 0.0, "message": "Hola buenos días."},
            {"role": "user",   "time_in_call_secs": 5.0, "message": "Dígame."},
            {"role": "agent",  "time_in_call_secs": 7.0, "message": "Le llamo de Laboratorio."},
        ],
    }
    r = client.post("/comercial/voz/eleven/transcript", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["turnos"] == 3
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert len(nodo["transcript"]) == 3
    # role=agent → hablante=agente; role=user → hablante=cliente
    assert nodo["transcript"][0]["hablante"] == "agente"
    assert nodo["transcript"][1]["hablante"] == "cliente"
    assert "transcript" in nodo["eventos_completados"]


def test_transcript_webhook_acepta_role_assistant_alias(cliente_y_lead):
    client, _ = cliente_y_lead
    payload = {
        "conversation_id": "x",
        "metadata": {"custom_data": {"call_sid": "CA_test_1"}},
        "transcript": [{"role": "assistant", "time_in_call_secs": 0, "message": "hola"}],
    }
    r = client.post("/comercial/voz/eleven/transcript", json=payload)
    nodo = _t.get_llamada(knowledge, "laboratorio", "CA_test_1")
    assert nodo["transcript"][0]["hablante"] == "agente"


# ── Firma (no bypass) ────────────────────────────────────────────────────────
def test_firma_invalida_devuelve_403(cliente_y_lead, monkeypatch):
    client, _ = cliente_y_lead
    monkeypatch.setenv("KAIZEN_VOICE_SIG_BYPASS", "false")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret_real")
    r = client.post("/comercial/voz/twilio/status",
                    data={"CallSid": "CA_test_1", "CallStatus": "ringing"},
                    headers={"X-Twilio-Signature": "firma_falsa"})
    assert r.status_code == 403


def test_firma_twilio_correcta_pasa(cliente_y_lead, monkeypatch):
    """Generamos firma válida con HMAC-SHA1 + comprobamos que el endpoint la acepta.

    La firma se calcula contra la MISMA URL que usa el servidor para verificarla:
    si PUBLIC_MEDIA_BASE_URL está definida (p.ej. filtrada desde .env como el resto
    de la suite), el servidor firma/verifica contra esa URL pública, no contra
    "http://testserver" — igual que en producción, donde Twilio firma la URL externa
    (ngrok/dominio real), no la que ve el proceso local detrás del proxy."""
    client, _ = cliente_y_lead
    monkeypatch.setenv("KAIZEN_VOICE_SIG_BYPASS", "false")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret_test")
    import base64, hashlib, hmac, os
    params = {"CallSid": "CA_test_1", "CallStatus": "ringing"}
    base = os.environ.get("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")
    url_firma = f"{base}/comercial/voz/twilio/status" if base else "http://testserver/comercial/voz/twilio/status"
    sorted_pairs = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    firma = base64.b64encode(hmac.new(b"secret_test", (url_firma + sorted_pairs).encode(),
                                       hashlib.sha1).digest()).decode()
    r = client.post("/comercial/voz/twilio/status", data=params, headers={"X-Twilio-Signature": firma})
    assert r.status_code == 200
