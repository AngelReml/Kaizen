"""Colocación de llamadas outbound en Twilio con Record=true + TwiML + Stream a CAI.

Topología B1a del PLAN_VOZ_CONVERSACIONAL.md:
  1. Twilio reproduce el aviso legal con Polly Conchita (deterministicio, R5).
  2. Pausa de 1 segundo (margen para colgar).
  3. <Connect><Stream> a wss://api.elevenlabs.io/v1/convai/conversation?agent_id=...

R1 (grabación obligatoria) se garantiza con `Record=true` en el POST.
Si Twilio devuelve error → no se coloca; pre_flight ya filtró buena parte de los casos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from xml.sax import saxutils

import requests
from requests.auth import HTTPBasicAuth

from departments.comercial.sdr.voz_conversacional import agente_config_v1 as _v1

TWILIO_BASE = "https://api.twilio.com/2010-04-01"
CAI_WS_BASE = "wss://api.elevenlabs.io/v1/convai/conversation"


@dataclass
class ResultadoLlamada:
    ok: bool
    call_sid: str | None = None
    twilio_status: str = ""
    detalle: dict | None = None
    motivo: str = ""


def _esc(s: str | None) -> str:
    """Escape XML para evitar inyección en el TwiML."""
    return saxutils.escape(str(s or ""), {"\"": "&quot;", "'": "&apos;"})


def construir_twiml(*, aviso_legal: str, agent_id: str, lead: dict,
                     pendiente_id: str = "") -> str:
    """Construye el TwiML que Twilio ejecutará en la llamada.

    El aviso legal se reproduce con Polly Conchita (es-ES); el Stream pasa a
    ElevenLabs CAI los parámetros del lead como `<Parameter>`, accesibles desde
    el system prompt del agente vía custom data.
    """
    ubic = (lead.get("ubicacion") or {})
    params = {
        "lead_id":      lead.get("id", ""),
        "lead_nombre":  lead.get("nombre", ""),
        "categoria":    lead.get("categoria_icp", ""),
        "prioridad":    lead.get("prioridad_icp", ""),
        "anillo":       str(lead.get("anillo", "")),
        "ciudad":       ubic.get("direccion", ""),
        "pendiente_id": pendiente_id,
    }
    parametros_xml = "".join(
        f'<Parameter name="{_esc(k)}" value="{_esc(v)}"/>' for k, v in params.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Say voice="Polly.Conchita" language="es-ES">{_esc(aviso_legal)}</Say>'
        '<Pause length="1"/>'
        '<Connect>'
        f'<Stream url="{CAI_WS_BASE}?agent_id={_esc(agent_id)}">'
        f'{parametros_xml}'
        '</Stream>'
        '</Connect>'
        '</Response>'
    )


def colocar_llamada(*, telefono_destino_e164: str, lead: dict, pendiente_id: str,
                     agente_snapshot=_v1, public_base_url: str | None = None,
                     ignorar_franja: bool = False) -> ResultadoLlamada:
    """POST a Twilio Calls.json con Record=true + TwiML. Devuelve call_sid o error claro."""
    sid    = os.environ.get("TWILIO_ACCOUNT_SID")
    key    = os.environ.get("TWILIO_API_KEY_SID")
    secret = os.environ.get("TWILIO_API_KEY_SECRET")
    frm    = os.environ.get("TWILIO_FROM_NUMBER")
    agent  = os.environ.get("ELEVENLABS_AGENT_ID")
    base   = public_base_url or os.environ.get("PUBLIC_MEDIA_BASE_URL")
    faltan = [n for n, v in {
        "TWILIO_ACCOUNT_SID": sid, "TWILIO_API_KEY_SID": key,
        "TWILIO_API_KEY_SECRET": secret, "TWILIO_FROM_NUMBER": frm,
        "ELEVENLABS_AGENT_ID": agent, "PUBLIC_MEDIA_BASE_URL": base,
    }.items() if not v]
    if faltan:
        return ResultadoLlamada(ok=False, motivo=f"faltan en .env: {', '.join(faltan)}")

    twiml = construir_twiml(
        aviso_legal=agente_snapshot.aviso_legal_twilio(),
        agent_id=agent, lead=lead, pendiente_id=pendiente_id,
    )

    base = base.rstrip("/")
    payload = {
        "To": telefono_destino_e164,
        "From": frm,
        "Twiml": twiml,
        "Record": "true",
        "RecordingChannels": "dual",
        "RecordingStatusCallback": f"{base}/comercial/voz/twilio/recording",
        "RecordingStatusCallbackEvent": "completed",
        "RecordingStatusCallbackMethod": "POST",
        "StatusCallback": f"{base}/comercial/voz/twilio/status",
        # Twilio acepta múltiples valores repitiendo el parámetro; requests serializa
        # bien una lista de tuples.
        "StatusCallbackMethod": "POST",
    }
    # Eventos del StatusCallback
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
        return ResultadoLlamada(ok=False, motivo=f"excepción de red: {e}")

    if r.status_code >= 400:
        return ResultadoLlamada(ok=False, motivo=f"Twilio {r.status_code}: {r.text[:300]}",
                                 detalle={"status": r.status_code, "body": r.text[:1000]})

    data = r.json()
    return ResultadoLlamada(ok=True, call_sid=data.get("sid"),
                            twilio_status=data.get("status", ""), detalle=data)
