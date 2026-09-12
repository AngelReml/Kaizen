"""Fuente real: Google Places API (New) — searchText.

Doc oficial: https://developers.google.com/maps/documentation/places/web-service/text-search
Devuelve `CandidatoCrudo` con id de Places, nombre, dirección formateada, ubicación, tipo
principal, lista completa de types, y metadatos útiles (rating, web, teléfono, business_status).

Pricing nota: cada llamada cuesta ~$0.032 con el SKU Text Search Pro de Places New.
"""
from __future__ import annotations

import os

import requests

from departments.comercial.fuentes.base import CandidatoCrudo, FuenteLeads

URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.primaryType,places.types,places.businessStatus,places.rating,"
    "places.userRatingCount,places.nationalPhoneNumber,places.internationalPhoneNumber,"
    "places.websiteUri,places.editorialSummary"
)


class GooglePlacesFuente(FuenteLeads):
    nombre = "google_places"

    def __init__(self, api_key: str | None = None, region_code: str = "ES",
                 language_code: str = "es", timeout: int = 15) -> None:
        self.key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not self.key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY no encontrada en el entorno.")
        self.region_code = region_code
        self.language_code = language_code
        self.timeout = timeout

    def buscar(self, query: str, *, centro: dict | None = None, radio_m: int = 30000,
               max_resultados: int = 20) -> list[CandidatoCrudo]:
        payload: dict = {
            "textQuery": query,
            "languageCode": self.language_code,
            "regionCode": self.region_code,
            "maxResultCount": min(max(max_resultados, 1), 20),     # API máximo 20 por petición
        }
        if centro:
            # Places New limita el radio del bias a 50_000 metros (validado contra docs).
            radio_efectivo = min(max(radio_m, 1), 50_000)
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": centro["lat"], "longitude": centro["lon"]},
                    "radius": radio_efectivo,
                }
            }
        r = requests.post(
            URL,
            headers={"Content-Type": "application/json",
                     "X-Goog-Api-Key": self.key,
                     "X-Goog-FieldMask": FIELD_MASK},
            json=payload, timeout=self.timeout,
        )
        r.raise_for_status()
        out: list[CandidatoCrudo] = []
        for p in r.json().get("places", []):
            loc = p.get("location") or {}
            nombre = (p.get("displayName") or {}).get("text", "")
            if not nombre:
                continue
            out.append(CandidatoCrudo(
                fuente=self.nombre,
                id_externo=p.get("id", ""),
                nombre=nombre,
                direccion=p.get("formattedAddress", ""),
                ubicacion={"lat": loc.get("latitude"), "lon": loc.get("longitude")},
                tipo_principal=p.get("primaryType"),
                place_types=list(p.get("types") or []),
                descripcion=(p.get("editorialSummary") or {}).get("text", ""),
                metadatos={
                    "business_status": p.get("businessStatus"),
                    "rating": p.get("rating"),
                    "ratings_count": p.get("userRatingCount"),
                    "telefono": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
                    "web": p.get("websiteUri"),
                },
            ))
        return out
