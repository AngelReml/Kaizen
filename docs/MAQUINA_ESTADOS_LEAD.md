# Módulo 2 — Máquina de estados del pipeline

Define los 12 estados que describen la vida útil de un lead, las transiciones
válidas entre ellos, los efectos automáticos que dispara cada transición, y la
trazabilidad de cada cambio.

## Por qué 12 estados y no 9

El lifecycle viejo (`departments/comercial/lifecycle.EstadoLead`) tenía 9 estados
suficientes para narrar el embudo. **No basta para operar un departamento real**:

- "EN_CONTACTO" abarca *"estamos llamando ahora mismo"*, *"no contestó"* y *"habló
  con la recepcionista"*. Imposible programar reintentos sin separar esos tres.
- "PERDIDO" abarca *"no me interesa"*, *"ya tengo proveedor"* y *"no me llaméis
  más"*. La última tiene implicaciones legales (LSSI) que no se pueden tratar
  como una baja normal.
- No había estado *"esperando aprobación humana"* — todo iba implícito.

ADR-002 documenta por qué creamos `EstadoPipeline` nuevo y mantenemos el viejo
en coexistencia.

## Los 12 estados

| Estado | Descripción | Terminal | Acción automática típica al entrar |
|---|---|---|---|
| `COLD` | Lead enriquecido, sin contacto previo. Inventario disponible. | no | — |
| `QUEUED` | Programado para contacto. Esperando aprobación humana o ventana horaria. | no | Motor de reintentos calcula `proxima_accion_ts`. |
| `CONTACTING` | Llamada en curso (estado transitorio, dura segundos). | no | — (la transición a NO_ANSWER/CONTACTED/ENGAGED cierra el estado) |
| `NO_ANSWER` | Se intentó contactar y no contestó. | no | Reintentos: programa siguiente intento en 2-4h, max 3 en 7 días. |
| `CONTACTED` | Habló con alguien que NO es el decisor (caso típico: recepcionista). | no | Si el contacto pactó callback con fecha → crear `Compromiso` + QUEUED al ts pactado. Si no → reintento estándar. |
| `ENGAGED` | Habló con el decisor y hay interés explícito. | no | Marca para revisión humana / handoff a Account Executive. |
| `SAMPLE_REQUESTED` | Pidió muestra concreta. | no | Crear compromiso de envío. Notificar a Sales Ops. |
| `SAMPLE_SENT` | Muestra despachada. | no | Programar follow-up en 5 días para feedback. |
| `TRIAL` | Ha probado el producto, en evaluación. | no | Programar follow-up de cierre en 3-7 días. |
| `CUSTOMER` | Convertido en cliente, ha pagado el primer pedido. | no | Account Manager toma posesión (Fase 2). |
| `LOST` | Descartado con razón. | reversible | Razón obligatoria. Puede resurrect a COLD en campañas de nurturing futuras. |
| `DO_NOT_CALL` | Pidió no ser contactado (LSSI/RGPD). | terminal | `lead.do_not_call=True`. Bloquea todo contacto futuro. NO reversible programáticamente. |

## Grafo de transiciones

```
                        ┌─────────────────────────────────┐
                        │            DO_NOT_CALL          │  ← desde CUALQUIER estado
                        │           (terminal duro)        │     si el cliente pide opt-out
                        └─────────────────────────────────┘
                                       ↑
                                       │
                                  desde todos
                                       │
   ┌────┐   approve   ┌──────┐  pick   ┌──────────┐
   │COLD│ ──────────► │QUEUED│ ──────► │CONTACTING│
   └────┘ ◄────────── └──────┘         └──────────┘
     ↑    re-schedule    │                  │
     │                   ↓                  │
   (resurrect            └─ (timeout)       ├─ no_answer ─► NO_ANSWER ─► (back to QUEUED on retry)
    desde LOST                              ├─ recep ──── ► CONTACTED ─► (callback) QUEUED, (no más) LOST
    en nurturing)                           └─ decisor ─► ENGAGED ──┐
                                                                      │
                       ┌──────────────────────────────────────────────┘
                       ▼
              SAMPLE_REQUESTED ──► SAMPLE_SENT ──► TRIAL ──► CUSTOMER
                       │              │             │           │
                       ▼              ▼             ▼           ▼
                     LOST           LOST          LOST       LOST (churn)
                       │
                       └─► COLD (resurrect en nurturing futuro)
```

## Transiciones válidas (matriz completa)

