"""Raíz de los datos de tenant — punto único de verdad (R-TENANT).

> El árbol del producto sabe QUÉ ES un tenant, jamás QUÉ tenant.

Corolario de infraestructura: los datos de cliente viven **fuera del árbol de
git** y su ubicación entra por configuración, nunca por ruta relativa al código.
Hasta ahora cada módulo reconstruía la ruta con `Path(__file__).parent.parent`,
lo que ataba físicamente el producto a los datos de sus clientes: no había forma
de sacar los datos sin romper el código, ni de testear con otra raíz.

Precedencia:

  1. La variable de entorno ``KAIZEN_DATOS``, si está definida y no vacía.
  2. ``<hermano-del-repo>/KAIZEN_DATOS`` — fuera del árbol de git por defecto.

**No hay caída silenciosa al árbol del repo.** Un producto que encuentra datos
de cliente dentro de su propio código es exactamente la brecha que R-TENANT
cierra; si el defecto cayese al repo, la migración parecería terminada sin
estarlo. Durante la migración R-TENANT (fases F2–F4, con los datos todavía en
`empresas/`) se apunta ``KAIZEN_DATOS`` al propio repo; en F5 los datos se
mudan a la ruta por defecto y la variable deja de hacer falta.

La resolución es **en cada llamada**, nunca en constante de módulo: una ruta
congelada en el import es intesteable y fue el peor de los puntos de acople
(`core/tenants.py:RUTA_REGISTRO`).
"""
from __future__ import annotations

import os
from pathlib import Path

_RAIZ_REPO = Path(__file__).resolve().parent.parent

#: Variable de entorno que declara dónde viven los datos de tenant.
VAR_ENTORNO = "KAIZEN_DATOS"

#: Nombre del directorio hermano del repo usado cuando no hay variable.
NOMBRE_POR_DEFECTO = "KAIZEN_DATOS"

#: Tenants SINTÉTICOS: ficción versionada junto al producto (negocios inventados,
#: correos `.invalid`, ningún tercero detrás). Son *fixture*, no dato de cliente,
#: así que —y solo ellos— pueden vivir dentro del árbol de git. Es la misma
#: allowlist que aplica `herramientas/centinela_datos.py`; si cambia una, cambia
#: la otra. Única excepción a "los datos viven fuera", nominal y auditable: no es
#: un fallback genérico al repo, que sería justo la brecha que R-TENANT cierra.
TENANTS_SINTETICOS = ("laboratorio",)


def raiz_datos() -> Path:
    """Raíz de los datos de tenant. FUERA del árbol de git por defecto."""
    valor = os.environ.get(VAR_ENTORNO, "").strip()
    if valor:
        return Path(valor).expanduser()
    return _RAIZ_REPO.parent / NOMBRE_POR_DEFECTO


def raiz_repo() -> Path:
    """Raíz del árbol del producto (código). Nunca contiene datos de cliente."""
    return _RAIZ_REPO


# ── Directorios de datos ─────────────────────────────────────────────────────

def dir_empresas() -> Path:
    return raiz_datos() / "empresas"


def dir_empresa(company: str, base_dir: Path | None = None) -> Path:
    """Directorio de un tenant concreto. `company` entra SIEMPRE por parámetro.

    Un tenant sintético que no esté en la raíz de datos se busca en el árbol:
    se distribuye con el producto (ver `TENANTS_SINTETICOS`). Cualquier otro
    tenant se resuelve solo contra la raíz de datos, exista o no.
    """
    if base_dir is not None:
        return Path(base_dir) / "empresas" / company
    directo = dir_empresas() / company
    if directo.exists() or company not in TENANTS_SINTETICOS:
        return directo
    return _RAIZ_REPO / "empresas" / company


def ruta_registro_tenants() -> Path:
    """Registro de tenants. El real vive fuera; el sintético se versiona aparte."""
    directo = dir_empresas() / "tenants.json"
    if directo.exists():
        return directo
    sintetico = _RAIZ_REPO / "empresas" / "tenants.laboratorio.json"
    return sintetico if sintetico.exists() else directo


def dir_diario() -> Path:
    return raiz_datos() / "diario"


def dir_diario_empresa(company: str) -> Path:
    """Diario de un tenant. Misma excepción nominal que `dir_empresa`: el diario
    del tenant sintético es fixture y viaja con el producto."""
    directo = dir_diario() / company
    if directo.exists() or company not in TENANTS_SINTETICOS:
        return directo
    return _RAIZ_REPO / "diario" / company


def dir_state() -> Path:
    return raiz_datos() / "state"


def dir_data() -> Path:
    return raiz_datos() / "data"


def dir_bitacora() -> Path:
    return raiz_datos() / "bitacora"
