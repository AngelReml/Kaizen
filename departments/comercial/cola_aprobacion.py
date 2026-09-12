"""Cola de Aprobación — el sistema NUNCA envía sin que el operador apruebe explícitamente.

Cada mensaje generado pasa por aquí: se persiste en Knowledge con estado `pendiente`. El
operador revisa, aprueba o rechaza. Solo los aprobados pueden enviarse, y el canal de
envío verifica que el token + hash coinciden (no se puede aprobar A y enviar B).

Tres barreras independientes — cualquiera ausente bloquea el envío:
  1. Token de aprobación EXISTE en Knowledge con estado=aprobado.
  2. Hash de aprobación COINCIDE con el del mensaje a enviar.
  3. Flag global KAIZEN_ENVIO_HABILITADO=true.
"""
from __future__ import annotations

import hashlib
import os
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Literal

from core.bloqueo import bloqueo_exclusivo
from core.knowledge import KnowledgeStore

EstadoAprobacion = Literal["pendiente", "aprobado", "enviando", "rechazado", "enviado"]
TIPO = "email_pendiente_aprobacion"

# R-09 (auditoria 2026-07-20): una aprobacion no caducaba nunca — un borrador aprobado
# podia enviarse semanas despues (lead ya dado de baja). TTL por defecto 72 h (alineado
# con la caducidad de las tarjetas del panel). Configurable por .env.
def _ttl_aprobacion_s() -> int:
    try:
        return int(os.environ.get("KAIZEN_APROBACION_TTL_SEGUNDOS", str(72 * 3600)))
    except ValueError:
        return 72 * 3600


# Locks por (company, pendiente_id) para el claim atomico compare-and-swap del envio.
_claim_locks: dict[str, threading.Lock] = {}
_claim_guard = threading.Lock()


def _lock_de(company: str, pendiente_id: str) -> threading.Lock:
    clave = f"{company}::{pendiente_id}"
    with _claim_guard:
        return _claim_locks.setdefault(clave, threading.Lock())


def _ruta_candado_claim(company: str, pendiente_id: str):
    """Ruta del candado ENTRE PROCESOS del claim de envío de un pendiente concreto.

    `_lock_de()` solo serializa hilos DENTRO de este proceso; el CLI y el panel
    son procesos distintos, así que dos claims simultáneos desde cada uno podían
    leer el mismo `knowledge.json` (estado 'aprobado') antes de que el otro
    escribiera 'enviando', y los dos ganaban la carrera. Candado propio, no el de
    `JsonKnowledge` (que se toma y suelta por operación, no por todo el ciclo
    leer-decidir-escribir de `reclamar_envio`).
    """
    from core.rutas import dir_state
    return dir_state() / "aprobacion_claims" / company / pendiente_id


class AprobacionCaducada(RuntimeError):
    """R-09: la aprobacion expiro (TTL). Requiere re-aprobacion antes de enviar."""


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _edad_segundos(iso: str | None) -> float:
    if not iso:
        return float("inf")
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except ValueError:
        return float("inf")


def hash_mensaje(canal: str, destino: str, asunto: str, cuerpo: str) -> str:
    """Hash determinista del contenido a enviar. Verifica integridad: el mensaje aprobado
    debe ser BIT-A-BIT idéntico al que se envía."""
    raw = f"{canal}\x1f{destino}\x1f{asunto}\x1f{cuerpo}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class EmailPendiente:
    id: str                     # UUID estable, key en Knowledge
    lead_id: str
    campaign_id: str
    canal: str
    destino: str
    asunto: str
    cuerpo: str
    hash_mensaje: str
    brand_review: dict
    estado: EstadoAprobacion
    creado_en: str
    aprobado_en: str | None = None
    aprobado_por: str | None = None
    enviado_en: str | None = None
    referencia_externa: str | None = None
    motivo_rechazo: str | None = None
    token_aprobacion: str | None = None
    razones_personalizacion: list[str] = field(default_factory=list)
    intentos_composer: int = 1


class EnvioSinAprobacion(RuntimeError):
    """Se intentó enviar un mensaje sin un token de aprobación válido."""


