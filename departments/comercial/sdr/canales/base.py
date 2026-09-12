"""Interfaz común de los canales del SDR Multicanal.

Cada canal (email, voz, WhatsApp, LinkedIn) implementa `Canal.contactar(...)`. El SDR
elige uno como canal principal por tipo de lead (§4.2 del v0.2) y los demás como
fallback secuencial.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

EstadoContacto = Literal["enviado", "fallido", "bloqueado", "deshabilitado"]


@dataclass
class ResultadoContacto:
    canal: str
    estado: EstadoContacto
    destino: str | None = None        # email, número, perfil...
    detalle: str = ""
    referencia_externa: str | None = None    # message_id SMTP, call_sid Twilio, etc.
    metadatos: dict = field(default_factory=dict)


class CanalDeshabilitado(RuntimeError):
    """Se intentó usar un canal que está apagado por configuración (flag/credencial)."""


class Canal(ABC):
    nombre: str = "abstract"

    @abstractmethod
    def disponible(self) -> tuple[bool, str]:
        """Devuelve (True, '') si el canal está listo para usarse; (False, motivo) si no.
        Los motivos típicos son flag desactivado o credenciales/recurso ausente."""

    @abstractmethod
    def contactar(self, *, destino: str, asunto: str | None, cuerpo: str,
                  lead: dict | None = None) -> ResultadoContacto:
        """Envía/coloca el contacto. `destino` es la dirección (email, número, URL perfil).
        Si el canal no está disponible, lanza `CanalDeshabilitado` con motivo claro."""
