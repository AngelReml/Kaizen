"""Registro de empresas (Fase 6 — multi-empresa).

La plataforma opera varias empresas con las MISMAS plantillas de flujo (Director +
departamentos) y datos aislados. Una empresa es solo contexto intercambiable: cambiar
de empresa no reescribe el sistema, solo cambia qué contexto y qué memoria se usan.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


from core.rutas import dir_empresa


def cargar_perfil_empresa(company: str, base_dir: Path | None = None) -> dict:
    """Lee `<raiz_datos>/empresas/<company>/perfil.json` y lo devuelve como dict.

    Si no existe perfil para la empresa, devuelve `{}` — el briefing sigue funcionando
    con cadenas vacías en `empresa_nombre` / `empresa_producto_clave`.
    """
    if not company:
        return {}
    ruta = dir_empresa(company, base_dir) / "perfil.json"
    if not ruta.exists():
        return {}
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class Empresa:
    slug: str
    nombre: str
    sector: str = ""
    contexto: str = ""     # texto base de negocio (equivalente a CONTEXTO_NEGOCIO)


class RegistroEmpresas:
    def __init__(self) -> None:
        self._empresas: dict[str, Empresa] = {}

    def alta(self, empresa: Empresa) -> None:
        self._empresas[empresa.slug] = empresa

    def get(self, slug: str) -> Empresa | None:
        return self._empresas.get(slug)

    def lista(self) -> list[Empresa]:
        return [self._empresas[s] for s in sorted(self._empresas)]
