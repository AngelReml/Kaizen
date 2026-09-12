"""Análisis de calidad post-call (R3 del operador).

Cuatro criterios sobre el transcript completo:
  1. Compromiso Recíproco (reusa CompromisoDetector existente).
  2. Tono de marca del tenant (vía BrandGuardian.analizar_tono_conversacional).
  3. Objeciones planteadas y si fueron abordadas.
  4. Sugerencias de mejora para la próxima llamada.

Más una puntuación heurística (0-10) calculada a partir de lo anterior, NO con LLM.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from typing import Any

import claude_client as ai
from departments.comercial.brand_guardian import BrandGuardian
from departments.comercial.sdr.compromiso import CompromisoDetector, DecisionCompromiso


@dataclass
class DictamenTono:
    ok: bool
    problemas: list[str] = field(default_factory=list)
    sugerencias: list[str] = field(default_factory=list)
    dictamen_llm: str = ""


@dataclass
class DictamenObjecion:
    frase_cliente: str
    abordada: bool
    motivo: str = ""
    sugerencia: str = ""


@dataclass
class DictamenCalidad:
    call_sid: str
    lead_id: str
    agente_config_version: str
    compromiso: DecisionCompromiso
    tono: DictamenTono
    objeciones: list[DictamenObjecion]
    mejoras: list[str]
    puntuacion_global: int                # 0-10
    duracion_s: float
    turnos_agente: int
    turnos_cliente: int

    def to_dict(self) -> dict:
        return {
            "call_sid": self.call_sid,
            "lead_id": self.lead_id,
            "agente_config_version": self.agente_config_version,
            "compromiso": asdict(self.compromiso),
            "tono": asdict(self.tono),
            "objeciones": [asdict(o) for o in self.objeciones],
            "mejoras": list(self.mejoras),
            "puntuacion_global": self.puntuacion_global,
            "duracion_s": self.duracion_s,
            "turnos_agente": self.turnos_agente,
            "turnos_cliente": self.turnos_cliente,
        }


_SISTEMA_OBJECIONES = """Eres un analista de llamadas comerciales B2B. Te paso el transcript
completo de una llamada del agente del negocio emisor a un negocio HORECA.

Identifica TODAS las objeciones que planteó el cliente (lo que dijo el lado 'cliente' en
contra, en duda o como freno). Para cada una determina si el agente la abordó y propón
cómo mejorarla.

Devuelve EXACTAMENTE JSON con este formato y nada más:
{
  "objeciones": [
    {"frase_cliente": "texto literal del cliente",
     "abordada": true|false,
     "motivo": "una frase corta justificando",
     "sugerencia": "qué decir la próxima vez"},
    ...
  ],
  "mejoras_generales": ["1-3 sugerencias concretas para la próxima llamada"]
}

