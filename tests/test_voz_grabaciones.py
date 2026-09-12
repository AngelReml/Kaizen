"""Tests de descarga de grabaciones Twilio (sin red real)."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional.grabaciones import (
    descargar_recording, ResultadoDescarga,
)


class _RespFake:
    def __init__(self, status=200, contenido=b"x" * 4096, headers=None):
        self.status_code = status
        self._contenido = contenido
        self.headers = headers or {"content-type": "audio/mpeg"}
    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._contenido), chunk_size):
            yield self._contenido[i:i+chunk_size]
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _entorno_twilio(monkeypatch):
    for v in ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET"):
        monkeypatch.setenv(v, "fake")


def test_descarga_OK_persiste_mp3_y_devuelve_metadata(monkeypatch, tmp_path):
    _entorno_twilio(monkeypatch)
    monkeypatch.setattr(requests, "get",
                        lambda url, **kw: _RespFake(200, b"\xff" * 50_000))
    res = descargar_recording(call_sid="CA1",
                               recording_url="https://api.twilio.com/2010-04-01/.../RE1",
                               salida_dir=tmp_path, duracion_s=30.0)
    assert res.ok is True
    assert res.ruta.exists()
    assert res.bytes == 50_000
    assert res.sha256                              # hash calculado
    # Sin .tmp residual
    assert not list(tmp_path.glob("*.tmp"))


def test_recording_url_sin_mp3_extension_se_agrega(monkeypatch, tmp_path):
    """Twilio devuelve URL sin extensión; el descargador añade `.mp3`."""
    _entorno_twilio(monkeypatch)
    urls_pedidas = []
    def _get(url, **kw):
        urls_pedidas.append(url)
        return _RespFake(200, b"\xff" * 50_000)
    monkeypatch.setattr(requests, "get", _get)
    descargar_recording(call_sid="CA1",
                        recording_url="https://api.twilio.com/2010-04-01/.../RE1",
                        salida_dir=tmp_path)
    assert urls_pedidas[0].endswith(".mp3")


def test_falla_si_grabacion_es_muy_pequeña(monkeypatch, tmp_path):
    """Tamaño <1KB → falla (R1: no aceptamos grabaciones sospechosamente vacías)."""
    _entorno_twilio(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda url, **kw: _RespFake(200, b"abc"))
    res = descargar_recording(call_sid="CA1", recording_url="https://x/RE",
                               salida_dir=tmp_path)
    assert not res.ok
    assert "demasiado pequeña" in res.motivo


def test_falla_si_duracion_es_corta(monkeypatch, tmp_path):
    _entorno_twilio(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda url, **kw: _RespFake(200, b"\xff" * 5000))
    res = descargar_recording(call_sid="CA1", recording_url="https://x/RE",
                               salida_dir=tmp_path, duracion_s=2.0)
    assert not res.ok
    assert "duración" in res.motivo


def test_falla_si_url_vacia(tmp_path):
    res = descargar_recording(call_sid="CA1", recording_url="", salida_dir=tmp_path)
    assert not res.ok
    assert "vacía" in res.motivo


def test_falla_explicito_si_faltan_credenciales(monkeypatch, tmp_path):
    for v in ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET"):
        monkeypatch.delenv(v, raising=False)
    res = descargar_recording(call_sid="CA1", recording_url="https://x/RE",
                               salida_dir=tmp_path)
    assert not res.ok
    assert "credenciales" in res.motivo


def test_falla_si_twilio_404(monkeypatch, tmp_path):
    _entorno_twilio(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda url, **kw: _RespFake(404, b""))
    res = descargar_recording(call_sid="CA1", recording_url="https://x/RE",
                               salida_dir=tmp_path)
    assert not res.ok
    assert "fallo descarga" in res.motivo
