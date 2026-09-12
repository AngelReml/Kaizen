"""SDR voz por MP3 pre-renderizado (lo que sí funciona).

Cada lead recibe una llamada con un mensaje **personalizado para él** sintetizado con
la voz clonada de Iván. NO es conversación bidireccional — es un mensaje hablado por
Iván que le deja al cliente, con un call-to-action concreto (devolverle la llamada
al 600 000 000).

Diferencias respecto a `voz_conversacional/`:
  - No usa el WebSocket de ElevenLabs CAI (que no acepta Twilio Media Streams).
  - Usa la API estándar de TTS de ElevenLabs (que sí funciona): texto → MP3.
  - El MP3 se sirve públicamente vía ngrok (PUBLIC_MEDIA_BASE_URL).
  - Twilio toca `<Play>` apuntando al MP3 — patrón estable y probado.

Reintegración con `voz_conversacional/` cuando la arquitectura bidireccional esté
resuelta (con ElevenLabs Outbound API o Twilio ConversationRelay).
"""
