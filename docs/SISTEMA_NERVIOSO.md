# Sistema Nervioso de Kaizen

Documento fundacional. Lee esto antes que el resto de docs de sistema nervioso.

## El problema que estamos resolviendo

Iván recibió una llamada de 89 segundos con su voz clonada y el agente pactó callback
con "Lidia" para mañana entre las 10 y las 11. La llamada funcionó como prueba de
audio + LLM + bridge ElevenLabs/Twilio. Pero reveló que **Kaizen no es un departamento
todavía — es un script con voz**.

Sin sistema nervioso:

- El agente NO recuerda si ya habló con ese lead.
- NO sabe qué se le prometió (el callback con Lidia se evaporaría).
- NO tiene política sobre cuándo reintentar.
- NO puede ser consultado ("¿qué leads tengo programados mañana?" → silencio).
- Repite el mismo first_message genérico siempre, llamada tras llamada.
- El director humano no tiene visibilidad operativa.

El sistema nervioso es la capa que convierte la voz funcional en un departamento real.

## Las 8 piezas que lo componen

```
┌──────────────────────────────────────────────────────────────────────────┐
│  MEMORIA                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────────┐│
│  │  lead_schema (M1)   │  │  knowledge migrado (no destructivo)         ││
│  │  · campos completos │  │  · 466 leads existentes con defaults nuevos ││
│  └─────────────────────┘  └─────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│  ESTADO Y POLÍTICA                                                        │
│  ┌────────────────────────────┐  ┌──────────────────────────────────────┐│
│  │  pipeline_state_machine (M2)│  │  reintentos (M3)                     ││
│  │  · 12 estados (granular)    │  │  · política JSON editable            ││
│  │  · transiciones validadas   │  │  · callback exacto / nurturing /     ││
│  │  · acciones automáticas     │  │    DO_NOT_CALL inmediato             ││
│  └────────────────────────────┘  └──────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│  INTELIGENCIA                                                             │
│  ┌────────────────────────────┐  ┌──────────────────────────────────────┐│
│  │  compromisos detector (M4)  │  │  briefing del agente (M5)            ││
│  │  · LLM sobre transcript     │  │  · dynamic_variables por lead        ││
│  │  · extrae callbacks, muestras│ │  · first_message: 1ª vs continuación ││
│  │  · validación JSON          │  │  · resumen de interacciones previas  ││
│  └────────────────────────────┘  └──────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│  INTERFAZ HUMANA                                                          │
│  ┌────────────────────────────┐  ┌──────────────────────────────────────┐│
│  │  consulta natural (M6)      │  │  dashboard Director Comercial (M7)   ││
│  │  · "qué leads están…"       │  │  · estado del pipeline               ││
│  │  · LLM-to-query              │  │  · acciones próximas 24h             ││
│  │  · CLI: kaizen pregunta      │  │  · compromisos críticos / alertas    ││
│  └────────────────────────────┘  └──────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│  INTEGRACIÓN (M8) — entregado 2026-05-28                                 │
│  · PRE-llamada: briefing → dynamic_variables (ElevenLabs CAI)            │
│  · POST-llamada: transcript → compromisos + reintentos + estado          │
│  · 12 tests verdes con detector mockeado; ver SISTEMA_NERVIOSO_M8.md     │
└──────────────────────────────────────────────────────────────────────────┘
```

## Principios que el sistema cumple

1. **No se pierde nada.** Cada llamada deja transcript persistente, cada compromiso
   queda como evento futuro, cada transición queda en el historial. El v0.2 §3.4 lo
   exigía; ahora el sistema lo encarna.
2. **Memoria útil, no archivada.** El briefing convierte el histórico en contexto
   accionable para la próxima llamada. El agente sabe **a qué viene** cuando llama
   a Lidia mañana a las 10.
3. **Política antes que improvisación.** El motor de reintentos sigue reglas
   documentadas, configurables en JSON por empresa. Cero magic numbers en código.
4. **El director humano tiene visibilidad operativa.** Dashboard + NLQ son la
   interfaz al departamento. Iván no necesita leer JSON ni código.
5. **Modular y agnóstico al cliente.** Todo lo específico de Laboratorio vive en
   `empresas/laboratorio/`. El motor no nombra al cliente.

## Mapeo con lo existente

| Existente hoy | Sistema nervioso | Acción |
|---|---|---|
| `departments/comercial/lifecycle.EstadoLead` (9 estados) | `core/pipeline_state_machine.EstadoPipeline` (12 estados) | Coexisten. Migración no destructiva. Callers viejos siguen funcionando con el viejo. ADR-002. |
| Campos del lead (sueltos en el nodo) | `core/lead_schema.LeadDoc` (esquema explícito) | El esquema documenta; los leads existentes ganan defaults nuevos al leerse. ADR-001. |
| `agente_config_v1.SYSTEM_PROMPT` (estático) | `core/briefing.generar(lead)` (dinámico) | El SYSTEM_PROMPT sigue siendo la identidad del agente; el briefing se inyecta como `dynamic_variables`. |
| `cola_aprobacion + pre_flight + token` | (intocable) | El sandbox arquitectónico se mantiene. Nada del sistema nervioso lo bypasea. |
| `kaizen comercial fase1 …` | (intocable, ampliable) | Nuevos comandos: `kaizen pregunta`, `kaizen comercial dashboard`. |

