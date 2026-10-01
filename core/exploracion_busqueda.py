"""Busqueda web para la exploracion de nichos (A3 del plan de apuestas).

Envuelve `ddgs` (DuckDuckGo), que Kaizen ya usa en `departments/prospeccion.py`. Devuelve SOLO
datos normalizados y acotados: titulo, URL http(s) y extracto. Lo que llega de la web es contenido
NO FIABLE (puede traer instrucciones disfrazadas): aqui solo se limpia y se acota; quien lo use en
un prompt debe tratarlo como dato, y la URL/fecha/extracto de una fuente las copia el CODIGO de este
resultado, nunca el modelo.
"""
from __future__ import annotations

import re
import time
import unicodedata
from datetime import date

MAX_CONSULTA = 200
MAX_TITULO = 200
MAX_URL = 500
MAX_EXTRACTO = 600


class ErrorBusqueda(RuntimeError):
    pass


def _limpio(v, maximo: int) -> str:
    if not isinstance(v, str):
        return ""
    v = unicodedata.normalize("NFC", v)
    v = "".join(" " if unicodedata.category(c) == "Cc" else c for c in v)
    return re.sub(r"\s+", " ", v).strip()[:maximo]


def normalizar(resultados, *, hoy: str | None = None, maximo: int = 8) -> list[dict]:
    """Lista de {titulo, url, extracto, fecha} sin duplicados y solo con URL http(s)."""
    hoy = hoy or date.today().isoformat()
    vistos, out = set(), []
    for r in resultados if isinstance(resultados, list) else []:
        if not isinstance(r, dict):
            continue
        url = _limpio(r.get("href") or r.get("url"), MAX_URL)
        if not re.match(r"^https?://[^\s]+$", url) or url in vistos:
            continue
        vistos.add(url)
        out.append({"titulo": _limpio(r.get("title") or r.get("titulo"), MAX_TITULO), "url": url,
                    "extracto": _limpio(r.get("body") or r.get("extracto"), MAX_EXTRACTO), "fecha": hoy})
        if len(out) >= maximo:
            break
    return out


def buscar_ddgs(consulta: str, max_resultados: int = 5, *, ddgs_factory=None, reintentos: int = 1,
                pausa=time.sleep, hoy: str | None = None) -> list[dict]:
    """Busca en la web. Reintenta una vez; si falla, ErrorBusqueda (el llamador decide seguir sin fuentes)."""
    q = _limpio(consulta, MAX_CONSULTA)
    if len(q) < 3:
        raise ErrorBusqueda("consulta vacia o demasiado corta")
    if ddgs_factory is None:
        try:
            from ddgs import DDGS as ddgs_factory           # noqa: N811
        except Exception as e:                              # noqa: BLE001
            raise ErrorBusqueda(f"ddgs no esta instalado ({type(e).__name__})") from None
    ultimo = ""
    for intento in range(reintentos + 1):
        try:
            d = ddgs_factory()
            try:
                crudo = list(d.text(q, region="es-es", max_results=max_resultados))
            except TypeError:                               # version sin `region`
                crudo = list(d.text(q, max_results=max_resultados))
            pausa(0.8)                                      # cortesia con el servicio (como prospeccion.py)
            return normalizar(crudo, hoy=hoy, maximo=max_resultados)
        except Exception as e:                              # noqa: BLE001 — red, limite de peticiones...
            ultimo = f"{type(e).__name__}"
            if intento < reintentos:
                pausa(2)
    raise ErrorBusqueda(f"la busqueda fallo ({ultimo})")
