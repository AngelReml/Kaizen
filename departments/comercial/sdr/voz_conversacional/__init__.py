"""SDR Conversacional Bidireccional — voz clonada de Iván + ElevenLabs CAI + Twilio.

Esta carpeta implementa Fase 1 voz del v0.2 §4.4. Topología B1a del
`docs/PLAN_VOZ_CONVERSACIONAL.md`:

  - Nosotros colocamos la llamada en Twilio (controlamos Record=true).
  - El `<Connect><Stream>` apunta al WebSocket de ElevenLabs CAI.
  - ElevenLabs maneja STT + Claude Sonnet 4.6 + TTS voz Iván.
  - Webhooks al cierre nos dan recording + transcript para análisis post-call.

Fuentes de verdad versionadas en este paquete (audit trail):
  - `agente_config_v1.py`: snapshot del agente desplegado en ElevenLabs.
  - `aviso_legal_v1.txt`: texto del `<Say>` Twilio (cumple R5 — informar grabación).

Cuando el dashboard de ElevenLabs cambie, se hace commit a una nueva versión
(`agente_config_v2.py`) para no perder qué se desplegó en cada momento.
"""
