"""Cliente API de ElevenLabs Conversational AI — wrapper mínimo para Fase 1.

Solo implementa lo que necesita el SDR del tenant hoy:
  - `listar_agentes()` — para no duplicar agentes en redeploys.
  - `crear_o_actualizar_agente(snapshot)` — provisión idempotente desde
    `agente_config_v1.py` (la fuente de verdad versionada en git).
  - `obtener_agente(agent_id)` — para verificar lo desplegado.

Todo via `requests`; sin SDK ElevenLabs (innecesario aquí, su API es REST sencillo).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import requests

API_BASE = "https://api.elevenlabs.io"
TIMEOUT = 30


@dataclass
class ResultadoDespliegue:
    agent_id: str
    creado: bool                          # True si nuevo, False si actualizado
    nombre: str
    detalle: dict[str, Any]


class ClienteCAI:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY no encontrada.")

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key, "Content-Type": "application/json"}

    # ── Lectura ────────────────────────────────────────────────────────────
    def listar_agentes(self) -> list[dict]:
        r = requests.get(f"{API_BASE}/v1/convai/agents", headers=self._headers(),
                         timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("agents", data) if isinstance(data, dict) else data

    def obtener_agente(self, agent_id: str) -> dict:
        r = requests.get(f"{API_BASE}/v1/convai/agents/{agent_id}",
                         headers=self._headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    # ── Provisión idempotente ──────────────────────────────────────────────
    def crear_o_actualizar_agente(self, snapshot: ModuleType) -> ResultadoDespliegue:
        """`snapshot` es el módulo `agente_config_vN`. Si ya existe un agente con
        el mismo `NOMBRE_AGENTE`, lo actualizamos; si no, lo creamos."""
        body = self._construir_body(snapshot)
        existente = self._buscar_por_nombre(snapshot.NOMBRE_AGENTE)

        if existente:
            agent_id = existente["agent_id"] if "agent_id" in existente else existente["id"]
            url = f"{API_BASE}/v1/convai/agents/{agent_id}"
            r = requests.patch(url, headers=self._headers(), json=body, timeout=TIMEOUT)
            if r.status_code >= 400:
                # PATCH puede no soportarse en algunos endpoints; probamos POST a /update.
                url2 = f"{API_BASE}/v1/convai/agents/{agent_id}"
                r = requests.post(url2, headers=self._headers(), json=body, timeout=TIMEOUT)
            r.raise_for_status()
            return ResultadoDespliegue(agent_id=agent_id, creado=False,
                                        nombre=snapshot.NOMBRE_AGENTE, detalle=r.json() if r.text else {})

        # No existe → crear
        r = requests.post(f"{API_BASE}/v1/convai/agents/create",
                          headers=self._headers(), json=body, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError(f"crear_agente falló {r.status_code}: {r.text[:500]}")
        data = r.json()
        agent_id = data.get("agent_id") or data.get("id")
        if not agent_id:
            raise RuntimeError(f"respuesta sin agent_id: {data}")
        return ResultadoDespliegue(agent_id=agent_id, creado=True,
                                    nombre=snapshot.NOMBRE_AGENTE, detalle=data)

    # ── Helpers ────────────────────────────────────────────────────────────
    def _buscar_por_nombre(self, nombre: str) -> dict | None:
        try:
            agentes = self.listar_agentes()
        except Exception:
            return None
        for a in agentes:
            if a.get("name") == nombre:
                return a
        return None

    @staticmethod
    def _construir_body(snapshot: ModuleType) -> dict:
        """Convierte el snapshot del módulo Python al schema de la API de CAI.

        El schema de CAI ha cambiado entre versiones; este body usa la forma de finales
        de 2024 / 2025: conversation_config con agent + tts + asr + conversation."""
        return {
            "name": snapshot.NOMBRE_AGENTE,
            "conversation_config": {
                "agent": {
                    "first_message": snapshot.FIRST_MESSAGE,
                    "language": snapshot.IDIOMA,
                    "prompt": {
                        "prompt": snapshot.SYSTEM_PROMPT,
                        "llm": snapshot.LLM["model"],
                        "temperature": snapshot.LLM["temperature"],
                        "max_tokens": snapshot.LLM["max_response_tokens"],
                        "tools": snapshot.TOOLS_V0,
                    },
                },
                "tts": {
                    "voice_id": snapshot.VOZ["voice_id"],
                    "model_id": snapshot.VOZ["tts_model"],
                    "stability": snapshot.VOZ["stability"],
                    "similarity_boost": snapshot.VOZ["similarity_boost"],
                    "style": snapshot.VOZ["style"],
                    "use_speaker_boost": snapshot.VOZ["use_speaker_boost"],
                    "optimize_streaming_latency": snapshot.VOZ["optimize_streaming_latency"],
                },
                "conversation": {
                    "max_duration_seconds": snapshot.CONVERSATION["max_duration_s"],
                    "client_events": ["audio", "interruption",
                                      "user_transcript", "agent_response"],
                },
                "turn": {
                    "turn_timeout": 7,
                    "silence_end_call_timeout": snapshot.CONVERSATION["idle_timeout_s"],
                },
            },
            "platform_settings": {
                "auth": {"enable_auth": False, "allowlist": []},
                "privacy": {
                    "record_voice": snapshot.PRIVACY["recordings_eleven"],
                    "retention_days": snapshot.PRIVACY["retention_days_eleven"],
                },
            },
        }