Si el cliente no planteó objeciones, devuelve "objeciones": []."""


def _texto_por_hablante(transcript: list[dict], hablante: str) -> str:
    return "\n".join(t.get("texto", "") for t in transcript
                     if t.get("hablante") == hablante and t.get("texto"))


def _silencios_largos_s(transcript: list[dict], umbral_s: float = 3.0) -> float:
    """Suma de pausas > umbral entre turnos consecutivos."""
    total = 0.0
    for a, b in zip(transcript, transcript[1:]):
        try:
            gap = float(b.get("ts", 0)) - float(a.get("ts", 0))
        except Exception:
            continue
        if gap > umbral_s:
            total += gap - umbral_s
    return total


def _puntuacion(*, compromiso: DecisionCompromiso, tono: DictamenTono,
                objeciones: list[DictamenObjecion], turnos_agente: int,
                turnos_cliente: int, silencios_s: float) -> int:
    """Heurística simple. Suma sobre 10."""
    p = 0
    if compromiso.es_compromiso and compromiso.confianza >= 0.6:
        p += 4
    if tono.ok:
        p += 2
    objeciones_no_abordadas = sum(1 for o in objeciones if not o.abordada)
    if objeciones_no_abordadas == 0:
        p += 2
    # "Sin monopolizar" = agente no habla más de 1 turno por encima del cliente
    # (margen para el turno de apertura). 5 vs 2 = monopolizó; 3 vs 2 = OK.
    if turnos_cliente and turnos_agente <= turnos_cliente + 1:
        p += 1
    if silencios_s < 10:
        p += 1
    return min(10, p)


class AnalisisCalidadLlamada:
    """Pipeline post-call. Devuelve `DictamenCalidad` con los 4 criterios + puntuación."""

    def __init__(self, *, chat=None, brand_guardian: BrandGuardian | None = None,
                 compromiso: CompromisoDetector | None = None) -> None:
        self.chat = chat or ai.chat
        self.brand_guardian = brand_guardian or BrandGuardian(chat=self.chat)
        self.compromiso = compromiso or CompromisoDetector(chat=self.chat)

    def analizar(self, *, transcript: list[dict], call_sid: str,
                 lead: dict | None, duracion_s: float,
                 agente_config_version: str = "v1",
                 company: str = "laboratorio") -> DictamenCalidad:
        lead_id = (lead or {}).get("id", "?")
        texto_cliente = _texto_por_hablante(transcript, "cliente")
        texto_agente  = _texto_por_hablante(transcript, "agente")

        # 1) Compromiso
        compromiso = self.compromiso.evaluar(texto_cliente, lead=lead, company=company)

        # 2) Tono
        tono = self.brand_guardian.analizar_tono_conversacional(texto_agente, lead=lead)

        # 3) Objeciones + 4) Mejoras (mismo LLM call, dos campos)
        objeciones, mejoras = self._detectar_objeciones_y_mejoras(transcript, company=company)

        # Puntuación
        turnos_agente = sum(1 for t in transcript if t.get("hablante") == "agente")
        turnos_cliente = sum(1 for t in transcript if t.get("hablante") == "cliente")
        silencios = _silencios_largos_s(transcript)
        puntuacion = _puntuacion(
            compromiso=compromiso, tono=tono, objeciones=objeciones,
            turnos_agente=turnos_agente, turnos_cliente=turnos_cliente,
            silencios_s=silencios,
        )

        return DictamenCalidad(
            call_sid=call_sid, lead_id=lead_id,
            agente_config_version=agente_config_version,
            compromiso=compromiso, tono=tono, objeciones=objeciones, mejoras=mejoras,
            puntuacion_global=puntuacion, duracion_s=duracion_s,
            turnos_agente=turnos_agente, turnos_cliente=turnos_cliente,
        )

    # ── Internals ──────────────────────────────────────────────────────────
    def _detectar_objeciones_y_mejoras(self, transcript: list[dict],
                                       company: str) -> tuple[list[DictamenObjecion], list[str]]:
        if not transcript:
            return [], []
        # Formateamos transcript como diálogo legible para el LLM.
        lineas = []
        for t in transcript:
            who = "CLIENTE" if t.get("hablante") == "cliente" else "AGENTE"
            lineas.append(f"{who}: {t.get('texto','')}")
        dialogue = "\n".join(lineas)

        try:
            respuesta = self.chat(
                [{"role": "user", "content": f"=== TRANSCRIPT ===\n{dialogue}"}],
                system=_SISTEMA_OBJECIONES,
                model="claude-sonnet-4-6",
                max_tokens=800,
                company=company,
            )
        except Exception as e:
            return [DictamenObjecion(frase_cliente=f"LLM falló: {e}",
                                      abordada=False, motivo="error")], []

        m = re.search(r"\{[\s\S]*\}", respuesta or "")
        if not m:
            return [], []
        try:
            data = json.loads(m.group(0))
        except Exception:
            return [], []
        objs = [DictamenObjecion(
            frase_cliente=o.get("frase_cliente", ""),
            abordada=bool(o.get("abordada", False)),
            motivo=o.get("motivo", ""),
            sugerencia=o.get("sugerencia", ""),
        ) for o in data.get("objeciones", [])]
        mejoras = list(data.get("mejoras_generales", []))
        return objs, mejoras
