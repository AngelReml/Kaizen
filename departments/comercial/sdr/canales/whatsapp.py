"""Canal WhatsApp — stub controlado por flag.

Sandbox de Twilio sirve solo para tests internos contra el propio número del operador
(prefijo "join <code>" requerido). NO sirve para contactar leads HORECA. El operador debe
gestionar el sender registration con Meta (verificación + plantillas) antes de operar.

Mientras WHATSAPP_ENABLED != "true", `contactar` lanza `CanalDeshabilitado` con motivo
explícito. Cuando se active, este adapter usa la Twilio Conversations / Messages API con
canal whatsapp:+ — código preparado, falta credencial de production.
"""
from __future__ import annotations

import os

import requests
from requests.auth import HTTPBasicAuth

from departments.comercial.sdr.canales.base import Canal, CanalDeshabilitado, ResultadoContacto

URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class WhatsAppChannel(Canal):
    nombre = "whatsapp"

    def disponible(self) -> tuple[bool, str]:
        if os.environ.get("WHATSAPP_ENABLED", "false").lower() != "true":
            return False, ("WhatsApp Business no verificado — usando solo sandbox en tests internos. "
                           "Activa con sender registrado en Meta y WHATSAPP_ENABLED=true.")
        faltan = [v for v in (
            "TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_WHATSAPP_FROM",
        ) if not os.environ.get(v)]
        if faltan:
            return False, f"Faltan en .env: {', '.join(faltan)}"
        return True, ""

    def contactar(self, *, destino: str, asunto: str | None, cuerpo: str,
                  lead: dict | None = None) -> ResultadoContacto:
        ok, motivo = self.disponible()
        if not ok:
            raise CanalDeshabilitado(f"WhatsApp no disponible: {motivo}")
        sid    = os.environ["TWILIO_ACCOUNT_SID"]
        key    = os.environ["TWILIO_API_KEY_SID"]
        secret = os.environ["TWILIO_API_KEY_SECRET"]
        frm    = os.environ["TWILIO_WHATSAPP_FROM"]   # whatsapp:+34xxxxxxxxx
        a      = destino if destino.startswith("whatsapp:") else f"whatsapp:{destino}"
        r = requests.post(URL.format(sid=sid), auth=HTTPBasicAuth(key, secret),
                          data={"From": frm, "To": a, "Body": cuerpo}, timeout=30)
        if r.status_code >= 400:
            return ResultadoContacto(canal=self.nombre, estado="fallido", destino=destino,
                                     detalle=f"{r.status_code}: {r.text[:200]}")
        return ResultadoContacto(canal=self.nombre, estado="enviado", destino=destino,
                                 referencia_externa=r.json().get("sid"))
