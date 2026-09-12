"""Descarga y verificación de grabaciones MP3 de Twilio (R1).

Twilio dispara `RecordingStatusCallback` cuando la grabación está lista. Nosotros
descargamos el MP3 a `state/voz/grabaciones/<call_sid>.mp3`, calculamos hash y tamaño,
y marcamos no conforme si algo huele mal (tamaño <1KB, duración <5s).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class ResultadoDescarga:
    ok: bool
    ruta: Path | None = None
    bytes: int = 0
    sha256: str = ""
    duracion_s: float = 0.0
    motivo: str = ""


def _base_dir() -> Path:
    from core.rutas import dir_state
    return dir_state() / "voz" / "grabaciones"


def descargar_recording(*, call_sid: str, recording_url: str,
                        duracion_s: float = 0.0,
                        salida_dir: Path | None = None,
                        min_bytes: int = 1024, min_duracion_s: float = 5.0) -> ResultadoDescarga:
    """Descarga el MP3 desde Twilio con autenticación. Verifica tamaño y duración mínimos.

    `recording_url` puede venir sin extensión; añadimos `.mp3` si falta.
    Autenticación con API Key (no Auth Token) — la que tenemos en .env.
    """
    if not recording_url:
        return ResultadoDescarga(ok=False, motivo="recording_url vacía")

    salida_dir = salida_dir or _base_dir()
    salida_dir.mkdir(parents=True, exist_ok=True)
    destino = salida_dir / f"{call_sid}.mp3"

    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    key = os.environ.get("TWILIO_API_KEY_SID")
    secret = os.environ.get("TWILIO_API_KEY_SECRET")
    if not all([sid, key, secret]):
        return ResultadoDescarga(ok=False, motivo="faltan credenciales Twilio en .env")

    url = recording_url if recording_url.endswith(".mp3") else recording_url + ".mp3"
    try:
        r = requests.get(url, auth=HTTPBasicAuth(key, secret), timeout=60, stream=True)
        r.raise_for_status()
        h = hashlib.sha256()
        total = 0
        tmp = destino.with_suffix(".mp3.tmp")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                h.update(chunk)
                total += len(chunk)
        os.replace(tmp, destino)
    except Exception as e:
        return ResultadoDescarga(ok=False, motivo=f"fallo descarga: {e}")

    if total < min_bytes:
        return ResultadoDescarga(ok=False, ruta=destino, bytes=total,
                                 motivo=f"grabación demasiado pequeña ({total} bytes)")
    if duracion_s and duracion_s < min_duracion_s:
        return ResultadoDescarga(ok=False, ruta=destino, bytes=total, duracion_s=duracion_s,
                                 motivo=f"duración {duracion_s}s < {min_duracion_s}s")

    return ResultadoDescarga(ok=True, ruta=destino, bytes=total,
                              sha256=h.hexdigest(), duracion_s=duracion_s)
