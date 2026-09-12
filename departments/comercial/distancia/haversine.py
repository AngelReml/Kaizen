"""Fallback sin red: haversine + velocidad media de carretera.

Aproximación honesta: la línea recta multiplicada por un factor de sinuosidad típico
(~1.3) y dividida por velocidad media. Solo se usa si Google Routes no está disponible;
el `get_distance_provider` deja claro en stderr cuándo se cae aquí.
"""
from __future__ import annotations

import math

from departments.comercial.distancia.base import DistanceProvider, ResultadoDistancia

VELOCIDAD_MEDIA_KMH = 90.0     # mix autovía/nacional típico Murcia; calibrado vs Google Routes
FACTOR_SINUOSIDAD  = 1.2        # camino real / línea recta para la región


class HaversineProvider(DistanceProvider):
    nombre = "haversine"

    def medir(self, olat: float, olon: float, dlat: float, dlon: float,
              direccion_destino: str | None = None) -> ResultadoDistancia:
        km_recta = _haversine_km(olat, olon, dlat, dlon)
        km_estim = km_recta * FACTOR_SINUOSIDAD
        minutos = (km_estim / VELOCIDAD_MEDIA_KMH) * 60.0
        return ResultadoDistancia(minutos=minutos, metros=km_estim * 1000.0, proveedor=self.nombre)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))
