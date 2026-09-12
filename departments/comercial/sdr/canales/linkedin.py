"""Canal LinkedIn — supervisado. La API oficial de LinkedIn no permite outbound automatizado
a perfiles que no son tu propia conexión. El v0.2 §9.2 acepta "automatización supervisada":
el sistema prepara el mensaje y lo encola para envío manual del operador. Sin LINKEDIN_*
configurado, el canal está deshabilitado.
"""
from __future__ import annotations

import os

from departments.comercial.sdr.canales.base import Canal, CanalDeshabilitado, ResultadoContacto


class LinkedInChannel(Canal):
    nombre = "linkedin"

    def disponible(self) -> tuple[bool, str]:
        if os.environ.get("LINKEDIN_ENABLED", "false").lower() != "true":
            return False, ("LinkedIn API restringida. El v0.2 §9.2 prescribe 'automatización supervisada'. "
                           "Activa con LINKEDIN_ENABLED=true para encolar mensajes a tu cola manual.")
        return True, ""

    def contactar(self, *, destino: str, asunto: str | None, cuerpo: str,
                  lead: dict | None = None) -> ResultadoContacto:
        ok, motivo = self.disponible()
        if not ok:
            raise CanalDeshabilitado(f"LinkedIn no disponible: {motivo}")
        # Modo supervisado: el "envío" es persistir el borrador para que el operador lo
        # mande desde su navegador. Aquí solo registramos la intención.
        return ResultadoContacto(
            canal=self.nombre, estado="enviado",
            destino=destino,
            detalle="Mensaje encolado para envío manual supervisado (LinkedIn).",
            metadatos={"asunto": asunto, "cuerpo": cuerpo, "lead": (lead or {}).get("id")},
        )
