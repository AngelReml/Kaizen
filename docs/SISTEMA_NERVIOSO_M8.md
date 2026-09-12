# Módulo 8 — Integración runtime del sistema nervioso con la voz

Cierra el ciclo: cada llamada **lee** el sistema nervioso antes de marcar
(briefing personalizado) y **escribe** en él al colgar (compromisos detectados,
nueva interacción, transición de pipeline, próxima acción agendada).

Sin M8 los módulos M1-M7 son inertes durante la conversación. Con M8, una
llamada de validación prueba el sistema completo en ~5 minutos.

## Filosofía

- **No reescribe la infraestructura de voz**. ElevenLabs CAI, Twilio y el
  WebSocket de audio quedan exactamente igual. M8 son dos costuras:
  PRE (briefing → `dynamic_variables`) y POST (transcript → compromisos +
  reintentos + estado).
- **Retrocompatible**. Toda la API de `eleven_outbound` mantiene su firma.
  Las nuevas variables del briefing se añaden como `extra_variables` solo si
  el caller pasa `company=...`. Las claves legacy (`lead_nombre`, `categoria`,
  `prioridad`, `anillo`, `ciudad`) se preservan para no romper el system_prompt
  del agente en producción.
- **Determinista en lo controlable**. El detector de compromisos sigue siendo
  LLM (M4); todo lo demás —proyección a `LeadDoc`, mapeo a transición, motor
  de reintentos— es código deterministra inyectable en tests.
- **Falla blando, persiste duro**. Si el briefing no carga, la llamada se
  hace con las variables legacy. Si una transición es inválida, se registra
  la interacción y el compromiso de todos modos; el error queda en `motivo`.

## API

```python
from departments.comercial.sdr.voz_conversacional import eleven_outbound as eo

# ───── PRE-llamada ─────────────────────────────────────────────────────
# 1) Helper aislado:
vars: dict[str, str] = eo.dynamic_variables_briefing(lead_dict, company="laboratorio")

# 2) Integrado al disparo real (pasar `company` activa M8):
res = eo.colocar_llamada_via_cai(
    to_number_e164="+34...",
    lead=lead_dict,
    company="laboratorio",                # ← M8 activado
)

# 3) Dry-run con briefing:
out = eo.dry_run(to_number_e164="+34...", lead=lead_dict, company="laboratorio")
# → out["body"]["conversation_initiation_client_data"]["dynamic_variables"]
#   contiene claves legacy + claves del briefing (empresa_nombre, razon_llamada,
#   compromisos_pendientes, ultima_interaccion_resumen, ...).

# ───── POST-llamada ────────────────────────────────────────────────────
res = eo.procesar_transcript_post_llamada(
    lead_id="lead_xxx",
    company="laboratorio",
    transcript=[{"hablante": "agente", "ts": 1.0, "texto": "..."},
                {"hablante": "cliente", "ts": 3.0, "texto": "..."}],
    call_sid="CA...",
    conversation_id="conv_...",
    duracion_s=42.0,
    # opcionales / inyectables para tests:
    # knowledge=..., detector=..., motor=..., machine=..., resultado=...
)

assert res.ok
assert res.resultado_derivado in {"callback_pactado", "no_answer",
                                   "engaged_pide_muestra", "contacted_no_decisor",
                                   "no_interesa", "opt_out"}
assert res.estado_final in {"queued", "lost", "do_not_call", ...}
```

## Variables del briefing inyectadas

Las que ya producía `GeneradorBriefing.generar_dynamic_variables` (ver
[BRIEFING.md](BRIEFING.md)) más el perfil de empresa cargado desde
`empresas/<company>/perfil.json`:

```text
nombre_lead, nombre_contacto, negocio, categoria, ciudad,
intentos_previos, razon_llamada, compromisos_pendientes,
ultima_interaccion_resumen, ultima_interaccion_dias_atras,
decisor_conocido, empresa_nombre, empresa_producto_clave
```

Mezcladas con las legacy (que **no** se pierden) en el mismo
`dynamic_variables`.

## Mapeo de transcript → estado

`procesar_transcript_post_llamada` deriva el `resultado` cuando el caller
no lo pasa, usando `derivar_resultado_llamada`:

| Señal en el transcript | `resultado` derivado | Transición intermedia (desde `contacting`) |
|---|---|---|
| Sin turnos (transcript vacío) | `no_answer` | `no_answer` |
| Cliente dice "no me llaméis más" | `opt_out` | `contacted` (motor → `do_not_call`) |
| Detector devuelve `callback` | `callback_pactado` | `contacted` (motor → `queued` con `proxima_accion_ts`) |
| Detector devuelve `muestra` | `engaged_pide_muestra` | `engaged` (motor → `sample_requested`) |
| Cliente dice "no me interesa" | `no_interesa` | `contacted` (motor → `lost`) |
| Cualquier otro diálogo | `contacted_no_decisor` | `contacted` (motor → `queued`/`lost` según intentos) |

El motor de reintentos (M3) toma esa transición intermedia como punto de
partida, aplica la política `empresas/<company>/politica_reintentos.json` y
produce la transición final + `proxima_accion_ts`/`proxima_accion_tipo`.

## Idempotencia y seguridad

- **Compromisos**: se deduplican por `(tipo, fecha_objetivo)` antes de
  añadirse al lead. Si el motor crea otro callback en `aplicar()`, también
  pasa por la misma deduplicación.
- **Transiciones inválidas**: si el motor propone una transición no permitida
  por la máquina, se aplica el resto de la recomendación (`proxima_accion`,
  intentos, compromiso) sin disparar la transición; el `motivo` del resultado
  lo refleja.
- **Lead inexistente**: devuelve `ok=False` con `motivo="lead <c>/<id> no
  existe"`, sin levantar excepción ni dejar el knowledge en estado raro.

## Qué NO toca M8

- `cliente_eleven_cai.py`, `twilio_outbound.py`, `pre_flight.py`, las URLs ni
  los headers del POST a ElevenLabs.
- El system_prompt del agente CAI (eso vive en el dashboard ElevenLabs).
- La capa legacy `post_call.py` (orquestador antiguo basado en `EstadoLead`):
  sigue funcionando en paralelo hasta que la deuda "Convivencia de máquinas
  de estados" ([[TODO]]) se cierre.

## Tests

`tests/test_eleven_outbound_m8.py` — 12 tests deterministas con un detector
de compromisos mockeado. Cubre:

- Briefing combina lead + perfil de empresa.
- Dry-run con y sin `company` (retrocompatibilidad).
- Derivación de `resultado` para los casos canónicos.
- Camino feliz callback pactado: `contacting → contacted → queued` con
  `proxima_accion_ts == fecha_objetivo` y compromiso persistido.
- Sin transcript (no_answer): `contacting → no_answer → queued` con
  intentos+1.
- Lead inexistente devuelve error explícito.
- Compromiso duplicado no se añade dos veces.

## Próximos pasos (no incluidos en M8)

1. Endpoint HTTP que reciba el webhook real de ElevenLabs CAI y llame a
   `procesar_transcript_post_llamada`. Hoy la integración es a nivel de
   función Python; el webhook bridge es un wrapper trivial.
2. Cuando el agente ElevenLabs use realmente las variables del briefing en
   su system_prompt (`{{razon_llamada}}`, `{{ultima_interaccion_resumen}}`,
   etc.), validar con una llamada real al número de Iván y comprobar el
   ciclo completo en `python kaizen.py comercial dashboard`.

---
Relacionados: [[BRIEFING]]
