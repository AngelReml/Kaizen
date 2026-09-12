"""Interfaz `DistanceProvider`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResultadoDistancia:
    minutos: float
    metros: float
    proveedor: str        # 'google_routes' | 'haversine'


class DistanceProvider(ABC):
    nombre: str = "abstract"

    @abstractmethod
    def medir(self, olat: float, olon: float, dlat: float, dlon: float,
              direccion_destino: str | None = None) -> ResultadoDistancia:
        """Devuelve duración en minutos y distancia en metros de origen a destino.
        `direccion_destino` puede usarse por proveedores que prefieren texto (Routes lo acepta)."""
