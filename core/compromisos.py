"""Detector de compromisos (Módulo 4 del sistema nervioso).

Extrae compromisos accionables (callback, muestra, email_info, referido, visita)
de un transcript de llamada. Usa Claude Sonnet 4.6 con structured output.
Ver `docs/COMPROMISOS_DETECTOR.md` y ADR-004.

NO se confunde con `departments/comercial/sdr/compromiso.py::CompromisoDetector`
(ese clasifica binariamente si una respuesta contiene señal de Compromiso
Recíproco; este extrae eventos concretos del transcript).
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import claude_client as ai
from core.lead_schema import Compromiso


TZ_ES = ZoneInfo("Europe/Madrid")
TIPOS_VALIDOS = frozenset({"callback", "muestra", "email_info", "referido", "visita"})


_SYSTEM = """Eres un asistente analizando el transcript de una llamada comercial entre
un agente sintético del negocio emisor y un cliente HORECA. Extrae TODOS los
compromisos accionables que se hayan pactado en la conversación.

Un COMPROMISO es algo concreto con fecha/referencia que el sistema deba ejecutar:
- callback: el cliente pidió que se le llame en una fecha/hora concretas.
- muestra: el cliente pidió o aceptó recibir una muestra del producto.
- email_info: el cliente pidió información por email.
- referido: el cliente delegó a otra persona (decisor distinto), con datos.
- visita: el cliente pidió una visita comercial presencial en fecha concreta.

NO es compromiso: saludos, cortesías, promesas vagas sin fecha, información del
negocio del cliente, frases hipotéticas tipo "ya veré".

Para fechas relativas ("mañana", "la semana que viene") usa la FECHA_REFERENCIA
que te paso para convertir a fecha absoluta.

**REGLAS DE HORA — CRÍTICAS**:
- El cliente vive en España (zona horaria Europe/Madrid).
- Si el cliente dice "a las 10 de la mañana" se refiere a 10:00 hora Madrid.
- Devuelve la fecha con el OFFSET de Madrid explícito al final:
  * "+02:00" durante horario de verano (último domingo de marzo a último de octubre).
  * "+01:00" durante horario de invierno (resto del año).
- Ejemplo en mayo (verano): "mañana a las 10" → "2026-05-28T10:00:00+02:00"
- Ejemplo en diciembre (invierno): "mañana a las 10" → "2026-12-15T10:00:00+01:00"
- NO conviertas a UTC tú; usa la hora local y el offset. El sistema normaliza después.

Para tolerancia:
- "a las 10" o "sobre las 10" → tolerancia_min=15 (default).
- "entre las 10 y las 11" → fecha_objetivo=10:00 + tolerancia_min=60.
- "por la mañana" sin hora → fecha_objetivo=11:00 + tolerancia_min=120.
- "por la tarde" sin hora → fecha_objetivo=17:00 + tolerancia_min=120.

DEVUELVE EXACTAMENTE este JSON (sin markdown, sin texto extra alrededor):

{
  "compromisos": [
    {
      "tipo": "callback",
      "fecha_objetivo": "2026-05-28T10:00:00+02:00",
      "tolerancia_min": 60,
      "contexto": "descripción breve de qué se pactó",
      "literal_cliente": "frase literal del cliente que lo pactó",
      "literal_agente": "frase literal del agente que lo confirmó"
    }
  ]
}

Si no hay compromisos en el transcript, devuelve: {"compromisos": []}.
"""


def _formatear_transcript(transcript: list[dict]) -> str:
    """Convierte la lista de turnos al formato dialogue compacto."""
    lineas = []
    for t in transcript or []:
        who = "AGENTE" if (t.get("hablante") or t.get("role", "")).lower() in (
            "agente", "agent", "assistant") else "CLIENTE"
        ts = t.get("ts", 0)
        texto = (t.get("texto") or t.get("message") or "").strip()
        lineas.append(f"[{ts:5.1f}s] {who}: {texto}")
    return "\n".join(lineas)


class DetectorCompromisos:
    """Pipeline LLM-Sonnet sobre transcript completo. `chat` inyectable para tests."""

    def __init__(self, chat=None, fecha_referencia_utc: Optional[datetime] = None,
                 company: str = "laboratorio") -> None:
        self.chat = chat or ai.chat
        self.fecha_referencia_utc = fecha_referencia_utc
        self.company = company

    def detectar(self, transcript: list[dict]) -> list[Compromiso]:
        if not transcript:
            return []
        fecha_ref = self.fecha_referencia_utc or datetime.now(timezone.utc)
        # Pasamos la fecha en formato legible local (Madrid) Y UTC para evitar dudas.
        fecha_ref_es = fecha_ref.astimezone(TZ_ES)
        diag = _formatear_transcript(transcript)
        user = (
            f"FECHA_REFERENCIA (UTC): {fecha_ref.isoformat()}\n"
            f"FECHA_REFERENCIA (Madrid): {fecha_ref_es.isoformat()}\n"
            f"DIA_SEMANA_HOY (Madrid): {fecha_ref_es.strftime('%A')}\n\n"
            f"=== TRANSCRIPT ===\n{diag}\n"
        )
        try:
            respuesta = self.chat(
                [{"role": "user", "content": user}],
                system=_SYSTEM,
                model=os.environ.get("KAIZEN_MODEL_COMPROMISOS", "claude-sonnet-4-6"),
                max_tokens=1200,
                company=self.company,
            )
        except Exception as e:
            print(f"[compromisos] LLM falló: {e}", file=sys.stderr)
            return []
        return self._parsear(respuesta or "")

    @staticmethod
    def _parsear(salida_llm: str) -> list[Compromiso]:
        if not salida_llm.strip():
            return []
        m = re.search(r"\{[\s\S]*\}", salida_llm)
        if not m:
            print(f"[compromisos] LLM no devolvió JSON: {salida_llm[:120]}",
                  file=sys.stderr)
            return []
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            print(f"[compromisos] JSON inválido: {e}", file=sys.stderr)
            return []
        out: list[Compromiso] = []
        for raw in data.get("compromisos") or []:
            tipo = (raw.get("tipo") or "").lower()
            if tipo not in TIPOS_VALIDOS:
                print(f"[compromisos] tipo inválido '{tipo}', omitido", file=sys.stderr)
                continue
            fecha = raw.get("fecha_objetivo") or ""
            if fecha:
                try:
                    parsed = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                except ValueError:
                    print(f"[compromisos] fecha_objetivo inválida '{fecha}', omitido",
                          file=sys.stderr)
                    continue
                # Normalizar a UTC. Si el LLM devolvió naive, asumimos hora Madrid.
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=TZ_ES)
                fecha = parsed.astimezone(timezone.utc).isoformat()
            comp = Compromiso(
                id=f"comp_{uuid.uuid4().hex[:10]}",
                tipo=tipo,
                fecha_objetivo=fecha,
                tolerancia_min=int(raw.get("tolerancia_min", 15) or 15),
                contexto=raw.get("contexto", "") or raw.get("literal_cliente", "") or "",
                cumplido=False,
            )
            out.append(comp)
        return out
