"""Enrichment Specialist — verifica actualidad y calidad de contacto del lead (§2.4 v0.2).

Para Fase 0 trabaja con la información que ya trae Places: business_status, rating_count,
teléfono, web. Valida la checklist mínima del §8.2 que es realista alcanzar sin LLM:
    - business_status = OPERATIONAL
    - ratings_count >= 1 (señal de actividad pública)
    - >=1 canal de contacto (teléfono / web)

Si todo OK → transición a ENRIQUECIDO con tamaño estimado y señal de actualidad. Si falla
algún check → el lead permanece en CUALIFICADO con `problemas_enrichment` anotados (para
revisión manual o segundo pase con LLM).

El nombre del decisor y email directo quedan como follow-up: requieren LLM sobre el sitio
web, que se enciende cuando Fase 0 ya está superada y se entra en Fase 1.
"""
from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from core.events import Event, EventType
from departments.comercial.lifecycle import EstadoLead, LeadStore


@dataclass
class ResultadoEnrichment:
    procesados: int = 0
    enriquecidos: int = 0
    rechazados: int = 0           # se quedan en CUALIFICADO con problemas
    perdidos: int = 0             # business_status closed o sin contacto -> perdido
    detalle: dict[str, int] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)


def _tamano_estimado(ratings_count: int | None) -> str:
    """Proxy simple de tamaño/tráfico a partir del número de reseñas en Google."""
    n = ratings_count or 0
    if n >= 200:
        return "grande"
    if n >= 50:
        return "medio"
    if n >= 5:
        return "pequeno"
    return "minimo"


class Enrichment:
    """Verifica que cada lead CUALIFICADO cumple el checklist mínimo §8.2."""

    def __init__(self, *, lead_store: LeadStore, bus=None, max_workers: int = 4) -> None:
        self.lead_store = lead_store
        self.bus = bus
        self.max_workers = max_workers
        self._lock = threading.Lock()

    def procesar_todos(self, verbose: bool = True) -> ResultadoEnrichment:
        cualificados = self.lead_store.listar(EstadoLead.CUALIFICADO)
        res = ResultadoEnrichment()
        if verbose:
            print(f"[Enrichment] {len(cualificados)} leads cualificados a procesar")

        # Paralelizar por si en el futuro se hace fetch HTTP/LLM por lead. Hoy es CPU-bound
        # ligero, pero la interfaz queda preparada.
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futuros = {ex.submit(self.procesar, lead["id"]): lead for lead in cualificados}
            for fut in as_completed(futuros):
                lead = futuros[fut]
                try:
                    estado, motivo = fut.result()
                except Exception as e:
                    res.errores.append(f"{lead['id']}: {e}")
                    print(f"[Enrichment] {lead['id']}: {e}", file=sys.stderr)
                    continue
                res.procesados += 1
                with self._lock:
                    res.detalle[motivo] = res.detalle.get(motivo, 0) + 1
                    if estado == EstadoLead.ENRIQUECIDO:
                        res.enriquecidos += 1
                    elif estado == EstadoLead.PERDIDO:
                        res.perdidos += 1
                    else:
                        res.rechazados += 1

        if verbose:
            print(f"[Enrichment] enriquecidos={res.enriquecidos} "
                  f"sin_aprobar={res.rechazados} perdidos={res.perdidos}")
        return res

    # ── Núcleo de validación por lead ──────────────────────────────────────
    def procesar(self, lead_id: str) -> tuple[EstadoLead, str]:
        """Evalúa un lead y, si procede, lo transiciona a ENRIQUECIDO o PERDIDO.
        Devuelve (estado_final_observado, motivo) para que el resumen lo agrupe."""
        lead = self.lead_store.get(lead_id)
        if lead is None:
            return EstadoLead.PERDIDO, "lead_no_existe"
        meta = lead.get("metadatos_fuente") or {}
        contacto = lead.get("contacto") or {}

        problemas: list[str] = []
        business_status = meta.get("business_status")
        if business_status and business_status != "OPERATIONAL":
            # Cerrado, temporal, no operativo → eliminamos del pipeline.
            self.lead_store.transicionar(
                lead_id, EstadoLead.PERDIDO,
                razon=f"business_status={business_status}",
                detalle={"check": "operatividad"},
            )
            return EstadoLead.PERDIDO, "no_operativo"

        ratings_count = meta.get("ratings_count") or 0
        if ratings_count < 1:
            problemas.append("sin_reseñas")

        canales = [c for c in (contacto.get("telefono"), contacto.get("web")) if c]
        if not canales:
            problemas.append("sin_canales")

        if problemas:
            # Se queda en CUALIFICADO con anotación; no es trabajo terminado.
            lead["problemas_enrichment"] = problemas
            self.lead_store.k.add(self.lead_store.company, LeadStore.TIPO, lead_id, lead)
            return EstadoLead.CUALIFICADO, "checklist_incompleto"

        # Pasa: enriquecer con tamaño estimado y señal de actualidad.
        parches = {
            "tamano_estimado": _tamano_estimado(ratings_count),
            "actualidad_signal": {
                "ratings_count": ratings_count,
                "rating": meta.get("rating"),
                "business_status": business_status or "OPERATIONAL",
                "metodo": "google_places_business_status_y_resenas",
            },
            "checklists": {
                **(lead.get("checklists") or {}),
                "enrichment": {
                    "ok": True,
                    "criterios": ["operativo", "con_reseñas", "≥1 canal"],
                    "criterios_pendientes": ["decisor_identificado", "email_directo"],
                },
            },
        }
        self.lead_store.transicionar(
            lead_id, EstadoLead.ENRIQUECIDO,
            razon=f"Enrichment OK: {len(canales)} canal(es), {ratings_count} reseñas",
            detalle={"tamano": parches["tamano_estimado"]},
            parches=parches,
        )
        if self.bus is not None:
            self.bus.publish(Event(
                EventType.DEPT_TASK_COMPLETED, source="enrichment",
                payload={"lead": lead_id, "tamano": parches["tamano_estimado"]},
                company=self.lead_store.company,
            ))
        return EstadoLead.ENRIQUECIDO, "ok"
