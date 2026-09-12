"""Clasificación geográfica por anillos (§5.4 del v0.2).

Anillo 0: Cieza y colindantes (<20 min)
Anillo 1: Murcia, Molina, Yecla, Jumilla (<45 min)
Anillo 2: Cartagena, Lorca, Caravaca (<90 min)
Anillo 3: el resto (>90 min) — decisión del Director o escalada al empresario.

Activación gradual: solo se prospecta el Anillo N+1 cuando el Anillo N está al 60% de
cobertura. Esa lógica vive en el Director Comercial; este módulo solo clasifica.
"""
from __future__ import annotations

from dataclasses import dataclass

from departments.comercial.distancia.base import DistanceProvider, ResultadoDistancia

# Límite superior en minutos para cada anillo (inclusive). El último es infinito.
LIMITES_ANILLOS_MIN: dict[int, float] = {0: 20, 1: 45, 2: 90, 3: float("inf")}


@dataclass
class ResultadoAnillo:
    anillo: int
    distancia_minutos: float
    distancia_metros: float
    proveedor: str
    activo: bool                   # según max_anillo_activo del ICP


class ClasificadorAnillos:
    def __init__(self, distancia: DistanceProvider, origen_lat: float, origen_lon: float,
                 max_anillo_activo: int = 1) -> None:
        self.distancia = distancia
        self.origen = (origen_lat, origen_lon)
        self.max_anillo_activo = max_anillo_activo

    def clasificar(self, lat: float, lon: float, direccion: str | None = None) -> ResultadoAnillo:
        d: ResultadoDistancia = self.distancia.medir(
            self.origen[0], self.origen[1], lat, lon, direccion_destino=direccion,
        )
        anillo = next(a for a in sorted(LIMITES_ANILLOS_MIN) if d.minutos <= LIMITES_ANILLOS_MIN[a])
        return ResultadoAnillo(
            anillo=anillo,
            distancia_minutos=round(d.minutos, 1),
            distancia_metros=round(d.metros, 0),
            proveedor=d.proveedor,
            activo=anillo <= self.max_anillo_activo,
        )
