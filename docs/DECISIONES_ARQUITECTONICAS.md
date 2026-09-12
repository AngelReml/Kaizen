# Decisiones arquitectónicas — Sistema Nervioso

Log inmutable. Cada decisión no trivial deja huella aquí con: contexto, opciones
consideradas, decisión, consecuencias. No se reescribe el pasado — si una decisión
cambia, se añade un nuevo ADR que la supersede.

Formato: ADR-NNN (Architecture Decision Record).

---

## ADR-001 — Esquema del lead como dataclass + validación blanda

**Fecha:** 2026-05-27 (sistema nervioso)

**Contexto:**
Los 466 leads en `state/knowledge.json` viven como `dict[str, Any]`. Funciona pero:
(a) cualquier campo nuevo se puede meter sin que nadie se entere; (b) no hay
contrato; (c) los IDEs no autocompletan; (d) los tests no detectan typos.

Necesitamos esquematizar **sin romper los 466 leads ya enriquecidos**.

**Opciones consideradas:**

1. **Pydantic BaseModel:** validación dura, serialización gratuita, requiere añadir
   dependencia. Penaliza si un lead viejo no cumple (lanza al cargar).
2. **TypedDict puro:** anotación de tipos sin validación runtime. Cero penalización
   con leads existentes. Pero no devuelve errores útiles.
3. **Dataclass + función `from_dict()` con defaults:** validación blanda (acepta
   leads existentes, rellena defaults), error claro si falta un campo crítico.
   Cero dependencias nuevas. Compatible con `asdict()` para volver a JSON.

**Decisión:** Opción 3 (dataclass + from_dict con defaults).

**Consecuencias:**

- Los 466 leads existentes se cargan sin tocar; los campos nuevos del esquema
  obtienen defaults. Migración = nil al leer.
- Las escrituras nuevas pasan por `LeadDoc(...)` y `asdict()`; los typos se
  detectan antes de persistir.
- Si en futuro se necesita Pydantic (e.g., para una API REST), se añade en
  paralelo sin romper el dataclass.

---

## ADR-002 — Nueva máquina de estados en `core/`, sin sustituir la vieja

**Fecha:** 2026-05-27

**Contexto:**
`departments/comercial/lifecycle.py` define `EstadoLead` con 9 estados (IDENTIFICADO,
CUALIFICADO, ENRIQUECIDO, EN_CONTACTO, COMPROMISO_RECIPROCO, MUESTRA_ENVIADA,
CLIENTE_ACTIVO, EN_RIESGO, PERDIDO).

El prompt del sistema nervioso pide 12 estados más granulares (COLD, QUEUED,
CONTACTING, NO_ANSWER, CONTACTED, ENGAGED, SAMPLE_REQUESTED, SAMPLE_SENT, TRIAL,
CUSTOMER, LOST, DO_NOT_CALL).

Hay código existente (Researcher, Enrichment, SDR, etc.) que importa `EstadoLead`.

**Opciones consideradas:**

1. **Sustituir `EstadoLead`:** romper imports en ~10 sitios. Mucha sangre.
2. **Renombrar el viejo a `EstadoLegacy` y nombrar al nuevo `EstadoLead`:** los
   imports rompen igual, solo cambiamos el nombre del culpable.
3. **Coexistir:** `core/pipeline_state_machine.EstadoPipeline` (nuevo) + mapeo a
   `EstadoLead` viejo. El viejo se mantiene operativo. Mientras tanto, los
   módulos nuevos usan `EstadoPipeline`; los viejos siguen como están. Migración
   gradual.

**Decisión:** Opción 3 (coexistir).

**Consecuencias:**

- Cero código existente roto.
- Los leads en el knowledge ganan un campo nuevo `estado_pipeline` (12 estados);
  el campo `estado` antiguo se mantiene. Cada lead vive en ambos espacios hasta
  que la migración a fondo (otra sesión) consolide.
- Mapeo bidireccional explícito en `core/pipeline_state_machine.py:mapear_legacy()`.
- Tradeoff: complejidad temporal (dos estados convivientes). Se acepta como deuda
  con plazo (ver [[TODO]]).

---

## ADR-003 — Política de reintentos en JSON externo, no en código

**Fecha:** 2026-05-27

**Contexto:**
Cada categoría de lead (hotel boutique, cafetería de especialidad, etc.) puede
requerir cadencias distintas. Y queremos que Iván las ajuste sin tocar código.

**Decisión:** Las reglas viven en `empresas/<empresa>/politica_reintentos.json`.
El motor (`core/reintentos.py`) carga el JSON al arrancar y lo evalúa con datos
del lead. Cambios al JSON → próxima invocación los recoge sin reiniciar.

**Consecuencias:**

