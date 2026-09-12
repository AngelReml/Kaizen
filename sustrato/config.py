"""Configuracion del sustrato (canonico 10.1).

Parser propio de .env (sin dependencias). Claves reconocidas:
COMITE_MODEL, LIMITE_COSTE_DIARIO_EUR, KAIZEN_ENVIO_HABILITADO,
SDR_VOICE_ENABLED, CLIENTE_ID. Las demas se ignoran con un unico WARN
agregado (solo nombres; PROHIBIDO imprimir o loguear valores de claves
que contengan KEY, TOKEN, SECRET, SID o PASSWORD).
"""
from __future__ import annotations

import os
from pathlib import Path

from sustrato.consola import log

_RAIZ = Path(__file__).resolve().parent.parent

CLAVES_RECONOCIDAS = (
    "COMITE_MODEL",
    "LIMITE_COSTE_DIARIO_EUR",
    "KAIZEN_ENVIO_HABILITADO",
    "SDR_VOICE_ENABLED",
    "CLIENTE_ID",
)
LIMITE_COSTE_DEFECTO_EUR = 16.00  # canonico 9: defecto FIJADO si falta la clave

_cache: dict[str, str] | None = None
_warn_emitido = False


def _parsear_env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave:
            valores[clave] = valor
    return valores


def cargar(ruta_env: Path | None = None, forzar: bool = False) -> dict[str, str]:
    """Carga .env una sola vez. Devuelve SOLO las claves reconocidas."""
    global _cache, _warn_emitido
    if _cache is not None and not forzar and ruta_env is None:
        return _cache
    todas = _parsear_env(ruta_env or (_RAIZ / ".env"))
    reconocidas = {k: v for k, v in todas.items() if k in CLAVES_RECONOCIDAS}
    ignoradas = sorted(k for k in todas if k not in CLAVES_RECONOCIDAS)
    if ignoradas and not _warn_emitido:
        log("WARN", "config", "claves .env no reconocidas por el sustrato (ignoradas)",
            n=len(ignoradas), nombres=",".join(ignoradas))
        _warn_emitido = True
    if ruta_env is None:
        _cache = reconocidas
    return reconocidas


def obtener(clave: str, defecto: str | None = None) -> str | None:
    """Valor de una clave reconocida: entorno del proceso > .env > defecto."""
    if clave not in CLAVES_RECONOCIDAS:
        raise KeyError(f"clave no reconocida por el sustrato: {clave}")
    return os.environ.get(clave) or cargar().get(clave) or defecto


def limite_coste_diario_eur() -> float:
    bruto = obtener("LIMITE_COSTE_DIARIO_EUR")
    if bruto is None:
        log("WARN", "config", "LIMITE_COSTE_DIARIO_EUR ausente; aplicando defecto",
            defecto=f"{LIMITE_COSTE_DEFECTO_EUR:.2f}")
        return LIMITE_COSTE_DEFECTO_EUR
    try:
        return float(bruto)
    except ValueError:
        log("ERROR", "config", "LIMITE_COSTE_DIARIO_EUR no numerico; aplicando defecto",
            defecto=f"{LIMITE_COSTE_DEFECTO_EUR:.2f}")
        return LIMITE_COSTE_DEFECTO_EUR


# ---------------------------------------------------------------------------
# Validador de manifest de cubo (canonico 3.1) — Bloque 2
# ---------------------------------------------------------------------------
import json as _json
import re as _re

_RE_TOPIC_MANIFEST = _re.compile(r"^kaizen\.[a-z_]+\.[a-z_]+\.v[0-9]+$")
NIVELES_AUTONOMIA = ("CERO", "BAJA", "MEDIA", "ALTA")
ELEMENTOS_SUSTRATO = ("bus", "registro", "gates", "comite", "coste",
                      "consola", "config", "hashchain")


class ManifestInvalido(ValueError):
    pass


def validar_manifest(path) -> None:
    """Valida el manifest de un cubo. Lanza ManifestInvalido citando el campo
    exacto; devuelve None si es valido (canonico 3.1)."""
    ruta = Path(path)
    if not ruta.exists():
        raise ManifestInvalido(f"manifest inexistente: {ruta}")
    try:
        m = _json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ManifestInvalido(f"JSON invalido en {ruta}: {exc}") from exc
    if not isinstance(m, dict):
        raise ManifestInvalido("raiz: debe ser un objeto JSON")
    # R-TENANT: un manifest de PRODUCTO no declara cliente. El cubo es el mismo
    # para todos los tenants; quien lo instancia dice contra cual opera.
    for campo in ("cubo", "version", "descripcion"):
        if not isinstance(m.get(campo), str) or not m.get(campo):
            raise ManifestInvalido(f"campo '{campo}': obligatorio y de tipo cadena no vacia")
    for campo in ("produce", "consume", "acciones_irreversibles", "requiere"):
        if not isinstance(m.get(campo), list):
            raise ManifestInvalido(f"campo '{campo}': obligatorio y de tipo lista")
    for campo in ("produce", "consume"):
        for t in m[campo]:
            if not isinstance(t, str) or not _RE_TOPIC_MANIFEST.match(t):
                # 'consume' puede referirse a cubos NO instalados: eso es legal.
                # Lo ilegal es un topic mal formado.
                raise ManifestInvalido(
                    f"campo '{campo}': topic '{t}' no cumple kaizen.<cubo>.<evento_pasado>.v<n>")
    na = m.get("nivel_autonomia_defecto")
    if na not in NIVELES_AUTONOMIA:
        raise ManifestInvalido(
            f"campo 'nivel_autonomia_defecto': '{na}' no esta en {NIVELES_AUTONOMIA}")
    for r in m["requiere"]:
        if r not in ELEMENTOS_SUSTRATO:
            raise ManifestInvalido(
                f"campo 'requiere': '{r}' no es un elemento del sustrato; un cubo que "
                f"requiere otro cubo es un error de diseno (canonico 3.1)")
