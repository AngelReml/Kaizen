# Módulo 1 — Modelo de datos del lead

Esquema unificado del lead enriquecido. Una vez aplicado, **cada lead en
`state/knowledge.json` cumple este contrato**: existe acceso programático
tipado, defaults para campos nuevos, validación blanda.

## Filosofía

- **Compatible con los [[REGISTRO_P9_LEADS|466 leads]] ya enriquecidos.** Los campos nuevos del esquema
  obtienen defaults al cargar; cero migración destructiva.
- **Dataclass con `from_dict` blando.** Si llega un campo desconocido, NO se descarta
  — se preserva en `metadatos_extra` para no perder datos.
- **Subdocumentos tipados.** Interacciones, compromisos, contacto, reintentos viven
  como dataclasses anidadas para que los IDEs y mypy ayuden.

## Estructura

```python
LeadDoc
├── id: str                              # slug estable
├── nombre: str
├── categoria_icp: str                   # hotel_boutique_con_desayuno, etc.
├── prioridad_icp: Optional[Literal["ALTA","MEDIA","BAJA"]]
├── anillo: int                          # 0=Cieza, 1=Murcia, 2=Cartagena, 3+
├── ubicacion: Ubicacion
│   ├── lat: float
│   ├── lon: float
│   └── direccion: str
├── contacto: Contacto
│   ├── telefono: Optional[str]
│   ├── email: Optional[str]
│   ├── email_verificado: bool
│   ├── web: Optional[str]
│   ├── instagram: Optional[str]
│   └── fuente_descubrimiento: str       # google_places, ddgs, manual…
├── estado: str                          # legacy EstadoLead (str)  — ADR-002
├── estado_pipeline: str                 # nuevo EstadoPipeline (str)
├── fecha_ultima_transicion: str         # ISO8601 UTC
├── razon_ultima_transicion: str
├── interacciones: list[Interaccion]
│   ├── ts: str                          # ISO UTC
│   ├── tipo: Literal["llamada","email","whatsapp","linkedin","manual"]
│   ├── direccion: Literal["outbound","inbound"]
│   ├── resultado: str                   # contestado, no_contesta, opt_out…
│   ├── canal_id: Optional[str]          # call_sid, message_id, etc.
│   ├── transcript_id: Optional[str]
│   ├── resumen_llm: Optional[str]       # 2-3 frases
│   └── duracion_s: Optional[float]
├── compromisos: list[Compromiso]
│   ├── id: str
│   ├── tipo: Literal["callback","muestra","email_info","referido","visita"]
│   ├── fecha_objetivo: str              # ISO UTC con hora aprox
│   ├── tolerancia_min: int              # ±15 default
│   ├── contexto: str                    # qué se prometió en lenguaje natural
│   ├── origen_interaccion_id: Optional[str]   # ref al evento que lo generó
│   ├── cumplido: bool
│   └── cumplido_en: Optional[str]
├── memoria_conversacional: str          # resumen acumulado del LLM tras cada interacción
├── reintentos: PoliticaReintentos
│   ├── proxima_accion_ts: Optional[str] # cuándo es la próxima acción programada
│   ├── proxima_accion_tipo: Optional[Literal["llamar","email","nurturing"]]
│   ├── intentos_realizados: int
│   ├── max_intentos: int
│   └── ultima_razon_reintento: str
├── checklists: dict                     # legacy (researcher/enrichment checks)
├── fuentes: list[dict]                  # legacy (google_places id_externo, ddgs, etc.)
├── metadatos_fuente: dict               # legacy (rating, ratings_count, business_status…)
├── descripcion: str
├── tamano_estimado: Optional[str]
├── actualidad_signal: Optional[dict]
├── do_not_call: bool                    # opt-out duro
├── historial: list[dict]                # legacy (transiciones del EstadoLead viejo)
├── company: str                         # "laboratorio"
├── creado_en: str                       # ISO UTC
├── actualizado_en: str
├── agente_responsable: Optional[str]    # qué agente sintético "tiene" el lead
├── _schema_version: int                 # 1 = post sistema nervioso
└── metadatos_extra: dict                # campos que vinieron del JSON pero no estaban modelados
```

## Comportamiento de `from_dict`

```python
LeadDoc.from_dict(raw: dict) -> LeadDoc
```

Reglas:

1. **Campos del schema presentes:** se asignan con su valor.
2. **Campos del schema ausentes:** valor por defecto del dataclass.
3. **Subdocumentos:** se construyen recursivamente con `Interaccion.from_dict`, etc.
4. **Campos extras del JSON no modelados:** preservados en `metadatos_extra` (no
   se descartan).
5. **`_schema_version`:** si ausente, se asume 0 (legacy) y se rellena con 1 al
   construir. Una migración del knowledge actualiza el valor al persistir.
6. **`estado_pipeline`:** si ausente, se deriva del `estado` legacy vía
   `mapear_legacy_a_pipeline()` (ver M2).

## Comportamiento de `to_dict` (vía `asdict` + cleanup)

- Serializa como dict listo para `json.dump`.
- `Optional[X]` → `None` queda como `null`.
- Listas vacías y dicts vacíos se preservan (no se omiten) para que el contrato
  sea idéntico siempre.
- `metadatos_extra` se "desempaqueta" al nivel del lead para que la representación
  JSON sea plana (los campos que vinieron del legacy salen como vinieron).

## Validaciones blandas

Solo dos validaciones que sí lanzan:

1. **`id` y `company` obligatorios.** Si faltan, `ValueError` claro.
2. **`estado_pipeline` debe ser uno del enum.** Si llega un valor desconocido,
   `ValueError` con la lista de valores válidos.

El resto es "best effort": un teléfono con formato raro NO bloquea la carga del
lead — el motor de reintentos decidirá si llamar o no.

## Test plan

- `from_dict` con un lead vacío `{"id": "x", "company": "laboratorio"}` → defaults
  llenan todo.
- `from_dict` con un lead legacy real (caso `restaurante_la_cabana` del piloto
  con todos los campos del JSON) → no se pierde ningún campo.
- `to_dict` round-trip: `dict → LeadDoc → dict` produce dict idéntico (los
  campos extras vuelven a su sitio).
- Subdocumentos: añadir una interacción, un compromiso, un reintento → se
  serializan/deserializan bien.
- `estado_pipeline` ausente con `estado="enriquecido"` → mapea a `"cold"`.
- `id` faltando → `ValueError`.

## Por qué no Pydantic / TypedDict

Resumen del ADR-001:

- **Pydantic:** cero deps nuevas es deseable; un lead viejo malformado tumbaría
  el load.
- **TypedDict:** no hay errores útiles en runtime, los typos no se detectan.
- **Dataclass + from_dict:** los 466 leads cargan sin tocar; defaults se rellenan;
  los typos al escribir se detectan; cero deps.

## Lo que NO modela este esquema (deliberado)

- Métricas agregadas (eso vive en la capa de NLQ + dashboard).
- Estado interno del SDR (qué llamada está en curso ahora) — vive en `llamada`
  como tipo separado.
- Información de pago (CUSTOMER no tiene aún campo de facturación; cuando llegue
  Account Executive sí).