- Iván puede editar el archivo a mano si una categoría tiene cadencia errónea.
- El motor no nombra ninguna empresa específica — completamente data-driven.
- Tests cubren combinaciones edge: callback vence en franja prohibida, reintento
  fuera de horario, máximo de reintentos alcanzado.

---

## ADR-004 — LLM para detector de compromisos: Claude Sonnet 4.6

**Fecha:** 2026-05-27

**Contexto:**
El detector de compromisos lee un transcript y extrae fechas, horas, productos,
direcciones. Necesita razonamiento contextual + structured output (JSON validable).

**Opciones consideradas:**

1. **Claude Sonnet 4.6:** ya en uso para Brand Guardian y CompromisoDetector
   (post-call de la conversacional anterior). Excelente en español, tool-use
   maduro. ~$0.005/llamada en el escenario típico (transcript <2k tokens).
2. **Gemini Flash 2.0:** más barato, pero menos consistente con structured output
   en español según experiencia previa.
3. **GPT-4o-mini:** barato y rápido, pero el operador descartó OpenAI por
   coherencia de stack en sesión anterior (ver historial commit `pivote a
   Sonnet`).

**Decisión:** Claude Sonnet 4.6 (mismo que ya se usa). Coste estimado al volumen
piloto (~50 llamadas/semana × 1 detector call) ≈ €0.25/semana.

**Consecuencias:**

- Reutilizamos `claude_client.chat` ya integrado y contabilizado.
- Si en futuro queremos cambiar provider, está aislado tras la interfaz
  `CompromisoLLM.detectar(transcript)`.

---

## ADR-005 — Consulta natural: LLM traduce a query estructurada, no a SQL

**Fecha:** 2026-05-27

**Contexto:**
`kaizen pregunta "qué leads están interesados"` necesita convertir lenguaje natural
en lectura sobre el knowledge.

**Opciones consideradas:**

1. **Text-to-SQL:** habría que tener un SQL real (tenemos JSON anidado). Pasar a
   SQLite añade infra. El operador valora simplicidad.
2. **Text-to-Filter:** el LLM devuelve un dict
   `{tipo, estado_pipeline, categoria, fecha_desde, fecha_hasta, agg}` que el
   código ejecuta sobre `KnowledgeStore.all()`. JSON validable, ejecuta sin
   inventarse nada.
3. **Embeddings + RAG:** sobre-ingeniería para el volumen actual (~500 leads).

**Decisión:** Opción 2 (Text-to-Filter). Pattern documentado en
`docs/CONSULTA_NATURAL.md`.

**Consecuencias:**

- Universo de preguntas inicialmente acotado pero extensible añadiendo campos al
  schema del filtro.
- Cero riesgo de SQL injection (no hay SQL).
- Cuando llegue una pregunta fuera del schema, el LLM devuelve
  `{"unsupported": true, "razon": "..."}` → el CLI responde "todavía no sé
  contestar a eso" en vez de inventar.

---

## ADR-006 — Dashboard en consola con `rich`, no web

**Fecha:** 2026-05-27

**Contexto:**
El Director Comercial necesita ver estado del pipeline, próximas acciones,
compromisos críticos.

**Opciones consideradas:**

1. **Dashboard web (FastAPI ya existe):** bonito visualmente pero requiere
   abrir browser, tener server corriendo. Para "Iván quiere mirar antes del
   primer café": fricción.
2. **CLI con `rich`:** ya está en el stack. Comando `kaizen comercial dashboard`
   imprime tablas. Cero infra extra.

**Decisión:** CLI con `rich`.

**Consecuencias:**

- Cero dependencias nuevas.
- Si después se quiere web, el `dashboard_director.py` ya devuelve estructuras
  serializables; basta envolverlo en endpoints FastAPI.

---

## ADR-007 — Migración del knowledge: no destructiva, idempotente

**Fecha:** 2026-05-27

**Contexto:**
Los [[REGISTRO_P9_LEADS|466 leads]] existentes tienen campos del viejo schema. El sistema nervioso
añade campos nuevos. Hay riesgo de corromper datos si la migración es agresiva.

**Decisión:**

- La migración es **una función** (`core.knowledge_migration.migrar()`) que se
  ejecuta una sola vez vía CLI (`kaizen migrar-knowledge`).
- Cada lead se enriquece con defaults para los campos nuevos del esquema sin
  tocar los existentes.
- Idempotente: si se ejecuta dos veces, no hay efecto distinto en el lead.
- Se hace un backup automático en `state/knowledge.json.bak.<timestamp>` antes
  de tocar nada.

**Consecuencias:**

- Cero riesgo de perder los 463 leads del piloto.
- Si la migración tiene un bug, basta `cp knowledge.json.bak.* knowledge.json` y
  revertir.
- Tests con leads sintéticos antes y después garantizan idempotencia.

---
Relacionados: [[CONSULTA_NATURAL]]