class ColaAprobacion:
    def __init__(self, knowledge: KnowledgeStore, company: str) -> None:
        self.k = knowledge
        self.company = company

    # ── Encolar (lo que hace el SDR.preparar) ───────────────────────────────
    def encolar(self, *, lead_id: str, canal: str, destino: str, asunto: str, cuerpo: str,
                brand_review: dict, campaign_id: str,
                razones_personalizacion: list[str] | None = None,
                intentos_composer: int = 1) -> EmailPendiente:
        pid = uuid.uuid4().hex
        pendiente = EmailPendiente(
            id=pid, lead_id=lead_id, campaign_id=campaign_id,
            canal=canal, destino=destino, asunto=asunto, cuerpo=cuerpo,
            hash_mensaje=hash_mensaje(canal, destino, asunto, cuerpo),
            brand_review=brand_review, estado="pendiente", creado_en=_ts(),
            razones_personalizacion=razones_personalizacion or [],
            intentos_composer=intentos_composer,
        )
        self.k.add(self.company, TIPO, pid, asdict(pendiente))
        return pendiente

    # ── Lecturas ────────────────────────────────────────────────────────────
    def get(self, pendiente_id: str) -> dict | None:
        return self.k.get(self.company, TIPO, pendiente_id)

    def listar(self, estado: EstadoAprobacion | None = None,
               campaign_id: str | None = None) -> list[dict]:
        items = list(self.k.all(self.company, TIPO).values())
        if estado:
            items = [x for x in items if x.get("estado") == estado]
        if campaign_id:
            items = [x for x in items if x.get("campaign_id") == campaign_id]
        return sorted(items, key=lambda x: x.get("creado_en", ""))

    def por_lead(self, lead_id: str) -> list[dict]:
        return [x for x in self.k.all(self.company, TIPO).values()
                if x.get("lead_id") == lead_id]

    # ── Aprobar / Rechazar ──────────────────────────────────────────────────
    def aprobar(self, pendiente_id: str, *, aprobado_por: str = "cli") -> dict:
        nodo = self._cargar(pendiente_id)
        if nodo["estado"] != "pendiente":
            raise ValueError(f"Solo se puede aprobar un pendiente; este está en '{nodo['estado']}'.")
        token = uuid.uuid4().hex
        nodo.update(estado="aprobado", aprobado_en=_ts(),
                    aprobado_por=aprobado_por, token_aprobacion=token)
        self.k.add(self.company, TIPO, pendiente_id, nodo)
        return nodo

    def rechazar(self, pendiente_id: str, motivo: str) -> dict:
        nodo = self._cargar(pendiente_id)
        if nodo["estado"] not in ("pendiente", "aprobado"):
            raise ValueError(f"No se puede rechazar desde '{nodo['estado']}'.")
        nodo.update(estado="rechazado", motivo_rechazo=motivo)
        self.k.add(self.company, TIPO, pendiente_id, nodo)
        return nodo

    def aprobar_campania(self, campaign_id: str, *, aprobado_por: str = "cli") -> list[dict]:
        out = []
        for nodo in self.listar(estado="pendiente", campaign_id=campaign_id):
            out.append(self.aprobar(nodo["id"], aprobado_por=aprobado_por))
        return out

    # ── Guard de envío: el corazón del requisito arquitectónico ─────────────
    def verificar_token(self, *, pendiente_id: str, token: str,
                        hash_a_enviar: str) -> dict:
        """Devuelve el nodo si todas las verificaciones pasan. Si no, lanza
        EnvioSinAprobacion. Esta función ES la barrera arquitectónica.
        R-09: ademas comprueba el TTL de la aprobacion (caducidad)."""
        nodo = self._cargar(pendiente_id)
        if nodo["estado"] not in ("aprobado", "enviando"):
            raise EnvioSinAprobacion(
                f"Pendiente '{pendiente_id}' está en estado '{nodo['estado']}', no 'aprobado'."
            )
        if not nodo.get("token_aprobacion") or nodo["token_aprobacion"] != token:
            raise EnvioSinAprobacion(
                f"Token de aprobación inválido para '{pendiente_id}'."
            )
        if nodo["hash_mensaje"] != hash_a_enviar:
            raise EnvioSinAprobacion(
                "El hash del mensaje a enviar NO coincide con el aprobado "
                "(asunto/cuerpo modificados tras la aprobación)."
            )
        # `>=` y no `>`: con TTL=N, a los N segundos exactos la aprobación YA ha caducado.
        # Con `>` el borde no cerraba, y en Windows `datetime.now()` tiene granularidad de
        # ~15,6 ms: aprobar y verificar dentro del mismo tick daba edad 0.0 y un TTL de 0
        # no expiraba nunca (test_r09_aprobacion_caduca_por_ttl, rojo intermitente).
        if _edad_segundos(nodo.get("aprobado_en")) >= _ttl_aprobacion_s():
            raise AprobacionCaducada(
                f"La aprobación de '{pendiente_id}' caducó (>= {_ttl_aprobacion_s()//3600} h). "
                "Vuelve a aprobarla antes de enviar (el lead pudo darse de baja entretanto).")
        return nodo

    def reclamar_envio(self, *, pendiente_id: str, token: str, hash_a_enviar: str,
                       idempotencia: str | None = None) -> dict:
        """R-09 — claim atómico compare-and-swap 'aprobado'→'enviando' ANTES del SMTP.

        Dos envíos concurrentes del mismo pendiente ya no pasan ambos: solo el PRIMERO
        obtiene el nodo y transiciona a 'enviando'; el segundo recibe EnvioSinAprobacion.
        Idempotencia: si ya está 'enviado'/'enviando' con la misma clave, no re-envía.

        R-09: `_lock_de()` (hilo) NO basta cuando el CLI y el panel son procesos
        distintos escribiendo el mismo `knowledge.json` — cada uno tiene su propia
        copia en memoria y su propio `threading.Lock`. El candado entre procesos
        envuelve el ciclo COMPLETO leer-decidir-escribir; dentro de él, `self.k.get()`
        (vía `verificar_token`/`_cargar`) fuerza la relectura desde disco antes de
        decidir, así que la decisión nunca se toma sobre una copia obsoleta.
        """
        with _lock_de(self.company, pendiente_id), \
                bloqueo_exclusivo(_ruta_candado_claim(self.company, pendiente_id)):
            nodo = self.verificar_token(pendiente_id=pendiente_id, token=token,
                                        hash_a_enviar=hash_a_enviar)
            if nodo["estado"] == "enviando":
                raise EnvioSinAprobacion(
                    f"'{pendiente_id}' ya está en envío (claim tomado): no se envía dos veces.")
            nodo.update(estado="enviando", envio_reclamado_en=_ts(),
                        idempotencia_key=idempotencia or nodo.get("idempotencia_key"))
            self.k.add(self.company, TIPO, pendiente_id, nodo)
            return nodo

    def revertir_reclamo(self, pendiente_id: str) -> dict:
        """Si el SMTP falla tras el claim, devuelve el pendiente a 'aprobado' (reintentable)."""
        with _lock_de(self.company, pendiente_id):
            nodo = self._cargar(pendiente_id)
            if nodo["estado"] == "enviando":
                nodo.update(estado="aprobado", envio_reclamado_en=None)
                self.k.add(self.company, TIPO, pendiente_id, nodo)
            return nodo

    def marcar_enviado(self, pendiente_id: str, *, referencia_externa: str | None = None) -> dict:
        with _lock_de(self.company, pendiente_id):
            nodo = self._cargar(pendiente_id)
            if nodo["estado"] not in ("aprobado", "enviando"):
                raise ValueError(f"Solo se marca enviado desde 'aprobado'/'enviando', no '{nodo['estado']}'.")
            nodo.update(estado="enviado", enviado_en=_ts(),
                        referencia_externa=referencia_externa)
            self.k.add(self.company, TIPO, pendiente_id, nodo)
            return nodo

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _cargar(self, pendiente_id: str) -> dict:
        nodo = self.k.get(self.company, TIPO, pendiente_id)
        if nodo is None:
            raise KeyError(f"Pendiente '{pendiente_id}' no existe en la cola de {self.company}.")
        return nodo


def envio_globalmente_habilitado() -> bool:
    """Tercera barrera: KAIZEN_ENVIO_HABILITADO=true en .env. Default: false."""
    return os.environ.get("KAIZEN_ENVIO_HABILITADO", "false").lower() == "true"
