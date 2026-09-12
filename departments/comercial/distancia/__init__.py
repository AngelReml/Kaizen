"""Proveedores de distancia logística.

Interfaz abstracta `DistanceProvider` con dos implementaciones:
- `HaversineProvider` (fallback sin red): línea recta a 60 km/h aproximada.
- `GoogleRoutesProvider` (real): tiempo de coche real, respetando rutas.

El selector `get_distance_provider()` elige Routes si GOOGLE_MAPS_API_KEY está; si no,
cae a haversine emitiendo un aviso al primer uso para que no pase desapercibido.
"""
