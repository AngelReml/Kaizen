"""Canal Voz — Twilio + ElevenLabs Multilingual v2 con la voz clonada de Iván (§4.4 v0.2).

Está construido funcional. Por defecto está APAGADO con el flag `SDR_VOICE_ENABLED=false`,
respetando la "zona ámbar consciente" del v0.2 §4.3: no se hacen llamadas comerciales a
producción hasta que el operador active explícitamente el flag y haya revisado el marco
LSSI/RGPD.

Para usarse necesita:
  - SDR_VOICE_ENABLED=true                (operador lo decide)
  - ELEVENLABS_API_KEY + IVAN_VOICE_ID
  - TWILIO_ACCOUNT_SID + (TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET) o AUTH_TOKEN
  - TWILIO_FROM_NUMBER (número español con voz habilitada)
  - PUBLIC_MEDIA_BASE_URL (URL pública donde se sirve el MP3 generado, para `<Play>`)
"""
from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from departments.comercial.sdr.canales.base import Canal, CanalDeshabilitado, ResultadoContacto

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TWILIO_CALL_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"


class VozBloqueada(RuntimeError):
    """La colocacion de llamada real fue bloqueada por una barrera de seguridad (R-02)."""


def _lista_numeros_propios() -> set[str]:
    """Allowlist de numeros propios de Ivan (E.164), de KAIZEN_VOZ_ALLOWLIST separada por comas."""
    crudo = os.environ.get("KAIZEN_VOZ_ALLOWLIST", "")
    return {re.sub(r"[\s\-().]", "", n) for n in crudo.split(",") if n.strip()}


def guardia_llamada_real(numero: str, *, confirmar_envio_real: bool = False) -> None:
    """R-02 — barrera UNICA que TODO camino de colocacion real debe cruzar.

    Antes de esta correccion `kaizen test voz <numero>` llamaba directo a
    `colocar_llamada`, saltandose sandbox, aprobacion, Robinson, franja y cuota,
    con un guion que se hacia pasar por Ivan. Ahora ningun camino coloca una
    llamada sin cruzar aqui. Fail-closed (GR-04): en duda, NO llama.

      1. Candado de BAJA: la voz esta DE BAJA por orden del operador
         (KAIZEN_VOZ_DE_BAJA != 'false'); mientras siga de baja, se corta aqui.
      2. Los dos flags del sandbox globales deben estar en true.
      3. Confirmacion explicita del llamador (--confirmar-envio-real).
      4. El numero destino debe estar en la allowlist de numeros propios.
    """
    if os.environ.get("KAIZEN_VOZ_DE_BAJA", "true").lower() != "false":
        raise VozBloqueada(
            "voz DE BAJA por orden del operador: ninguna llamada sale (candado R-02). "
            "Reactivarla exige el gate de D00 §8.3, no una variable suelta.")
    if os.environ.get("KAIZEN_ENVIO_HABILITADO", "false").lower() != "true":
        raise VozBloqueada("KAIZEN_ENVIO_HABILITADO != true (sandbox global).")
    if os.environ.get("SDR_VOICE_ENABLED", "false").lower() != "true":
        raise VozBloqueada("SDR_VOICE_ENABLED != true (zona ambar consciente v0.2 §4.3).")
    if not confirmar_envio_real:
        raise VozBloqueada("falta confirmacion explicita de envio real (--confirmar-envio-real).")
    destino = re.sub(r"[\s\-().]", "", numero or "")
    allow = _lista_numeros_propios()
    if not allow or destino not in allow:
        raise VozBloqueada(
            f"numero destino {numero!r} no esta en la allowlist de numeros propios "
            "(KAIZEN_VOZ_ALLOWLIST). Los tests de voz solo van a tus propios numeros (R4/R-02).")


