"""Máquina de estados del pipeline (Módulo 2 del sistema nervioso).

Doce estados, transiciones validadas, historial inmutable, hooks aislados.
Ver `docs/MAQUINA_ESTADOS_LEAD.md` y `docs/DECISIONES_ARQUITECTONICAS.md#adr-002`.

Diseño deliberadamente desacoplado de la persistencia: la máquina recibe un
`LeadDoc` y devuelve uno actualizado. Quien lo persista (LeadStore / migración /
SDR) decide cuándo escribir al `KnowledgeStore`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Protocol

from core.lead_schema import LeadDoc


class EstadoPipeline(str, Enum):
    COLD              = "cold"               # enriquecido sin contactar
    QUEUED            = "queued"             # programado para contacto
    CONTACTING        = "contacting"         # llamada en curso (transitorio)
    NO_ANSWER         = "no_answer"          # no contestó
    CONTACTED         = "contacted"          # habló con no-decisor
    ENGAGED           = "engaged"            # decisor con interés
    SAMPLE_REQUESTED  = "sample_requested"   # pidió muestra
    SAMPLE_SENT       = "sample_sent"        # muestra enviada
    TRIAL             = "trial"              # ha probado
    CUSTOMER          = "customer"           # convertido
    LOST              = "lost"               # descartado con razón (reversible)
    DO_NOT_CALL       = "do_not_call"        # opt-out terminal


# Matriz de transiciones permitidas. Cualquier estado puede ir a DO_NOT_CALL
# (opt-out del cliente respeta siempre).
TRANSICIONES_VALIDAS: dict[EstadoPipeline, set[EstadoPipeline]] = {
    EstadoPipeline.COLD:             {EstadoPipeline.QUEUED, EstadoPipeline.LOST,
                                       EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.QUEUED:           {EstadoPipeline.CONTACTING, EstadoPipeline.COLD,
                                       EstadoPipeline.LOST, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.CONTACTING:       {EstadoPipeline.NO_ANSWER, EstadoPipeline.CONTACTED,
                                       EstadoPipeline.ENGAGED, EstadoPipeline.LOST,
                                       EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.NO_ANSWER:        {EstadoPipeline.QUEUED, EstadoPipeline.LOST,
                                       EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.CONTACTED:        {EstadoPipeline.QUEUED, EstadoPipeline.ENGAGED,
                                       EstadoPipeline.LOST, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.ENGAGED:          {EstadoPipeline.SAMPLE_REQUESTED, EstadoPipeline.QUEUED,
                                       EstadoPipeline.LOST, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.SAMPLE_REQUESTED: {EstadoPipeline.SAMPLE_SENT, EstadoPipeline.LOST,
                                       EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.SAMPLE_SENT:      {EstadoPipeline.TRIAL, EstadoPipeline.CUSTOMER,
                                       EstadoPipeline.LOST, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.TRIAL:            {EstadoPipeline.CUSTOMER, EstadoPipeline.LOST,
                                       EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.CUSTOMER:         {EstadoPipeline.LOST, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.LOST:             {EstadoPipeline.COLD, EstadoPipeline.DO_NOT_CALL},
    EstadoPipeline.DO_NOT_CALL:      set(),     # terminal duro
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TransicionInvalida(ValueError):
    """Se intentó una transición que la máquina de estados no permite."""


@dataclass
class TransicionPipeline:
    """Registro inmutable de una transición. Va al `lead.historial_pipeline`."""
    ts: str
    desde: str                              # EstadoPipeline.value
    a: str
    razon: str
    detalle: dict = field(default_factory=dict)
    evento_disparador: str = ""             # call_sid, message_id, manual, …


class HookTransicion(Protocol):
    """Cualquier objeto callable que reciba (lead, transicion) puede registrarse.

    Los hooks se invocan tras persistir la transición, en el orden de registro.
    Excepciones se loggean a stderr — NO interrumpen la transición.
    """
    def __call__(self, lead: LeadDoc, transicion: TransicionPipeline) -> None: ...


class PipelineMachine:
    """Motor sin estado propio. Aplica transiciones sobre `LeadDoc`s que recibe.

    No persiste — el caller decide cuándo escribir al `KnowledgeStore`. Esto la
    hace trivial de testear y agnóstica al backend.
    """

    def __init__(self) -> None:
        self._hooks: list[HookTransicion] = []

    def registrar_hook(self, hook: HookTransicion) -> None:
        self._hooks.append(hook)

    def quitar_hook(self, hook: HookTransicion) -> bool:
        try:
            self._hooks.remove(hook); return True
        except ValueError:
            return False

    # ── Validación ────────────────────────────────────────────────────────
    @staticmethod
    def puede_transicionar(desde: EstadoPipeline | str,
                            a: EstadoPipeline | str) -> bool:
        try:
            desde_e = EstadoPipeline(desde) if not isinstance(desde, EstadoPipeline) else desde
            a_e = EstadoPipeline(a) if not isinstance(a, EstadoPipeline) else a
        except ValueError:
            return False
        return a_e in TRANSICIONES_VALIDAS.get(desde_e, set())

    # ── Transición principal ─────────────────────────────────────────────
    def transicionar(self, lead: LeadDoc, nuevo: EstadoPipeline | str, *,
                     razon: str = "", detalle: dict | None = None,
                     evento_disparador: str = "") -> tuple[LeadDoc, TransicionPipeline]:
        """Aplica la transición. Devuelve (lead actualizado, registro de transición)."""
        if isinstance(nuevo, str):
            try:
                nuevo = EstadoPipeline(nuevo)
            except ValueError as e:
                raise TransicionInvalida(
                    f"Estado destino '{nuevo}' no es un EstadoPipeline válido. "
                    f"Válidos: {[s.value for s in EstadoPipeline]}"
                ) from e

        try:
            actual = EstadoPipeline(lead.estado_pipeline)
        except ValueError as e:
            raise TransicionInvalida(
                f"Lead '{lead.id}' tiene estado_pipeline inválido: "
                f"'{lead.estado_pipeline}'"
            ) from e

        permitidas = TRANSICIONES_VALIDAS.get(actual, set())
        if nuevo not in permitidas:
            raise TransicionInvalida(
                f"Transición no permitida {actual.value} → {nuevo.value} "
                f"(válidas desde {actual.value}: "
                f"{sorted(s.value for s in permitidas)})"
            )

        # Construir registro
        ahora = _now()
        registro = TransicionPipeline(
            ts=ahora, desde=actual.value, a=nuevo.value,
            razon=razon or "", detalle=detalle or {},
            evento_disparador=evento_disparador or "",
        )

        # Actualizar lead
        lead.estado_pipeline = nuevo.value
        lead.fecha_ultima_transicion = ahora
        lead.razon_ultima_transicion = razon or ""
        lead.actualizado_en = ahora

        # Append a historial_pipeline (preserva legacy `historial` aparte)
        hist = lead.metadatos_extra.setdefault("historial_pipeline", [])
        hist.append(asdict(registro))

        # Si la transición es a DO_NOT_CALL, marca el flag — siempre.
        if nuevo == EstadoPipeline.DO_NOT_CALL:
            lead.do_not_call = True

        # Disparar hooks (aislados)
        for hook in list(self._hooks):
            try:
                hook(lead, registro)
            except Exception as e:                          # noqa: BLE001
                print(f"[pipeline] hook {getattr(hook, '__name__', hook)} "
                      f"falló en {actual.value}→{nuevo.value}: {e}",
                      file=sys.stderr)

        return lead, registro


# ─────────────────────────────────────────────────────────────────────────────
#  Mapeo legacy completo (incluye EstadoLead → EstadoPipeline). Idéntico al de
#  lead_schema pero como dict de Enum→Enum para uso interno del motor.
# ─────────────────────────────────────────────────────────────────────────────

MAPEO_LEGACY_ESTADOS: dict[str, EstadoPipeline] = {
    "identificado":         EstadoPipeline.COLD,
    "cualificado":          EstadoPipeline.COLD,
    "enriquecido":          EstadoPipeline.COLD,
    "en_contacto":          EstadoPipeline.CONTACTING,
    "compromiso_reciproco": EstadoPipeline.ENGAGED,
    "muestra_enviada":      EstadoPipeline.SAMPLE_SENT,
    "cliente_activo":       EstadoPipeline.CUSTOMER,
    "en_riesgo":            EstadoPipeline.CUSTOMER,
    "perdido":              EstadoPipeline.LOST,
}


def mapear_legacy_estado(estado_legacy: str) -> EstadoPipeline:
    """Conversión defensiva. Default a COLD si el estado legacy no se reconoce."""
    return MAPEO_LEGACY_ESTADOS.get(estado_legacy, EstadoPipeline.COLD)
