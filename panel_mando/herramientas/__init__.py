# -*- coding: utf-8 -*-
"""Registro de herramientas de director, por cubo (Fase 4).

Cada `panel_mando/herramientas/<cubo>.py` exporta `HERRAMIENTAS: dict[str,
ToolSpec]` con SOLO las operaciones reales de ESE departamento (verificadas
contra el codigo real de `departments/<cubo>/` — no inventadas). Este modulo
las agrega en `REGISTRO[cubo] -> {nombre: ToolSpec}`.

Carga defensiva: si un fichero de cubo falta o tiene un error de import, ese
cubo simplemente no aporta herramientas (el director sigue funcionando en
modo solo-conversacion, como antes de la Fase 4) — nunca tira abajo el panel
entero por un fallo en un modulo aislado."""
from __future__ import annotations

import importlib

from panel_mando.herramientas.base import (ArgumentosInvalidos, Argumento,
                                            CLASES_HERRAMIENTA, NoExisteHerramienta,
                                            ToolSpec, herramientas_para_prompt,
                                            invocar, invocar_aprobada)

_CUBOS = ("comercial", "brand", "ops", "finanzas", "marketing",
          "inteligencia", "legal", "qa", "rrhh", "customer_success")


def _cargar() -> dict[str, dict[str, ToolSpec]]:
    out: dict[str, dict[str, ToolSpec]] = {}
    for cubo in _CUBOS:
        try:
            mod = importlib.import_module(f"panel_mando.herramientas.{cubo}")
            out[cubo] = dict(getattr(mod, "HERRAMIENTAS", {}) or {})
        except Exception:                          # noqa: BLE001 — fail-soft por cubo
            out[cubo] = {}
    return out


REGISTRO: dict[str, dict[str, ToolSpec]] = _cargar()

__all__ = ["REGISTRO", "ToolSpec", "Argumento", "CLASES_HERRAMIENTA",
           "NoExisteHerramienta", "ArgumentosInvalidos", "invocar",
           "invocar_aprobada", "herramientas_para_prompt"]
