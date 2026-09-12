"""Detector de Compromiso Recíproco (v0.2 §3).

El núcleo del modelo comercial: detectar cuándo el cliente se moja con una
afirmación o pregunta verificable que implica intención real, frente a cortesías sin
compromiso o aplazamientos indefinidos.

NO hace matching de palabras clave (eso falla con el español rico). Usa Claude Sonnet 4.6
con los ejemplos del §3.2 (señales válidas) y §3.3 (señales que NO son compromiso) como
few-shot, y devuelve un dictamen estructurado.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import claude_client as ai


@dataclass
class DecisionCompromiso:
    es_compromiso: bool
    confianza: float                          # 0.0 - 1.0
    senales_detectadas: list[str] = field(default_factory=list)
    motivo: str = ""
    recomendacion: str = ""                   # "escalar_account_executive" | "nurturing" | "descartar"


_SISTEMA = """Eres el SDR sintético del negocio emisor. Tu trabajo es analizar una
respuesta de un cliente potencial (HORECA: hotel, cafetería, restaurante, tienda gourmet)
y decidir si expresa **Compromiso Recíproco**.

Compromiso Recíproco (v0.2 §3.2): el cliente se moja con una afirmación o pregunta
verificable que implica intención REAL. Algunos patrones (no exhaustivos):
- Comparación favorable de precio con proveedor actual ("tu precio me conviene más").
- Volumen prometido condicional ("si me gustan te compro X a la semana").
- Petición explícita de muestra ("puedo tomar una muestra").
- Urgencia con proveedor actual ("mi proveedor está fallando").
- Interés en producto específico ("esos rollicos me llaman la atención").
- Pregunta sobre logística ("cómo me llegaría el pedido").
- Mención de evento próximo ("tengo un evento dentro de un mes y necesito repostería").

NO es Compromiso Recíproco (§3.3):
- Cortesía sin compromiso ("qué bonito, suerte con eso").
- Aplazamiento indefinido ("mándame info y ya te diré").
- Preguntas sin urgencia ni volumen ("cuánto cuesta el kilo").
- Interés generalista sin enfoque ("me interesa todo lo de repostería").

Interpreta el español rico. NO exijas frases literales. Una pregunta sobre logística
con volumen implícito ES compromiso aunque no diga "quiero una muestra".

Devuelve EXACTAMENTE un JSON con este formato y nada más:
{
  "es_compromiso": true|false,
  "confianza": 0.00-1.00,
  "senales_detectadas": ["texto literal del cliente que evidencia la señal", ...],
  "motivo": "una frase corta justificando",
  "recomendacion": "escalar_account_executive" | "nurturing" | "descartar"
}
"""


class CompromisoDetector:
    """Analiza una respuesta de cliente y decide si hay Compromiso Recíproco."""

    def __init__(self, chat=None) -> None:
        self.chat = chat or ai.chat

    def evaluar(self, texto_respuesta: str, *, lead: dict | None = None,
                company: str = "laboratorio") -> DecisionCompromiso:
        if not texto_respuesta or not texto_respuesta.strip():
            return DecisionCompromiso(False, 0.0, motivo="respuesta vacía",
                                      recomendacion="descartar")
        contexto_lead = ""
        if lead:
            contexto_lead = (
                f"\n[Lead: {lead.get('nombre','?')} · {lead.get('categoria_icp','?')} · "
                f"{(lead.get('ubicacion') or {}).get('direccion','')}]"
            )
        user = f"=== RESPUESTA DEL CLIENTE ==={contexto_lead}\n{texto_respuesta.strip()}"
        respuesta = self.chat(
            [{"role": "user", "content": user}],
            system=_SISTEMA,
            model="claude-sonnet-4-6",
            max_tokens=400,
            company=company,
        ).strip()
        return self._parsear(respuesta)

    @staticmethod
    def _parsear(salida_llm: str) -> DecisionCompromiso:
        # Algunos modelos envuelven en ```json ... ``` o añaden texto antes/después.
        m = re.search(r"\{[\s\S]*\}", salida_llm)
        if not m:
            return DecisionCompromiso(False, 0.0,
                                      motivo=f"LLM devolvió respuesta no parseable: {salida_llm[:80]}",
                                      recomendacion="descartar")
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return DecisionCompromiso(False, 0.0,
                                      motivo=f"JSON inválido: {e}",
                                      recomendacion="descartar")
        return DecisionCompromiso(
            es_compromiso=bool(data.get("es_compromiso", False)),
            confianza=float(data.get("confianza", 0.0)),
            senales_detectadas=list(data.get("senales_detectadas", [])),
            motivo=str(data.get("motivo", "")),
            recomendacion=str(data.get("recomendacion", "nurturing")),
        )
