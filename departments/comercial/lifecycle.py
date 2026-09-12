"""Lifecycle del lead — máquina de estados con persistencia inmutable de transiciones.

Implementa la regla fundacional del v0.2 §3.4 "NO SE PIERDE NADA": cada lead guarda
todo su historial de transiciones, fuentes, checklists y decisiones. La fuente de verdad
operativa es `core.knowledge.KnowledgeStore`; el Diario se mantiene como vista humana.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class EstadoLead(str, Enum):
    IDENTIFICADO         = "identificado"          # Researcher detectó candidato
    CUALIFICADO          = "cualificado"           # Pasó el ICP
    ENRIQUECIDO          = "enriquecido"           # Contacto + decisor + actualidad verificados
    EN_CONTACTO          = "en_contacto"           # SDR ha intentado contactar
    COMPROMISO_RECIPROCO = "compromiso_reciproco"  # Cliente expresa intención verificable
    MUESTRA_ENVIADA      = "muestra_enviada"       # AE despachó muestra gratuita
    CLIENTE_ACTIVO       = "cliente_activo"        # Primer pedido pagado y recibido
    EN_RIESGO            = "en_riesgo"             # Caída de frecuencia o señal de churn
    PERDIDO              = "perdido"               # Descartado, sin respuesta o churn confirmado


# Transiciones válidas. Cualquier estado puede caer a PERDIDO (descarte/abandono).
TRANSICIONES_VALIDAS: dict[EstadoLead, set[EstadoLead]] = {
    EstadoLead.IDENTIFICADO:         {EstadoLead.CUALIFICADO, EstadoLead.PERDIDO},
    EstadoLead.CUALIFICADO:          {EstadoLead.ENRIQUECIDO, EstadoLead.PERDIDO},
    EstadoLead.ENRIQUECIDO:          {EstadoLead.EN_CONTACTO, EstadoLead.PERDIDO},
    EstadoLead.EN_CONTACTO:          {EstadoLead.COMPROMISO_RECIPROCO, EstadoLead.PERDIDO},
    EstadoLead.COMPROMISO_RECIPROCO: {EstadoLead.MUESTRA_ENVIADA, EstadoLead.PERDIDO},
    EstadoLead.MUESTRA_ENVIADA:      {EstadoLead.CLIENTE_ACTIVO, EstadoLead.PERDIDO},
    EstadoLead.CLIENTE_ACTIVO:       {EstadoLead.EN_RIESGO, EstadoLead.PERDIDO},
    EstadoLead.EN_RIESGO:            {EstadoLead.CLIENTE_ACTIVO, EstadoLead.PERDIDO},
    EstadoLead.PERDIDO:              set(),         # estado terminal
}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Transicion:
    ts: str
    desde: str | None
    a: str
    razon: str
    detalle: dict = field(default_factory=dict)


class TransicionInvalida(ValueError):
    """Se intentó una transición que la máquina de estados no permite."""


class LeadStore:
    """Persistencia + máquina de estados sobre `KnowledgeStore`.

    Cada lead se guarda como nodo `lead` con el JSON íntegro. El historial de transiciones
    vive dentro del propio nodo (`historial: [...]`) para mantener la regla "no se pierde
    nada" incluso si el sistema se reinicia entre fases.
    """

    TIPO = "lead"

    def __init__(self, knowledge, company: str) -> None:
        self.k = knowledge
        self.company = company

    # ── CRUD básico ─────────────────────────────────────────────────────────
    def crear(self, lead_id: str, datos: dict, razon: str = "identificado por Researcher") -> dict:
        if self.get(lead_id) is not None:
            raise ValueError(f"Lead '{lead_id}' ya existe en {self.company}")
        ahora = _ts()
        nodo = {
            **datos,
            "id": lead_id,
            "company": self.company,
            "estado": EstadoLead.IDENTIFICADO.value,
            "creado_en": ahora,
            "actualizado_en": ahora,
            "historial": [asdict(Transicion(ts=ahora, desde=None,
                                            a=EstadoLead.IDENTIFICADO.value,
                                            razon=razon, detalle={}))],
        }
        self.k.add(self.company, self.TIPO, lead_id, nodo)
        return nodo

    def get(self, lead_id: str) -> dict | None:
        try:
            return self.k.get(self.company, self.TIPO, lead_id)
        except AttributeError:
            return self.k.all(self.company, self.TIPO).get(lead_id)

    def listar(self, estado: EstadoLead | None = None) -> list[dict]:
        todos = list(self.k.all(self.company, self.TIPO).values())
        if estado is None:
            return todos
        return [n for n in todos if n.get("estado") == estado.value]

    def contar_por_estado(self) -> dict[str, int]:
        cuentas: dict[str, int] = {e.value: 0 for e in EstadoLead}
        for n in self.k.all(self.company, self.TIPO).values():
            cuentas[n.get("estado", "?")] = cuentas.get(n.get("estado", "?"), 0) + 1
        return cuentas

    # ── Transiciones ────────────────────────────────────────────────────────
    def transicionar(self, lead_id: str, nuevo: EstadoLead, razon: str,
                     detalle: dict | None = None, parches: dict | None = None) -> dict:
        """Pasa el lead a `nuevo`. Registra la transición en el historial. Si la máquina
        no la permite, lanza `TransicionInvalida` (no degrada en silencio)."""
        nodo = self.get(lead_id)
        if nodo is None:
            raise KeyError(f"Lead '{lead_id}' no existe en {self.company}")
        actual = EstadoLead(nodo["estado"])
        permitidas = TRANSICIONES_VALIDAS.get(actual, set())
        if nuevo not in permitidas:
            raise TransicionInvalida(
                f"Transición no permitida {actual.value} → {nuevo.value} "
                f"(válidas desde {actual.value}: {[s.value for s in permitidas]})"
            )
        ahora = _ts()
        nodo["estado"] = nuevo.value
        nodo["actualizado_en"] = ahora
        nodo.setdefault("historial", []).append(asdict(Transicion(
            ts=ahora, desde=actual.value, a=nuevo.value,
            razon=razon, detalle=detalle or {},
        )))
        if parches:
            for k, v in parches.items():
                nodo[k] = v
        self.k.add(self.company, self.TIPO, lead_id, nodo)
        return nodo
