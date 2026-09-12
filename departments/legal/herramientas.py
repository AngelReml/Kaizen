"""Herramientas de Legal (Fase 5.3). Deterministas; análisis por base curada de cláusulas."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_BASE = Path(__file__).parent / "clausulas_problematicas.json"


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _cargar_base() -> tuple:
    return tuple(json.loads(_BASE.read_text(encoding="utf-8")))


def consultar_clausula_problematica(texto: str) -> dict:
    """Comprueba si un texto de cláusula contiene un patrón problemático conocido."""
    t = _norm(texto)
    for entrada in _cargar_base():
        if _norm(entrada["patron"]) in t:
            return {"es_problematica": True, "motivo": entrada["motivo"],
                    "gravedad": entrada["gravedad"], "referencia": entrada.get("referencia")}
    return {"es_problematica": False, "motivo": "", "gravedad": None, "referencia": None}


def analizar_contrato(texto: str) -> dict:
    """Trocea el texto en cláusulas y evalúa cada una contra la base."""
    clausulas = [c.strip() for c in re.split(r"\n+|(?<=[.;])\s{2,}", texto or "") if c.strip()]
    riesgos, puntos = [], []
    for c in clausulas:
        r = consultar_clausula_problematica(c)
        if r["es_problematica"]:
            item = {"clausula": c[:120], "motivo": r["motivo"], "gravedad": r["gravedad"],
                    "referencia": r["referencia"]}
            (riesgos if r["gravedad"] == "alta" else puntos).append(item)
    return {"clausulas": clausulas, "riesgos": riesgos, "puntos_atencion": puntos}


def analizar_contrato_pdf(path: str) -> dict:
    """Extrae texto del documento (.txt directo; .pdf vía pypdf) y lo analiza."""
    p = str(path)
    if p.lower().endswith(".txt"):
        texto = Path(p).read_text(encoding="utf-8", errors="replace")
    else:
        try:
            from pypdf import PdfReader
            texto = "\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
        except Exception as e:
            raise RuntimeError(f"No se pudo leer el PDF ({e}). Instala pypdf o usa un .txt.")
    return analizar_contrato(texto)


def comparar_con_plantilla(contrato: str, requeridos: list[str]) -> dict:
    """Detecta qué cláusulas requeridas por la plantilla faltan en el contrato."""
    t = _norm(contrato)
    faltan = [r for r in requeridos if _norm(r) not in t]
    return {"diferencias": faltan, "coincide": not faltan}