class VoiceChannel(Canal):
    nombre = "voz"

    def __init__(self, *, media_dir: Path | None = None) -> None:
        self.media_dir = media_dir or (Path(__file__).resolve().parents[4] / "_workspace" / "voz")
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def disponible(self) -> tuple[bool, str]:
        if os.environ.get("SDR_VOICE_ENABLED", "false").lower() != "true":
            return False, "flag SDR_VOICE_ENABLED=false (zona ámbar consciente del v0.2 §4.3)"
        faltan = [v for v in (
            "ELEVENLABS_API_KEY", "IVAN_VOICE_ID",
            "TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_FROM_NUMBER",
        ) if not os.environ.get(v)]
        if faltan:
            return False, f"Faltan en .env: {', '.join(faltan)}"
        if not os.environ.get("PUBLIC_MEDIA_BASE_URL"):
            return False, "Falta PUBLIC_MEDIA_BASE_URL (URL pública para servir el MP3 a Twilio <Play>)"
        return True, ""

    # ── Generación de audio con ElevenLabs (voz clonada de Iván) ───────────
    def generar_audio(self, texto: str, *, voice_id: str | None = None,
                      modelo: str | None = None, dest: Path | None = None) -> Path:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise CanalDeshabilitado("ELEVENLABS_API_KEY ausente")
        vid = voice_id or os.environ.get("IVAN_VOICE_ID")
        if not vid:
            raise CanalDeshabilitado("IVAN_VOICE_ID ausente — confirma cuál de las voces clonadas usar")
        modelo = modelo or os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        url = ELEVEN_TTS_URL.format(voice_id=vid)
        r = requests.post(url, headers={"xi-api-key": key, "Accept": "audio/mpeg",
                                        "Content-Type": "application/json"},
                          json={"text": texto, "model_id": modelo,
                                "voice_settings": {"stability": 0.5, "similarity_boost": 0.85}},
                          timeout=60)
        r.raise_for_status()
        if dest is None:
            dest = self.media_dir / f"voz_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp3"
        dest.write_bytes(r.content)
        return dest

    # ── Llamada Twilio reproduciendo MP3 público (TwiML <Play>) ────────────
    def colocar_llamada(self, *, a: str, audio_url: str | None = None,
                        twiml: str | None = None, confirmar_envio_real: bool = False) -> dict:
        # R-02: barrera DENTRO del dispatcher (como el email blinda dentro de _enviar).
        # Ningun camino — ni el CLI test voz — coloca una llamada sin cruzarla.
        guardia_llamada_real(a, confirmar_envio_real=confirmar_envio_real)
        sid    = os.environ["TWILIO_ACCOUNT_SID"]
        key    = os.environ["TWILIO_API_KEY_SID"]
        secret = os.environ["TWILIO_API_KEY_SECRET"]
        frm    = os.environ["TWILIO_FROM_NUMBER"]
        if not twiml:
            if not audio_url:
                raise ValueError("colocar_llamada necesita twiml o audio_url")
            twiml = f"<Response><Play>{audio_url}</Play></Response>"
        r = requests.post(
            TWILIO_CALL_URL.format(sid=sid),
            auth=HTTPBasicAuth(key, secret),
            data={"To": a, "From": frm, "Twiml": twiml},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def contactar(self, *, destino: str, asunto: str | None, cuerpo: str,
                  lead: dict | None = None) -> ResultadoContacto:
        ok, motivo = self.disponible()
        if not ok:
            raise CanalDeshabilitado(f"Voz no disponible: {motivo}")
        mp3 = self.generar_audio(cuerpo)
        # Construimos la URL pública (PUBLIC_MEDIA_BASE_URL + nombre del archivo).
        base = os.environ["PUBLIC_MEDIA_BASE_URL"].rstrip("/")
        audio_url = f"{base}/{mp3.name}"
        try:
            data = self.colocar_llamada(a=destino, audio_url=audio_url)
        except Exception as e:
            return ResultadoContacto(canal=self.nombre, estado="fallido",
                                     destino=destino, detalle=str(e),
                                     metadatos={"audio_mp3": str(mp3)})
        return ResultadoContacto(
            canal=self.nombre, estado="enviado", destino=destino,
            referencia_externa=data.get("sid"),
            detalle=f"Twilio call SID {data.get('sid')}",
            metadatos={"audio_mp3": str(mp3), "audio_url": audio_url, "twilio": data},
        )
