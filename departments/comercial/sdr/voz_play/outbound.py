"""Coloca llamada Twilio con TwiML `<Play>` apuntando al MP3 personalizado.

Patrón estable y probado: Polly lee el aviso legal, pausa, Twilio descarga el MP3
desde PUBLIC_MEDIA_BASE_URL y lo reproduce con la voz clonada de Iván. La llamada
se graba completa (Record=true) por si el cliente responde algo audible.

Webhooks: si la URL pública apunta a un FastAPI corriendo, los 3 callbacks llegan
y se actualiza el nodo `llamada`. Si no (servidor estático), la llamada funciona
igual y la grabación queda recuperable manualmente desde Twilio.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from xml.sax import saxutils

import requests
from requests.auth import HTTPBasicAuth

TWILIO_BASE = "https://api.twilio.com/2010-04-01"


@dataclass
class ResultadoLlamadaPlay:
    ok: bool
    call_sid: str | None = None
    twilio_status: str = ""
    motivo: str = ""
    detalle: dict | None = None


def _esc(s: str | None) -> str:
    return saxutils.escape(str(s or ""), {'"': "&quot;", "'": "&apos;"})


def construir_twiml(*, aviso_legal: str, mp3_url: str) -> str:
    """TwiML simple: Polly anuncia + Play del MP3 personalizado de Iván.

    Twilio descargará el MP3 desde `mp3_url` cuando el cliente conteste. La URL
    debe ser pública (PUBLIC_MEDIA_BASE_URL + nombre del archivo en ngrok).
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Say voice="Polly.Conchita" language="es-ES">{_esc(aviso_legal)}</Say>'
        '<Pause length="1"/>'
        f'<Play>{_esc(mp3_url)}</Play>'
        '<Pause length="2"/>'
        '</Response>'
    )


def colocar_llamada(*, telefono_destino_e164: str, mp3_url: str,
                     aviso_legal: str, public_base_url: str | None = None) -> ResultadoLlamadaPlay:
    """POST a Twilio Calls.json con `Record=true` + TwiML con `<Play>`."""
    sid    = os.environ.get("TWILIO_ACCOUNT_SID")
    key    = os.environ.get("TWILIO_API_KEY_SID")
    secret = os.environ.get("TWILIO_API_KEY_SECRET")
    frm    = os.environ.get("TWILIO_FROM_NUMBER")
    base   = (public_base_url or os.environ.get("PUBLIC_MEDIA_BASE_URL", "")).rstrip("/")

    faltan = [n for n, v in {
        "TWILIO_ACCOUNT_SID": sid, "TWILIO_API_KEY_SID": key,
        "TWILIO_API_KEY_SECRET": secret, "TWILIO_FROM_NUMBER": frm,
    }.items() if not v]
    if faltan:
        return ResultadoLlamadaPlay(ok=False, motivo=f"faltan en .env: {', '.join(faltan)}")
    if not mp3_url:
        return ResultadoLlamadaPlay(ok=False, motivo="mp3_url vacío")

    # R-02 embebido: misma barrera de sandbox que `eleven_outbound.colocar_llamada_via_cai`
    # y `VoiceChannel.colocar_llamada` (guardia_llamada_real). Antes solo el CLI (kaizen.py
    # -> pre_flight.verificar) la comprobaba; cualquier otro caller de esta función podía
    # colocar la llamada saltándosela. Fail-closed: sin las dos barreras, no se llama.
    if os.environ.get("KAIZEN_ENVIO_HABILITADO", "false").lower() != "true":
        return ResultadoLlamadaPlay(ok=False, motivo="KAIZEN_ENVIO_HABILITADO != true (sandbox global).")
    if os.environ.get("SDR_VOICE_ENABLED", "false").lower() != "true":
        return ResultadoLlamadaPlay(ok=False,
                                     motivo="SDR_VOICE_ENABLED != true (zona ambar consciente v0.2 §4.3).")

    # Quota diaria: se RESERVA aquí, antes del POST — mismo patrón que
    # `eleven_outbound.colocar_llamada_via_cai`. Antes este canal nunca tocaba la
    # quota: las llamadas por voz_play no contaban para el techo diario compartido
    # (KAIZEN_VOZ_MAX_LLAMADAS_DIA), dejando pasar de facto un canal sin límite.
    from departments.comercial.sdr.voz_conversacional import pre_flight as _pf
    try:
        _pf.reservar_llamada()
    except (_pf.QuotaAgotada, _pf.QuotaCorrupta) as e:
        return ResultadoLlamadaPlay(ok=False, motivo=str(e))

    twiml = construir_twiml(aviso_legal=aviso_legal, mp3_url=mp3_url)
    payload = {
        "To": telefono_destino_e164,
        "From": frm,
        "Twiml": twiml,
        "Record": "true",
        "RecordingChannels": "dual",
    }
    if base:
        payload["RecordingStatusCallback"] = f"{base}/comercial/voz/twilio/recording"
        payload["RecordingStatusCallbackMethod"] = "POST"
        payload["StatusCallback"] = f"{base}/comercial/voz/twilio/status"
        payload["StatusCallbackMethod"] = "POST"
    eventos = [("StatusCallbackEvent", e) for e in
               ("initiated", "ringing", "answered", "completed")]

    try:
        r = requests.post(
            f"{TWILIO_BASE}/Accounts/{sid}/Calls.json",
            auth=HTTPBasicAuth(key, secret),
            data=[*payload.items(), *eventos],
            timeout=30,
        )
    except Exception as e:
        _pf.liberar_llamada()          # no salió ninguna llamada: devolver el hueco
        return ResultadoLlamadaPlay(ok=False, motivo=f"red: {e}")
    if r.status_code >= 400:
        _pf.liberar_llamada()          # Twilio rechazó: tampoco se colocó
        return ResultadoLlamadaPlay(ok=False,
                                     motivo=f"Twilio {r.status_code}: {r.text[:300]}",
                                     detalle={"status": r.status_code, "body": r.text[:1000]})
    data = r.json()
    return ResultadoLlamadaPlay(ok=True, call_sid=data.get("sid"),
                                 twilio_status=data.get("status", ""), detalle=data)
