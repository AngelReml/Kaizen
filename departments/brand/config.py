"""Carga declarativa de la configuración de marca por empresa (tesis §6.4).

La configuración del Brand se reorganiza bajo `empresas/<empresa>/brand/` con archivos JSON
versionados en git: guia.json, palabras_prohibidas.json, argumentos_prohibidos.json,
firma.json y assets_manifest.json. Mismo patrón declarativo que el argumentario
por tenant (gemelo de `core.argumentario`).

Lecturas puras: la mutación se hace editando el JSON. Cualquier archivo ausente degrada a
un valor vacío sensato, no a excepción.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.rutas import dir_empresa


def _leer(company: str, archivo: str, base_dir: Path | None = None) -> dict:
    if not company:
        return {}
    ruta = dir_empresa(company, base_dir) / "brand" / archivo
    if not ruta.exists():
        return {}
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def cargar_guia(company: str, base_dir: Path | None = None) -> dict:
    return _leer(company, "guia.json", base_dir)


def palabras_prohibidas(company: str, base_dir: Path | None = None) -> list[str]:
    data = _leer(company, "palabras_prohibidas.json", base_dir)
    return [str(p).strip().lower() for p in data.get("palabras", []) if str(p).strip()]


def patrones_argumentos_prohibidos(company: str, base_dir: Path | None = None) -> list[dict]:
    """`{id, patron, razon}` por substring; los `deteccion=semantica_llm` se omiten aquí."""
    data = _leer(company, "argumentos_prohibidos.json", base_dir)
    out: list[dict] = []
    for p in data.get("argumentos_prohibidos", []) or []:
        if p.get("deteccion") == "semantica_llm":
            continue
        pid, razon = p.get("id", ""), p.get("razon", "")
        for patron in p.get("patrones_substring", []) or []:
            patron = (patron or "").strip().lower()
            if patron:
                out.append({"id": pid, "patron": patron, "razon": razon})
    return out


def cargar_firma(company: str, base_dir: Path | None = None) -> dict:
    return _leer(company, "firma.json", base_dir)


def cargar_assets(company: str, base_dir: Path | None = None) -> dict:
    return _leer(company, "assets_manifest.json", base_dir)


def contexto_marca(company: str, base_dir: Path | None = None) -> str:
    """Texto compacto de la guía de marca para inyectar a un LLM o al comité."""
    g = cargar_guia(company, base_dir)
    if not g:
        return ""
    partes = [f"Posicionamiento: {g.get('posicionamiento','')}"]
    if g.get("valores"):
        partes.append("Valores: " + " · ".join(g["valores"]))
    tono = g.get("tono", {})
    if tono:
        partes.append(f"Tono: {tono.get('descripcion','')}")
    if g.get("que_no_decir"):
        partes.append("Nunca: " + " · ".join(g["que_no_decir"]))
    return "\n".join(partes)
