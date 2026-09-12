"""Interfaz `FuenteLeads` y `CandidatoCrudo`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CandidatoCrudo:
    fuente: str                       # 'google_places' | 'ddgs' | ...
    id_externo: str                   # ID estable en la fuente (p. ej. place_id de Google)
    nombre: str
    direccion: str
    ubicacion: dict                   # {"lat": float, "lon": float}
    tipo_principal: str | None        # primary_type de Places, o el más relevante
    place_types: list[str] = field(default_factory=list)
    descripcion: str = ""             # texto libre del establecimiento
    metadatos: dict = field(default_factory=dict)   # campos extra (rating, web, teléfono…)


class FuenteLeads(ABC):
    nombre: str = "abstract"

    @abstractmethod
    def buscar(self, query: str, *, centro: dict | None = None, radio_m: int = 30000,
               max_resultados: int = 20) -> list[CandidatoCrudo]:
        """Busca candidatos. `centro` es {"lat","lon"} para sesgar geográficamente; `radio_m`
        es radio en metros para el bias. Devuelve hasta `max_resultados`."""
