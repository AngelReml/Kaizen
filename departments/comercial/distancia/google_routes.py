"""Distancia logística real vía Google Routes API v2 (computeRoutes).

Usa lat/lon en origen y destino — más fiable que dirección de texto para coordenadas que
ya tenemos de Places. Cachea en memoria por (origen, destino) redondeados para no pagar
dos veces la misma ruta dentro de una pasada.
"""
from __future__ import annotations

import os
import threading

import requests

from departments.comercial.distancia.base import DistanceProvider, ResultadoDistancia

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


class GoogleRoutesProvider(DistanceProvider):
    nombre = "google_routes"

    def __init__(self, api_key: str | None = None, timeout: int = 10) -> None:
        self.key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not self.key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY no encontrada en el entorno.")
        self.timeout = timeout
        self._cache: dict[tuple, ResultadoDistancia] = {}
        self._cache_lock = threading.Lock()

    def medir(self, olat: float, olon: float, dlat: float, dlon: float,
              direccion_destino: str | None = None) -> ResultadoDistancia:
        clave = (round(olat, 5), round(olon, 5), round(dlat, 5), round(dlon, 5))
        with self._cache_lock:
            if clave in self._cache:
                return self._cache[clave]
        payload = {
            "origin": {"location": {"latLng": {"latitude": olat, "longitude": olon}}},
            "destination": {"location": {"latLng": {"latitude": dlat, "longitude": dlon}}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",   # determinista; coste mínimo
        }
        r = requests.post(
            URL,
            headers={"Content-Type": "application/json",
                     "X-Goog-Api-Key": self.key,
                     "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"},
            json=payload, timeout=self.timeout,
        )
        r.raise_for_status()
        rutas = r.json().get("routes", [])
        if not rutas:
            raise RuntimeError(f"Google Routes no encontró ruta entre {clave[:2]} y {clave[2:]}")
        rt = rutas[0]
        # `duration` viene como cadena "1982s"; parseamos.
        dur_str = rt.get("duration", "0s")
        segundos = float(dur_str.rstrip("s")) if isinstance(dur_str, str) else float(dur_str)
        metros = float(rt.get("distanceMeters", 0))
        res = ResultadoDistancia(minutos=segundos / 60.0, metros=metros, proveedor=self.nombre)
        with self._cache_lock:
            self._cache[clave] = res
        return res


def get_distance_provider() -> DistanceProvider:
    """Selector con preferencia por Routes. Cae a haversine con aviso si falta la clave."""
    import sys
    from departments.comercial.distancia.haversine import HaversineProvider
    if os.environ.get("GOOGLE_MAPS_API_KEY"):
        return GoogleRoutesProvider()
    print("[distancia] GOOGLE_MAPS_API_KEY ausente — usando haversine (aproximación recta).",
          file=sys.stderr)
    return HaversineProvider()
