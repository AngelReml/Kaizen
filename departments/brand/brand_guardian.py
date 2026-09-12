"""Brand Guardian — promovido del Comercial al cubo Brand (tesis §6.4).

El Brand Guardian del Comercial no se copia: su capacidad se promueve a departments/brand/
y el Comercial pasa a consumirlo por contrato (publica brand.review_requested y espera
brand.review_completed). Ningún import cruza la frontera de departamentos.

Diferencia con el del Comercial: este es CONFIG-DRIVEN. No tiene palabras prohibidas
hardcodeadas; las lee de `empresas/<empresa>/brand/` (guia, palabras_prohibidas,
argumentos_prohibidos, firma). Así sirve a cualquier empresa sin tocar código.

Doble capa (igual que el original):
  1. Reglas deterministas (longitud, placeholders, palabras/argumentos prohibidos, firma).
  2. Evaluación semántica por LLM contra la guía de marca de la empresa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from departments.brand import config as brand_cfg

PLACEHOLDERS_MAYUSCULAS = re.compile(r"\b(TODO|INSERTAR|XXX|FIXME|PENDIENTE)\b")
PLACEHOLDERS_CORCHETES = re.compile(r"\[[A-Z_]{2,}\]")
MARKDOWN_PROHIBIDO = re.compile(r"(?m)^(#+\s|---+\s*$|\*\*?|^\s*[-*]\s)")


@dataclass
class BrandReview:
    aprobado: bool
    problemas: list[str] = field(default_factory=list)
    sugerencias: list[str] = field(default_factory=list)
    detalle_llm: str = ""


class BrandGuardian:
    """Revisor de marca config-driven. `semantic_evaluator` y `chat` son inyectables."""

    def __init__(self, empresa: str = "laboratorio", *, semantic_evaluator=None, chat=None) -> None:
        self.empresa = empresa
        self.guia = brand_cfg.cargar_guia(empresa)
        self.palabras_prohibidas = brand_cfg.palabras_prohibidas(empresa)
        self.argumentos_prohibidos = brand_cfg.patrones_argumentos_prohibidos(empresa)
        firma = brand_cfg.cargar_firma(empresa)
        self.remitente_nombre = firma.get("remitente_nombre", "")
        self.remitente_empresa = firma.get("remitente_empresa", "")
        self.contexto_marca = brand_cfg.contexto_marca(empresa)
        self.semantic = semantic_evaluator
        if chat is None:
            import claude_client
            chat = claude_client.chat
        self.chat = chat

    def revisar(self, asunto: str, cuerpo: str, *, lead: dict | None = None,
                usar_llm: bool = True, exigir_firma: bool = True) -> BrandReview:
        problemas: list[str] = []
        sugerencias: list[str] = []

        if not asunto.strip():
            problemas.append("Asunto vacío.")
        elif len(asunto) > 80:
            problemas.append(f"Asunto demasiado largo ({len(asunto)} caracteres, máx 80).")

        palabras = cuerpo.split()
        if len(palabras) < 50:
            problemas.append(f"Cuerpo demasiado corto ({len(palabras)} palabras, mín 50).")
        elif len(palabras) > 200:
            sugerencias.append(f"Cuerpo largo ({len(palabras)} palabras); recomendado máx 150.")

        if MARKDOWN_PROHIBIDO.search(cuerpo):
            problemas.append("Cuerpo contiene markdown; el email debe ir en texto plano.")

        full = cuerpo + " " + asunto
        m = PLACEHOLDERS_MAYUSCULAS.search(full) or PLACEHOLDERS_CORCHETES.search(full)
        if m:
            problemas.append(f"Placeholder sin rellenar: '{m.group(0)}'.")

        cuerpo_lower = cuerpo.lower()
        for p in self.palabras_prohibidas:
            if p in cuerpo_lower:
                problemas.append(f"Palabra prohibida: '{p}' (no cuadra con la marca).")
        for arg in self.argumentos_prohibidos:
            if arg["patron"] in cuerpo_lower:
                problemas.append(f"Argumento prohibido [{arg['id']}]: '{arg['patron']}'. {arg['razon']}")

        if exigir_firma:
            if self.remitente_nombre and self.remitente_nombre not in cuerpo:
                problemas.append(f"Falta el remitente '{self.remitente_nombre}' al cierre.")
            if self.remitente_empresa and self.remitente_empresa not in cuerpo:
                sugerencias.append(f"No aparece la empresa '{self.remitente_empresa}'.")

        detalle_llm = ""
        if usar_llm and not problemas and self.semantic is not None:
            try:
                v = self.semantic(asunto, cuerpo, contexto_marca=self.contexto_marca, lead=lead)
            except Exception as e:  # noqa: BLE001
                sugerencias.append(f"Evaluación LLM falló: {e}")
            else:
                detalle_llm = v.get("dictamen", "")
                if not v.get("ok", True):
                    problemas.append(f"Brand Guardian (LLM): {v.get('motivo', 'tono no encaja')}")

        return BrandReview(aprobado=not problemas, problemas=problemas,
                           sugerencias=sugerencias, detalle_llm=detalle_llm)
