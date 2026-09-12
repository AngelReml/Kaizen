"""Puente aditivo entre el flujo real del Researcher (Fase 0, legacy `LeadStore`) y el
modelo canonico de KAIZEN-D01 (`PipelineCanonico`, coleccion `lead_canon`).

No sustituye nada: el `LeadStore` legado sigue siendo la fuente de verdad de la que
dependen metricas y gates de Fase 0 (`lifecycle.py`, `metricas.py`). Este modulo solo
espeja, ADITIVAMENTE, cada lead cualificado hacia `lead_canon` para que las
herramientas de directores que ya hablan D01 (comite, cumplimiento, Atribuidor) tengan
datos reales que consultar.

`construir_lead_canonico` es PURA: sin red, sin knowledge, solo mapeo de campos.
`dar_alta_canonico` es la unica funcion que toca el `PipelineCanonico` (I/O de knowledge).
"""
from __future__ import annotations

import re
import unicodedata

from departments.comercial.cubo_serie_d import GateLegal, PipelineCanonico
from departments.comercial.fuentes.base import CandidatoCrudo


def _slug(texto: str) -> str:
    """Slug estable para el ID del lead canonico. Mismo criterio que
    `departments.comercial.researcher._slug` (duplicado a proposito: este modulo debe
    permanecer puro y sin dependencias circulares con `researcher.py`)."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s-]", "", t)
    return re.sub(r"[\s_]+", "_", t).strip("_")[:64]


def construir_lead_canonico(cand: CandidatoCrudo, decision, anillo_res, *, ts: str) -> dict:
    """Mapea un `CandidatoCrudo` aceptado por ICP/anillo a un dict que satisface los
    gates S1 (procedencia) y S2 (contacto) de `PipelineCanonico.alta_lead`.

    - `id`: mismo slug del nombre que usa el `LeadStore` legado (I-consistencia entre
      ambos almacenes; no es una garantia de igualdad de ID, solo el mismo criterio).
    - `fuentes[0].url`: se construye a partir de `cand.id_externo` (place_id de Google)
      como URL publica real del listado de Google Maps.
    - `fuentes[0].fecha`: el `ts` de la pasada (nunca `datetime.now()`; testeable).
    - `contacto.publicado_por_el_negocio`: True SOLO si la propia ficha de Google
      Business (metadatos oficiales) trae telefono o web; si ambos estan vacios el
      contacto queda `{}` (no bloquea S2, que solo exige el campo si `contacto` es
      truthy).
    """
    id_externo = cand.id_externo or ""
    url = f"https://www.google.com/maps/place/?q=place_id:{id_externo}"
    fuentes = [{"nombre": cand.fuente, "id_externo": id_externo, "url": url,
                "fecha": ts, "tipo": "WEB"}]

    metadatos = cand.metadatos or {}
    telefono = metadatos.get("telefono") or ""
    web = metadatos.get("web") or ""
    contacto: dict = {}
    if telefono or web:
        contacto = {"telefono": telefono, "web": web, "publicado_por_el_negocio": True}

    return {
        "id": _slug(cand.nombre),
        "nombre": cand.nombre,
        "categoria_icp": decision.categoria,
        "prioridad_icp": decision.prioridad,
        "anillo": anillo_res.anillo,
        "ubicacion": {**(cand.ubicacion or {}), "direccion": cand.direccion},
        "distancia_minutos": anillo_res.distancia_minutos,
        "distancia_metros": anillo_res.distancia_metros,
        "distancia_provider": anillo_res.proveedor,
        "fuentes": fuentes,
        "contacto": contacto,
        "descripcion": cand.descripcion,
        "place_types": list(cand.place_types or []),
        "icp_match": {"senal": decision.senal, "peso": decision.peso,
                      "razon": decision.razones[0] if decision.razones else ""},
    }


def dar_alta_canonico(pipeline: PipelineCanonico, lead: dict) -> dict | None:
    """Alta idempotente en `lead_canon`. Anade la comprobacion de duplicado que
    `PipelineCanonico.alta_lead` no hace, y degrada un `GateLegal` a `None` en vez de
    propagarlo: un lead que no supera los gates D01 no debe tumbar la pasada de
    Fase 0 que lo origino."""
    if pipeline.k.get(pipeline.tenant, "lead_canon", lead["id"]) is not None:
        return None
    try:
        return pipeline.alta_lead(lead)
    except GateLegal:
        return None
