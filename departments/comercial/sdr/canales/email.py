"""Canal Email — funcional desde Fase 1. Reusa `agentes.smtp_send`.

REQUISITO ARQUITECTÓNICO (instrucción explícita del operador, Fase 1):
el SDR NO PUEDE enviar nada sin aprobación. Este canal aplica tres barreras antes de
tocar SMTP, todas independientes:

  1. `KAIZEN_ENVIO_HABILITADO=true` en el entorno (default: false).
  2. Token de aprobación presente y existente en la Cola con `estado=aprobado`.
  3. Hash del mensaje a enviar IDÉNTICO al hash del aprobado (no se puede aprobar A y
     enviar B).

Si cualquiera de las tres falla → `EnvioSinAprobacion`. El canal no envía.
"""
from __future__ import annotations

import os

from departments.comercial.cola_aprobacion import (
    ColaAprobacion, EnvioSinAprobacion, envio_globalmente_habilitado, hash_mensaje,
)
from departments.comercial.sdr.canales.base import Canal, CanalDeshabilitado, ResultadoContacto


class EmailChannel(Canal):
    nombre = "email"

    def disponible(self) -> tuple[bool, str]:
        faltan = [v for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS") if not os.environ.get(v)]
        if faltan:
            return False, f"Faltan en .env: {', '.join(faltan)}"
        if not envio_globalmente_habilitado():
            return False, "KAIZEN_ENVIO_HABILITADO=false (modo composición/revisión, no envío)"
        return True, ""

    def contactar(self, *, destino: str, asunto: str | None, cuerpo: str,
                  lead: dict | None = None,
                  aprobacion: dict | None = None) -> ResultadoContacto:
        """Envío directo PROHIBIDO sin `aprobacion`. Para uso normal, llamar a
        `enviar_pendiente(cola, pendiente_id)` (más legible y verifica todo).
        """
        if not asunto:
            raise ValueError("EmailChannel requiere un asunto.")
        if aprobacion is None:
            raise EnvioSinAprobacion(
                "Envío rechazado: este canal no acepta llamadas sin un objeto `aprobacion` "
                "con {cola, pendiente_id, token}. Usa enviar_pendiente() o el flujo del SDR."
            )
        cola: ColaAprobacion = aprobacion["cola"]
        pendiente_id: str = aprobacion["pendiente_id"]
        token: str = aprobacion["token"]
        return self._enviar(cola, pendiente_id, token, destino, asunto, cuerpo)

    def enviar_pendiente(self, cola: ColaAprobacion, pendiente_id: str) -> ResultadoContacto:
        """Camino de alto nivel: lee el pendiente, verifica las 3 barreras, envía y marca."""
        nodo = cola.get(pendiente_id)
        if nodo is None:
            raise EnvioSinAprobacion(f"Pendiente '{pendiente_id}' no existe en la cola.")
        return self._enviar(
            cola, pendiente_id,
            nodo.get("token_aprobacion") or "",
            nodo["destino"], nodo["asunto"], nodo["cuerpo"],
        )

    def _enviar(self, cola: ColaAprobacion, pendiente_id: str, token: str,
                destino: str, asunto: str, cuerpo: str) -> ResultadoContacto:
        # Barrera 1: flag global.
        if not envio_globalmente_habilitado():
            raise EnvioSinAprobacion(
                "KAIZEN_ENVIO_HABILITADO=false. Modo composición/revisión activo, "
                "sin SMTP. Define KAIZEN_ENVIO_HABILITADO=true cuando estés listo."
            )
        # Barrera 2 + 3 + R-09: claim atómico CAS 'aprobado'→'enviando' ANTES del SMTP.
        # Verifica token, hash y TTL, y garantiza exactamente-una-vez ante concurrencia.
        hash_a_enviar = hash_mensaje(self.nombre, destino, asunto, cuerpo)
        cola.reclamar_envio(pendiente_id=pendiente_id, token=token,
                            hash_a_enviar=hash_a_enviar,
                            idempotencia=f"{pendiente_id}:{hash_a_enviar[:16]}")

        # Candado AI Act art. 50 por fecha (E4): desde 2026-08-02 el cuerpo debe llevar el
        # disclosure de IA o NO sale. Va DELANTE del SMTP; si corta, se libera el claim.
        from core.aiact_gate import exigir_transparencia, AIActSinTransparencia
        try:
            exigir_transparencia(cuerpo, canal=self.nombre)
        except AIActSinTransparencia:
            cola.revertir_reclamo(pendiente_id)
            raise

        # Comprobación de credenciales SMTP justo antes del envío.
        faltan = [v for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS") if not os.environ.get(v)]
        if faltan:
            cola.revertir_reclamo(pendiente_id)               # el claim se libera: reintentable
            raise CanalDeshabilitado(f"SMTP no configurado: faltan {', '.join(faltan)}")

        from agentes import smtp_send
        try:
            smtp_send(destino, asunto, cuerpo)
        except Exception as e:
            cola.revertir_reclamo(pendiente_id)               # fallo SMTP: se libera el claim
            return ResultadoContacto(canal=self.nombre, estado="fallido",
                                     destino=destino, detalle=str(e))
        # Marcar enviado en la cola (auditoría): 'enviando' → 'enviado'.
        cola.marcar_enviado(pendiente_id, referencia_externa=f"smtp:{destino}")
        return ResultadoContacto(canal=self.nombre, estado="enviado",
                                 destino=destino, referencia_externa=pendiente_id,
                                 detalle="SMTP envío OK (post-aprobación verificada)")
