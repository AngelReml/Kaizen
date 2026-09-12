"""Argumentario comercial por empresa.

Cada empresa declara su argumentario en `empresas/<company>/argumentario.json`:
qué argumentos funcionan (ordenados por prioridad), cuáles están prohibidos,
segmentos diana, competencia, precios de competencia (uso interno) y
distribuidores logísticos.

Patrón gemelo de `core.empresa.cargar_perfil_empresa` y de las políticas de
reintentos: archivo declarativo versionado en git como fuente única. Los
accesores aquí son lecturas puras — la mutación se hace editando el JSON.

Consumidores:
  * `BrandGuardian.revisar()` usa `patrones_argumentos_prohibidos()` para bloquear
    frases prohibidas por substring antes incluso de invocar el LLM.
  * `GeneradorBriefing` y el SDR pueden inyectar `argumentos_funcionan()` y
    `segmentos_diana()` en el contexto del agente cuando llaman al lead.
  * `precios_competencia()` SOLO se consulta para análisis interno (dashboard,
    informes); nunca debe filtrarse al transcript ni al email saliente — la
    salvaguarda está en `argumentos_prohibidos.comparacion_precio_competencia`.
"""
from __future__ import annotations

import json
from pathlib import Path


from core.rutas import dir_empresa


def cargar_argumentario(company: str, base_dir: Path | None = None) -> dict:
    """Lee `<raiz_datos>/empresas/<company>/argumentario.json`. `{}` si no existe."""
    if not company:
        return {}
    ruta = dir_empresa(company, base_dir) / "argumentario.json"
    if not ruta.exists():
        return {}
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def argumentos_funcionan(company: str, base_dir: Path | None = None) -> list[dict]:
    """Argumentos que se pueden usar, ordenados por prioridad asc (1 = primero)."""
    arg = cargar_argumentario(company, base_dir=base_dir)
    items = list(arg.get("argumentos_funcionan", []) or [])
    return sorted(items, key=lambda x: int(x.get("prioridad", 99) or 99))


def patrones_argumentos_prohibidos(company: str,
                                    base_dir: Path | None = None) -> list[dict]:
    """Patrones substring para detección dura por BrandGuardian.

    Devuelve una lista de `{id, patron, razon}` donde `patron` ya está en
    minúsculas. Solo se incluyen los argumentos prohibidos con detección por
    substring; los marcados `deteccion: "semantica_llm"` quedan para el LLM.
    """
    arg = cargar_argumentario(company, base_dir=base_dir)
    out: list[dict] = []
    for prohibido in arg.get("argumentos_prohibidos", []) or []:
        if prohibido.get("deteccion") == "semantica_llm":
            continue
        pid = prohibido.get("id", "") or ""
        razon = prohibido.get("razon", "") or ""
        for patron in prohibido.get("patrones_substring", []) or []:
            patron = (patron or "").strip().lower()
            if patron:
                out.append({"id": pid, "patron": patron, "razon": razon})
    return out


def segmentos_diana(company: str, base_dir: Path | None = None) -> list[dict]:
    """Segmentos diana, ordenados por prioridad asc."""
    arg = cargar_argumentario(company, base_dir=base_dir)
    items = list(arg.get("segmentos_diana", []) or [])
    return sorted(items, key=lambda x: int(x.get("prioridad", 99) or 99))


def competidores(company: str, base_dir: Path | None = None) -> list[dict]:
    arg = cargar_argumentario(company, base_dir=base_dir)
    return list(arg.get("competencia", []) or [])


def precios_competencia(company: str, base_dir: Path | None = None) -> dict:
    """USO INTERNO. Nunca pasar al transcript ni al email saliente."""
    arg = cargar_argumentario(company, base_dir=base_dir)
    return dict(arg.get("precios_competencia_uso_interno", {}) or {})


def distribuidores_logistica(company: str,
                              base_dir: Path | None = None) -> list[dict]:
    arg = cargar_argumentario(company, base_dir=base_dir)
    return list(arg.get("distribuidores_logistica_fase1", []) or [])