```python
TRANSICIONES_VALIDAS = {
    COLD:             {QUEUED, LOST, DO_NOT_CALL},
    QUEUED:           {CONTACTING, COLD, LOST, DO_NOT_CALL},
    CONTACTING:       {NO_ANSWER, CONTACTED, ENGAGED, LOST, DO_NOT_CALL},
    NO_ANSWER:        {QUEUED, LOST, DO_NOT_CALL},
    CONTACTED:        {QUEUED, ENGAGED, LOST, DO_NOT_CALL},
    ENGAGED:          {SAMPLE_REQUESTED, LOST, DO_NOT_CALL, QUEUED},  # QUEUED si pacta callback
    SAMPLE_REQUESTED: {SAMPLE_SENT, LOST, DO_NOT_CALL},
    SAMPLE_SENT:      {TRIAL, CUSTOMER, LOST, DO_NOT_CALL},  # CUSTOMER si pide pedido directo
    TRIAL:            {CUSTOMER, LOST, DO_NOT_CALL},
    CUSTOMER:         {LOST, DO_NOT_CALL},                    # LOST = churn
    LOST:             {COLD, DO_NOT_CALL},                     # resurrect a COLD
    DO_NOT_CALL:      set(),                                   # terminal duro
}
```

## Anatomía de una transición

Cada llamada a `PipelineMachine.transicionar(...)`:

1. **Valida estado actual permite el destino.** Si no, lanza `TransicionInvalida`.
2. **Registra evento en `lead.historial_pipeline`** (lista append-only). Esquema:
   ```
   { ts, desde, a, razon, detalle, evento_disparador }
   ```
3. **Actualiza `lead.estado_pipeline`** y `lead.fecha_ultima_transicion`.
4. **Dispara hooks registrados** (M3-M4 conectan reintentos y compromisos aquí).
5. **Persiste el lead actualizado** en `KnowledgeStore`.

El historial de transiciones es INMUTABLE — nunca se reescribe.

## Hooks (Protocol)

```python
class HookTransicion(Protocol):
    def on_transicion(self, lead: LeadDoc, transicion: TransicionPipeline) -> None: ...
```

Los hooks se registran globalmente:

```python
machine.registrar_hook(reintentos.on_transicion)
machine.registrar_hook(compromisos.on_transicion)
```

Cuando una transición ocurre, todos los hooks reciben el lead actualizado y la
transición. Excepciones en hooks NO bloquean la transición — se loggean en
`stderr` y siguen. (Patrón aislamiento de suscriptores, idéntico al del bus.)

## Acciones automáticas (M3+ las implementan)

Hooks típicos que vivirán en otros módulos:

- **Reintentos (M3):** al entrar a `QUEUED`, programa `proxima_accion_ts`. Al entrar
  a `NO_ANSWER`, decide cuándo reintentar según política. Al entrar a `LOST`,
  cancela cualquier acción futura.
- **Compromisos (M4):** al detectar un compromiso en el transcript post-call, crea
  el `Compromiso` y, si es callback, transiciona a `QUEUED` con `proxima_accion_ts`
  = fecha pactada.
- **DO_NOT_CALL handler:** marca `lead.do_not_call=True` y cancela todo lo pendiente.

En M2 solo se definen las **interfaces** y se prueba que los hooks se llaman; los
hooks reales se enchufan en sus módulos.

## Mapeo legacy → pipeline (referencia)

Ver `core/lead_schema.py::mapear_legacy_a_pipeline()`. Resumen:

```
identificado, cualificado, enriquecido  → COLD
en_contacto                              → CONTACTING (luego refinado por interacciones)
compromiso_reciproco                     → ENGAGED
muestra_enviada                          → SAMPLE_SENT
cliente_activo                           → CUSTOMER
en_riesgo                                → CUSTOMER (con flag riesgo_churn — TODO.md)
perdido                                  → LOST
```

## Test plan

- Cada transición permitida funciona y devuelve el lead actualizado.
- Cada transición no permitida lanza `TransicionInvalida` con mensaje claro.
- `DO_NOT_CALL` desde cualquier estado funciona.
- `DO_NOT_CALL` es terminal: ninguna transición sale de él.
- `LOST → COLD` permite resurrección.
- Historial pipeline append-only: cada transición se acumula, nunca se reescribe.
- Hooks se ejecutan en el orden registrado y reciben el lead actualizado.
- Hook que lanza excepción NO bloquea la transición.
- Test con el caso real Lidia: ENGAGED al detectar callback → QUEUED con
  proxima_accion_ts mañana 10h (esto último vendrá con el hook de M3-M4; en
  M2 solo se prueba la transición pura).

---
Relacionados: [[TODO]]
