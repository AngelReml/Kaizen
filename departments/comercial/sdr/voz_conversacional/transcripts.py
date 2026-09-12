"""Persistencia de llamadas y transcripts en JsonKnowledge.

Esquema (en `state/knowledge.json` bajo la empresa):

    llamada/
      <call_sid>:
        id: <call_sid>
        lead_id, pendiente_id, agente_config_version
        estado: iniciada | en_curso | completada | fallida | no_conforme
        inicio_ts, fin_ts, duracion_s
        twilio_status: initiated/ringing/answered/completed/...
        recording_path: ruta MP3 local (cuando se haya descargado)
        recording_url_twilio: URL en Twilio
        transcript: [{hablante, ts, texto}, ...]
        transcript_ts: cuándo llegó
        eventos_completados: ["status_completed", "recording", "transcript"]
        no_conforme_motivos: [...] si la llamada se considera no conforme
        analisis_id: ref a analisis_llamada/<id>
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from core.knowledge import KnowledgeStore

TIPO_LLAMADA = "llamada"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def crear_llamada(knowledge: KnowledgeStore, company: str, *,
                  call_sid: str, lead_id: str, pendiente_id: str,
                  agente_config_version: str, aviso_legal_version: str = "v1",
                  telefono_destino: str = "") -> dict:
    """Crea el registro de llamada cuando colocamos el POST a Twilio."""
    nodo = {
        "id": call_sid,
        "lead_id": lead_id,
        "pendiente_id": pendiente_id,
        "agente_config_version": agente_config_version,
        "aviso_legal_version": aviso_legal_version,
        "telefono_destino": telefono_destino,
        "estado": "iniciada",
        "inicio_ts": _ts(),
        "eventos_completados": [],
        "no_conforme_motivos": [],
    }
    knowledge.add(company, TIPO_LLAMADA, call_sid, nodo)
    return nodo


def get_llamada(knowledge: KnowledgeStore, company: str, call_sid: str) -> dict | None:
    return knowledge.get(company, TIPO_LLAMADA, call_sid)


def actualizar_llamada(knowledge: KnowledgeStore, company: str, call_sid: str,
                       **parches) -> dict:
    """Aplica parches al nodo. Si no existe, lanza KeyError."""
    nodo = knowledge.get(company, TIPO_LLAMADA, call_sid)
    if nodo is None:
        raise KeyError(f"Llamada '{call_sid}' no existe en {company}")
    nodo.update(parches)
    nodo["actualizado_en"] = _ts()
    knowledge.add(company, TIPO_LLAMADA, call_sid, nodo)
    return nodo


def marcar_evento_completado(knowledge: KnowledgeStore, company: str, call_sid: str,
                              evento: str) -> dict:
    """Marca uno de los 3 eventos asíncronos (status_completed, recording, transcript)
    como recibido. El orquestador `post_call` decide cuándo todos están listos."""
    nodo = knowledge.get(company, TIPO_LLAMADA, call_sid)
    if nodo is None:
        # La llamada puede no existir si el webhook llegó antes de que persistiéramos
        # (race con el initiated callback). Creamos un shell mínimo.
        nodo = {
            "id": call_sid, "lead_id": "?", "pendiente_id": "?",
            "estado": "huerfana", "inicio_ts": _ts(),
            "eventos_completados": [],
            "no_conforme_motivos": ["webhook_antes_de_initiated"],
        }
    completados = set(nodo.get("eventos_completados") or [])
    completados.add(evento)
    nodo["eventos_completados"] = sorted(completados)
    nodo["actualizado_en"] = _ts()
    knowledge.add(company, TIPO_LLAMADA, call_sid, nodo)
    return nodo


def persistir_transcript(knowledge: KnowledgeStore, company: str, call_sid: str,
                          transcript: list[dict]) -> dict:
    """Guarda el transcript completo en el nodo y marca el evento."""
    nodo = knowledge.get(company, TIPO_LLAMADA, call_sid)
    if nodo is None:
        raise KeyError(f"Llamada '{call_sid}' no existe en {company}")
    nodo["transcript"] = transcript
    nodo["transcript_ts"] = _ts()
    knowledge.add(company, TIPO_LLAMADA, call_sid, nodo)
    return marcar_evento_completado(knowledge, company, call_sid, "transcript")


def marcar_no_conforme(knowledge: KnowledgeStore, company: str, call_sid: str,
                       motivo: str) -> dict:
    """R1-R5: si alguna verificación post-call falla (ej. recording faltante), la
    llamada queda marcada NO CONFORME y el lead no transiciona."""
    nodo = knowledge.get(company, TIPO_LLAMADA, call_sid)
    if nodo is None:
        raise KeyError(f"Llamada '{call_sid}' no existe en {company}")
    motivos = list(nodo.get("no_conforme_motivos") or [])
    motivos.append(motivo)
    nodo["no_conforme_motivos"] = motivos
    nodo["estado"] = "no_conforme"
    nodo["actualizado_en"] = _ts()
    knowledge.add(company, TIPO_LLAMADA, call_sid, nodo)
    return nodo


def todas_las_llamadas(knowledge: KnowledgeStore, company: str,
                        estados: Iterable[str] | None = None) -> list[dict]:
    items = list(knowledge.all(company, TIPO_LLAMADA).values())
    if estados is not None:
        estados = set(estados)
        items = [x for x in items if x.get("estado") in estados]
    return sorted(items, key=lambda x: x.get("inicio_ts", ""), reverse=True)
