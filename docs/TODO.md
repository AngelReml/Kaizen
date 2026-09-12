# TODO — Deuda técnica registrada durante el sistema nervioso

Cosas vistas que NO se arreglan en esta sesión (Principio 7: sin parches).
Iván decide qué se prioriza la próxima sesión.

---

## Convivencia de dos máquinas de estados

`departments/comercial/lifecycle.EstadoLead` (9 estados, legacy) y
`core/pipeline_state_machine.EstadoPipeline` (12 estados, sistema nervioso) coexisten
durante un periodo. ADR-002 lo justifica.

**Deuda:** consolidar callers — migrar todos los módulos que usan `EstadoLead` a
`EstadoPipeline`. Estimación: 1 día.

**Archivos afectados:**

- `departments/comercial/researcher.py`
- `departments/comercial/enrichment.py`
- `departments/comercial/account_executive.py`
- `departments/comercial/sdr/multicanal.py`
- `departments/comercial/sdr/voz_conversacional/post_call.py`
- Tests asociados.

**Cuándo:** después de validar el sistema nervioso en piloto.

---

## Integración runtime del SDR voz con sistema nervioso

`eleven_outbound.colocar_llamada_via_cai` debería leer el briefing y inyectarlo
como `dynamic_variables`. La pieza está construida (`core/briefing.py`); la
modificación al outbound NO se hace en esta sesión por la restricción operativa
"NO toques nada de la voz".

**Cuándo:** primera sesión de la próxima semana, cuando se reanude la voz.

---

## `EN_RIESGO` del lifecycle viejo no tiene mapeo claro en el nuevo

El estado viejo `EN_RIESGO` (caída de frecuencia / churn pendiente) no tiene
equivalente directo en los 12 estados nuevos. El más cercano sería `CUSTOMER`
con un flag aparte, o un nuevo estado `AT_RISK` que el prompt no incluyó.

**Decisión temporal:** mapeo `EN_RIESGO → CUSTOMER` con metadato
`riesgo_churn=True`. Se revisa cuando aparezca el primer cliente en riesgo real
(probablemente cuando llegue Account Executive).

---

## El backup automático del knowledge crece sin freno

`core.knowledge_migration` hace backup antes de cada ejecución. Si se ejecuta
varias veces, se acumulan `.bak.<ts>` en `state/`. Cero rotación.

**Deuda:** rotación de backups (max 5 más recientes). 1 hora de trabajo.

---

## La consulta natural devuelve "unsupported" en preguntas con dimensiones temporales relativas complejas

Preguntas tipo "¿qué pasó hace dos viernes?" o "¿cuántos compromisos vencen
entre el martes y el jueves de la semana que viene?" no están resueltas en el
filtro inicial.

**Deuda:** ampliar el schema del filtro con `fecha_relativa`. 2 horas de trabajo.

---

## El schema de Lead carece de campo `nombre_contacto`

`Contacto` tiene teléfono, email, web, instagram pero **no el nombre de la
persona** con la que se habló (ej. "Lidia"). El briefing M5 lo busca como
solución intermedia en `lead.metadatos_extra.nombre_contacto`.

**Deuda:** añadir `Contacto.nombre_contacto: str = ""` y migrar el lead de
Lidia (y cualquier futuro lead con contacto identificado) a usar el campo de
primera clase. ~30 min, requiere bumpar `SCHEMA_VERSION` o convivir.

**Cuándo:** cuando aparezca el segundo lead con persona contacto identificada.

---

## TwilioClient en `eleven_outbound` y `twilio_outbound` está duplicado

Los dos módulos construyen auth Twilio de forma idéntica. Si cambia la firma del
API, hay que tocarlo en dos sitios.

**Deuda:** extraer `core.twilio_client` con un cliente común. 1 hora.