## Lo que NO está en esta entrega (deliberado)

- **Integración runtime con el SDR voz**: por restricción operativa (voz pausada).
  Toda la maquinaria queda lista; el día que se reanude voz, el cambio en
  `eleven_outbound.py` son ~10 líneas.
- **Account Executive sintético**: el sistema nervioso lo prepara como consumidor
  futuro, no como pieza de esta entrega.
- **Dashboard web**: solo consola con `rich`. Si después hace falta web, el
  Director ya tiene los datos agregados.
- **Email inbound, WhatsApp, LinkedIn como canales**: fuera de alcance esta sesión.

## Orden de construcción

Per principio "doc antes que código":

1. M1 — `core/lead_schema.py` (con [[MODELO_DATOS_LEAD]] antes)
2. M2 — `core/pipeline_state_machine.py` (con [[MAQUINA_ESTADOS_LEAD]])
3. Migración de `state/knowledge.json` al esquema nuevo (no destructiva, tests primero)
4. M3 — `core/reintentos.py` + `empresas/laboratorio/politica_reintentos.json`
5. M4 — `core/compromisos.py` (test con el transcript real de Lidia)
6. M5 — `core/briefing.py`
7. M6 — `core/consulta_natural.py` + `kaizen pregunta`
8. M7 — `departments/comercial/dashboard_director.py` + `kaizen comercial dashboard`
9. README actualizado con el sistema nervioso

Cada módulo se commitea solo cuando: (a) tiene doc, (b) código funciona, (c) tests
verdes y (d) la suite global sigue ≥349 passed.

## Cómo lo usa Iván cuando vuelve

```bash
# Ver el estado del departamento
kaizen comercial dashboard

# Consultar en lenguaje natural
kaizen pregunta "qué compromisos tengo pendientes mañana"
kaizen pregunta "cuántos leads están interesados esta semana"
kaizen pregunta "qué hicimos ayer"

# Cuando se reanude la voz, el briefing es automático:
kaizen comercial fase1 voz preparar --lead cliente_b
  # ← inyecta briefing contextualizado; el agente sabrá que es la 2ª llamada
```

---

## Estado de entrega (sesión 2026-05-27 + M8 el 2026-05-28)

Las 8 piezas previstas están entregadas. M8 (integración runtime con voz) se
cerró el 28/5/2026 sin tocar Twilio/ElevenLabs/infraestructura: el cableado vive
en `eleven_outbound.py` y se activa pasando `company=...` (PRE) o llamando a
`procesar_transcript_post_llamada(...)` (POST).

| Módulo | Doc | Código | Tests | Commit | Estado |
|---|---|---|---|---|---|
| M1 — lead_schema | MODELO_DATOS_LEAD.md | core/lead_schema.py | 15 | ✔ | **OK** |
| M2 — state machine | MAQUINA_ESTADOS_LEAD.md | core/pipeline_state_machine.py | 18 | ✔ | **OK** |
| Migración no destructiva | (en ADR-007) | core/knowledge_migration.py | 9 | ✔ | **OK** — 466 leads migrados |
| M3 — reintentos | POLITICA_REINTENTOS.md | core/reintentos.py | 20 | ✔ | **OK** |
| M4 — compromisos detector | COMPROMISOS_DETECTOR.md | core/compromisos.py | 21 | ✔ | **OK** — validado contra Sonnet 4.6 real |
| M5 — briefing | BRIEFING.md | core/briefing.py | 24 | ✔ | **OK** |
| M6 — consulta natural | CONSULTA_NATURAL.md | core/consulta_natural.py | 25 | ✔ | **OK** — `kaizen pregunta "…"` |
| M7 — dashboard director | DASHBOARD_DIRECTOR.md | departments/comercial/dashboard_director.py | 14 | ✔ | **OK** — `kaizen comercial dashboard` |
| M8 — integración voz | SISTEMA_NERVIOSO_M8.md | departments/comercial/sdr/voz_conversacional/eleven_outbound.py | 12 | ✔ | **OK** — briefing PRE + transcript POST, sin tocar infra |

Suite global: **507 passed, 7 skipped** (los 7 skips son tests opt-in que requieren
`KAIZEN_TEST_LLM_REAL=1` para correr contra la API real de Anthropic).

M8 ya integrado — invocación canónica:

```python
from departments.comercial.sdr.voz_conversacional import eleven_outbound as eo

# PRE-llamada: M8 se activa pasando company=
eo.colocar_llamada_via_cai(to_number_e164="+34…", lead=lead_dict, company="laboratorio")

# POST-llamada: webhook de ElevenLabs CAI → sistema nervioso
eo.procesar_transcript_post_llamada(
    lead_id=lead_id, company="laboratorio",
    transcript=transcript, call_sid=call_sid, duracion_s=42.0,
)
```

---

*Fundacional. Cuando este doc no tiene sentido, el sistema no tiene sentido. Si lees
esto y no entiendes algo, eso es el bug, no tú.*

---
Relacionados: [[BRIEFING]] · [[COMPROMISOS_DETECTOR]] · [[CONSULTA_NATURAL]] · [[DASHBOARD_DIRECTOR]] · [[POLITICA_REINTENTOS]] · [[SISTEMA_NERVIOSO_M8]]
