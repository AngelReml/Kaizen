"""Interoperabilidad y resiliencia de los cubos (tesis §7).

La ingeniería que convierte la metáfora de los cubos en algo que se sostiene en producción:
apagar un cubo no rompe a los demás.

  * arranque    — sin dependencia de arranque: Cubo base, Orquestador, matriz (§7.1).
  * degradacion — clases de evento, metadatos degraded, cola persistente con TTL (§7.2).
"""
from core.resiliencia.arranque import (
    Cubo, Orquestador, CUBOS_CATALOGO, verificar_combinaciones,
)
from core.resiliencia.degradacion import (
    ClaseEvento, DegradedReason, ContratoEvento, ColaPersistente,
    marcar_degradado, es_degradado, TTL_POR_CLASE,
)

__all__ = [
    "Cubo", "Orquestador", "CUBOS_CATALOGO", "verificar_combinaciones",
    "ClaseEvento", "DegradedReason", "ContratoEvento", "ColaPersistente",
    "marcar_degradado", "es_degradado", "TTL_POR_CLASE",
]
