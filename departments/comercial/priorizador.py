"""Priorizador — ordena los leads enriquecidos para que el SDR ataque primero los mejores.

Criterio (data-driven sobre lo que el Researcher/Enrichment ya pusieron en el lead):
  1. Anillo ASC (0 primero — más cerca de Cieza, logística más barata).
  2. Prioridad ICP DESC (ALTA > MEDIA > BAJA).
  3. ratings_count DESC (más reseñas → más actividad pública).
  4. rating DESC (mejor reputación → mejor encaje narrativo).
  5. Alfabético por nombre (desempate determinista para tests).
"""
from __future__ import annotations

from dataclasses import dataclass

from departments.comercial.lifecycle import EstadoLead, LeadStore

PRIORIDAD_VAL = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}


@dataclass(frozen=True)
class ClavePrioridad:
    anillo: int
    prioridad: int        # 3=ALTA, 2=MEDIA, 1=BAJA (mayor = antes)
    ratings_count: int
    rating: float


def clave(lead: dict) -> tuple:
    meta = lead.get("metadatos_fuente") or {}
    return (
        lead.get("anillo", 99),
        -PRIORIDAD_VAL.get(lead.get("prioridad_icp", "BAJA"), 0),
        -(meta.get("ratings_count") or 0),
        -(meta.get("rating") or 0),
        lead.get("nombre", "") or "",
    )


class Priorizador:
    def __init__(self, lead_store: LeadStore) -> None:
        self.lead_store = lead_store

    def cola(self, *, estado: EstadoLead = EstadoLead.ENRIQUECIDO,
             limite: int | None = None, prioridades: tuple[str, ...] | None = None,
             excluir_lead_ids: set[str] | None = None) -> list[dict]:
        leads = self.lead_store.listar(estado)
        if prioridades:
            leads = [l for l in leads if l.get("prioridad_icp") in prioridades]
        if excluir_lead_ids:
            leads = [l for l in leads if l.get("id") not in excluir_lead_ids]
        leads.sort(key=clave)
        return leads[:limite] if limite else leads
