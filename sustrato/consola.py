"""Consola segura para Windows y logging del sustrato (canonico 10.3 y 0.5).

- safe_print: todo print de cara al operador pasa por aqui. Ante
  UnicodeEncodeError (bug conocido cp1252 con el simbolo euro y acentos)
  reintenta sustituyendo euro por EUR y degradando caracteres. La
  sustitucion es SOLO para consola; en ficheros y BD se escribe euro normal.
- log: una linea por evento, formato exacto
  ISO8601Z | NIVEL | modulo | mensaje | clave1=valor1 clave2=valor2
  en logs/kaizen_YYYYMMDD.log (rotacion diaria por nombre de fichero).
  PROHIBIDO emojis. Valores de claves sensibles se ocultan.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

_RAIZ = Path(__file__).resolve().parent.parent
NIVELES = ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL")
_MARCAS_SENSIBLES = ("KEY", "TOKEN", "SECRET", "SID", "PASSWORD")


def ts_iso8601z() -> str:
    """UTC ISO-8601 con milisegundos y sufijo Z (canonico 0.5)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def safe_print(texto: str) -> None:
    try:
        print(texto)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "cp1252"
        degradado = (
            texto.replace("€", "EUR")
            .encode(enc, errors="replace")
            .decode(enc, errors="replace")
        )
        print(degradado)


def _dir_logs() -> Path:
    # KAIZEN_LOGS_DIR solo para inyeccion en tests; por defecto logs/ del repo.
    d = Path(os.environ.get("KAIZEN_LOGS_DIR", _RAIZ / "logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(nivel: str, modulo: str, mensaje: str, **claves) -> str:
    """Escribe la linea de log y la devuelve (para tests). Nunca lanza."""
    if nivel not in NIVELES:
        nivel = "INFO"
    partes = []
    for k, v in claves.items():
        if any(m in k.upper() for m in _MARCAS_SENSIBLES):
            v = "[oculto]"
        partes.append(f"{k}={v}")
    cola = (" | " + " ".join(partes)) if partes else ""
    linea = f"{ts_iso8601z()} | {nivel} | {modulo} | {mensaje}{cola}"
    try:
        fichero = _dir_logs() / f"kaizen_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        with open(fichero, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass
    return linea
