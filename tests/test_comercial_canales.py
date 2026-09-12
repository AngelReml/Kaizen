"""Tests del contrato de canales del SDR (todos deshabilitados por defecto y con motivo)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.canales.base import CanalDeshabilitado
from departments.comercial.sdr.canales.email import EmailChannel
from departments.comercial.sdr.canales.linkedin import LinkedInChannel
from departments.comercial.sdr.canales.voz import VoiceChannel
from departments.comercial.sdr.canales.whatsapp import WhatsAppChannel


def test_voz_apagada_por_flag_por_defecto():
    # SDR_VOICE_ENABLED debe ser "false" en .env por seguridad LSSI/RGPD.
    os.environ.pop("SDR_VOICE_ENABLED", None)   # forzar default
    ok, motivo = VoiceChannel().disponible()
    assert ok is False
    assert "SDR_VOICE_ENABLED" in motivo

    # Contactar debe lanzar CanalDeshabilitado, no fallar silencioso.
    with pytest.raises(CanalDeshabilitado):
        VoiceChannel().contactar(destino="+34611111111", asunto=None, cuerpo="hola")


def test_whatsapp_apagado_y_motivo_explica_sandbox():
    os.environ.pop("WHATSAPP_ENABLED", None)
    ok, motivo = WhatsAppChannel().disponible()
    assert ok is False
    assert "sandbox" in motivo.lower() or "Meta" in motivo


def test_linkedin_apagado_y_motivo_explica_supervisado():
    os.environ.pop("LINKEDIN_ENABLED", None)
    ok, motivo = LinkedInChannel().disponible()
    assert ok is False
    assert "supervisada" in motivo.lower() or "supervisado" in motivo.lower()


def test_email_se_apaga_si_faltan_credenciales_smtp():
    for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        os.environ.pop(v, None)
    ok, motivo = EmailChannel().disponible()
    assert ok is False
    assert "SMTP_HOST" in motivo


def test_voz_genera_audio_si_se_pasa_voice_id_explicito(monkeypatch, tmp_path):
    """Si el operador llama a generar_audio con un voice_id explícito y la clave de
    ElevenLabs no está, debe lanzar CanalDeshabilitado claro (no AttributeError)."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(CanalDeshabilitado):
        VoiceChannel(media_dir=tmp_path).generar_audio("hola", voice_id="xxxx")
