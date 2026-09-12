# Plan de Acción — Departamento Comercial Sintético

Documento de diseño técnico derivado de `Kaizen_DepartamentoComercial_v0.2.docx`.
Cliente piloto: Repostería Laboratorio (Cieza). Canal objetivo: HORECA.

## TL;DR

1. **Construcción por fases con gates numéricos del propio documento.** No se avanza por calendario.
2. **Fase 0** (Researcher + Enrichment + Director Comercial + persistencia total) es **íntegramente implementable ahora**, sin bloqueadores externos. Es lo único que el documento permite encender el día 1.
3. **Fase 1** (SDR Multicanal) tiene bloqueadores externos reales que el operador debe resolver: voz de Iván, Meta Business, Twilio, ElevenLabs, LSSI/RGPD. El canal **email** sí es construible ya (reutiliza `agentes.smtp_send` existente).
4. **Fase 2** (Account Executive/Manager/Ops, muestra → primer pedido → recurrencia) depende de catálogo estructurado de Laboratorio + acuerdo con empresa de transporte.
5. Esta sesión: **plan + Fase 0 completa + verificación contra el criterio del doc (≥100 leads cualificados, descarte <40%, contacto verificado >85%)**.

---

## 1. Diagnóstico — qué hay vs. qué pide v0.2

| Pieza del doc | Estado actual en el repo | Acción |
|---|---|---|
| Director Comercial sintético | No existe (hay `core/director.py` genérico para enrutamiento, no comercial) | Crear `departments/comercial/director.py` que herede de `Department` |
| Researcher (búsqueda paralela multi-fuente) | Existe parcial: `agentes.prospectar` + `departments/prospeccion` hacen lo básico con ddgs | Refactor → `comercial/researcher.py` con N hilos configurables + adaptadores de fuente |
| Enrichment Specialist | No existe como rol separado; está fundido dentro de `prospectar` | Crear `comercial/enrichment.py` con verificación de actualidad ≤90 días |
| SDR Multicanal | No existe; `departments/redaccion` redacta pero no contacta | Crear `comercial/sdr/` con interfaz pluggable de canales |
| Account Executive / Manager / Sales Ops | No existen | Fase 2 |
| Brand Guardian | Parcial: `departments/qa` valida borradores; le falta dimensión de tono/posicionamiento | Crear `comercial/brand_guardian.py` (básico Fase 1, completo Fase 2) |
| ICP de Laboratorio codificado | No existe (los prompts mencionan "artesanal premium" pero no hay filtro determinista) | Crear `comercial/icp.py` con inclusiones/exclusiones del §5.2/§5.3 |
| Anillos geográficos | No existe | Crear `comercial/anillos.py` con haversine + interfaz para Google Routes |
| Lifecycle del lead (estados) | Implícito en el Diario; no hay máquina de estados | Crear `comercial/lifecycle.py` con estados explícitos |
| Compromiso Recíproco | No existe | Detector LLM en `comercial/sdr/compromiso.py` |
| Persistencia "NO SE PIERDE NADA" | Parcial: `diario/<empresa>/clientes/` + Knowledge (in-mem/Neo4j) | Reforzar: schema versionado + auditoría de transiciones de estado |
| Métricas verde/ámbar/rojo | No existe | Crear `comercial/metricas.py` con las 8 métricas del §7.1 |
| Rituales (daily/semanal/forecast) | No existe | `comercial/rituales.py` + scheduler |
| Reporte ejecutivo del viernes (5 secciones) | No existe | `comercial/reporting.py` |
| Hipótesis con revisión quincenal | No existe | Tabla `hypothesis` en Knowledge |
| Checklists por entregable | No existe | Validators inyectables en cada handoff |
| Filtro logístico real (no línea recta) | No existe | Interfaz `DistanceProvider` con fallback haversine y adaptador Routes |
| Voz clonada del empresario | No existe | **BLOQUEADO** (ver §4) |
| WhatsApp Business API | No existe | **BLOQUEADO** (ver §4) |

---

## 2. Arquitectura objetivo

### 2.1 Estructura de carpetas (lo que se añade)

```
departments/
  comercial/                       # NUEVO — paraguas del departamento
    __init__.py
    director.py                    # Director Comercial Sintético (Fase 0)
    jefe_prospeccion.py            # Fase 1
    jefe_cuentas.py                # Fase 2
    researcher.py                  # Fase 0
    enrichment.py                  # Fase 0
    sdr/
      __init__.py
      multicanal.py                # Fase 1 — orquestador
      compromiso.py                # Fase 1 — detector de intención LLM
      canales/
        base.py                    # Interfaz Canal + ResultadoContacto
        email.py                   # Fase 1 — IMPLEMENTABLE (usa smtp_send)
        whatsapp.py                # Fase 1 — BLOQUEADO (Meta)
        voz.py                     # Fase 1 — BLOQUEADO (Twilio+ElevenLabs)
        linkedin.py                # Fase 1 — limitado / supervisado
    account_executive.py           # Fase 2
    account_manager.py             # Fase 2
    sales_ops.py                   # Fase 2
    brand_guardian.py              # Fase 1 básico, Fase 2 completo
    icp.py                         # Filtro de cliente ideal (Fase 0)
    anillos.py                     # Clasificación geográfica (Fase 0)
    lifecycle.py                   # Estados del lead (Fase 0)
    metricas.py                    # Verde/ámbar/rojo (Fase 0)
    reporting.py                   # Reporte viernes (Fase 0)
    rituales.py                    # Schedules de daily/semanal (Fase 0)
    hipotesis.py                   # Registro de hipótesis (Fase 0)
    distancia/
      base.py                      # Interfaz DistanceProvider
      haversine.py                 # Fallback sin clave
      google_routes.py             # Adapter (necesita GOOGLE_MAPS_API_KEY)
    fuentes/
      base.py                      # Interfaz FuenteLeads
      ddgs.py                      # Ya existente, envuelto
      google_places.py             # Adapter (necesita GOOGLE_MAPS_API_KEY)
      yelp.py                      # Adapter (necesita YELP_API_KEY)
      directorios_horeca.py        # Scraping de directorios sectoriales
tests/
  comercial/
    test_icp.py
    test_anillos.py
    test_lifecycle.py
    test_researcher.py
    test_enrichment.py
    test_metricas.py
    test_reporting.py
    test_director_comercial.py
    test_e2e_fase0.py              # Pasada completa con datos reales de Laboratorio
```

### 2.2 Modelo de datos del lead (lifecycle)

Estados explícitos (transiciones registradas como eventos en el bus):

```
identificado            ← Researcher detecta candidato
   ↓ (pasa ICP)
cualificado             ← ICP filter aprueba
   ↓ (pasa Enrichment checklist)
enriquecido             ← contacto verificado <90d, decisor identificado
   ↓ (Fase 1)
en_contacto             ← SDR ha intentado contactar
   ↓ (señal Compromiso Recíproco detectada)
compromiso_reciproco    ← cliente expresa intención verificable
   ↓ (Fase 2: muestra enviada)
muestra_enviada
   ↓ (cliente acepta y compra)
cliente_activo
   ↓
en_riesgo  /  recurrente  /  perdido
```

Schema del lead (`Knowledge.add("laboratorio", "lead", slug, {...})`):

```python
{
  "id": "slug",
  "nombre": "Hotel La Parra",
  "tipo": "hotel_boutique" | "cafeteria_especialidad" | ...,
  "estado": "cualificado",
  "anillo": 1,                       # 0/1/2/3
  "ubicacion": {"lat": ..., "lon": ..., "ciudad": "Murcia"},
  "distancia_logistica_min": 42,     # minutos reales (Routes) o estimación haversine
  "fuentes": ["google_maps", "yelp"],
  "scoring_inicial": 0.78,
  "decisor": {"nombre": "...", "cargo": "F&B Manager", "fuente": "linkedin"},
  "contacto": {"email": "...", "telefono": "...", "whatsapp": "..."},
  "ultima_actividad_publica": "2026-05-10",   # señal de actualidad
  "proveedor_actual": "Berlys",
  "historial": [                    # NO SE PIERDE NADA: cada transición de estado registrada
    {"ts": "...", "evento": "identificado", "fuente": "google_maps"},
    {"ts": "...", "evento": "cualificado", "razon": "tipo+anillo+ICP_ok"},
    ...
  ],
  "checklists": {                   # auditoría de gates de calidad del §8
    "researcher": {"ok": True, "items": [...]},
    "enrichment": {"ok": True, "items": [...]},
  }
}
```

### 2.3 Integración con lo existente

- **`core/bus.py`**: nuevos `EventType` — `LEAD_IDENTIFIED`, `LEAD_QUALIFIED`, `LEAD_ENRICHED`, `LEAD_STATE_CHANGED`, `SAMPLE_DECIDED`, `SAMPLE_SHIPPED`, `RECIPROCITY_DETECTED`, `RITUAL_TRIGGERED`, `WEEKLY_REPORT_GENERATED`, `METRIC_AMBER`, `METRIC_RED`.
- **`core/director.py`** (Director general): aprende a enrutar intents tipo "buscar leads HORECA" al **Director Comercial**, no a `prospeccion` directamente. `prospeccion` queda como herramienta del Researcher.
- **`core/guardian.py`**: las acciones de Fase 1+ (enviar email, llamar, enviar muestra) pasan por Guardian con kinds nuevos (`contact_lead`, `ship_sample`).
- **`diario_ops.py`**: las fichas del Diario siguen siendo la representación humana legible; el Knowledge es la fuente operativa. Sincronización en una dirección: Knowledge → Diario al cambiar de estado.
- **`agentes.prospectar`** (legacy CLI): se mantiene como adaptador del Researcher para no romper la CLI actual.

---

## 3. Roadmap por fases

### Fase 0 — Fundación

**Roles activos:** Researcher, Enrichment Specialist, Director Comercial sintético, ICP, Anillos, Persistencia, Reporting básico.

**Criterio de paso a Fase 1 (del doc §2.1):**
- ≥100 leads cualificados generados
- Descarte por filtro ICP <40%
- Contacto verificado >85%

**Entregables concretos:**

| # | Entregable | Verificación |
|---|---|---|
| 1 | `departments/comercial/` package | imports OK desde tests |
| 2 | `icp.py` con INCLUIR/EXCLUIR del §5.2/§5.3 codificado | test que rechaza "Ballester" y acepta "Hotel La Parra Cieza" |
| 3 | `anillos.py` con haversine + interfaz `DistanceProvider` | test de Cieza→Murcia ≤45min, Cieza→Cartagena ≤90min |
| 4 | `lifecycle.py` con máquina de estados + eventos | test de transiciones válidas/inválidas |
| 5 | `researcher.py` con búsqueda paralela real (ddgs + scraping) | smoke run produce ≥50 candidatos/día |
| 6 | `enrichment.py` con verificación de actualidad ≤90d | test de ficha con/sin señal de actividad |
| 7 | `metricas.py` con las 8 bandas del §7.1 | test con datos sembrados produce verde/ámbar/rojo correcto |
| 8 | `reporting.py` con reporte ejecutivo de 5 secciones | test de generación con datos sembrados |
| 9 | `director.py` Comercial que orquesta los 6 anteriores | test E2E con Laboratorio |
| 10 | CLI `kaizen comercial fase0` (lanza la pasada y guarda métricas) | comando ejecuta sin error y reporta |
| 11 | Tests por componente + E2E | `pytest tests/comercial/ -v` todo verde |
| 12 | Smoke run real contra HORECA Laboratorio | ≥100 cualificados, <40% descarte, >85% verificado |

**Bloqueadores externos para Fase 0:** ninguno crítico.
**Mejoras opcionales:** `GOOGLE_MAPS_API_KEY` (Places + Routes) eleva precisión geográfica y de enriquecimiento. Sin ella, ddgs + scraping + haversine funcionan pero con menor precisión.

### Fase 1 — Contacto

**Roles que se añaden:** SDR Multicanal, Jefe de Prospección, Brand Guardian (básico).

**Criterio de paso a Fase 2 (del doc):**
- 5 clientes en Compromiso Recíproco la primera semana
- Escalado a 10 la siguiente semana

**Lo construible YA en código (independiente de credenciales):**

- `comercial/sdr/multicanal.py`: orquestador con interfaz pluggable.
- `comercial/sdr/compromiso.py`: detector LLM de las señales del §3.2 (no por palabras clave — `claude-sonnet-4-6` interpreta el español rico).
- `comercial/sdr/canales/base.py`: contrato `Canal` (`contactar(lead, mensaje) -> ResultadoContacto`).
- `comercial/sdr/canales/email.py`: **funcional al 100%** sobre `agentes.smtp_send` + plantillas personalizadas + tracking de apertura básico (pixel + redirects).
- `comercial/jefe_prospeccion.py`: scoring + cola priorizada.
- `comercial/brand_guardian.py` básico: validador de tono sobre `CONTEXTO_NEGOCIO.md` de Laboratorio.
- Selector de canal del §4.2 codificado.
- `comercial/sdr/canales/{whatsapp,voz,linkedin}.py`: stubs con la interfaz `Canal` que lanzan `RuntimeError("canal X no configurado: faltan credenciales Y")` con mensaje claro hasta que llegue lo externo.

**Bloqueadores externos para Fase 1 completa:**

| Bloqueador | Quién lo proporciona | Sin esto |
|---|---|---|
| Muestra de voz limpia de Iván (3 min, sin ruido, lectura neutra) | Iván graba | Voz SDR no se activa |
| Cuenta ElevenLabs Pro + voice clone hecho | Operador | Voz SDR no se activa |
| Cuenta Twilio + número español verificado + saldo | Operador | Voz SDR no se activa |
| WhatsApp Business API account + verificación Meta + número | Operador | WhatsApp SDR no se activa |
| Plantillas de WhatsApp aprobadas por Meta | Operador | WhatsApp no envía outbound |
| Política de cumplimiento LSSI/RGPD revisada | Operador / Iván | Voz comercial bloqueada |
| `LINKEDIN_*` o decisión de "supervisado" | Operador | LinkedIn limitado |

### Fase 2 — Cierre y cuidado

**Roles que se añaden:** Account Executive, Account Manager, Sales Ops, Jefe de Cuentas, Brand Guardian completo.

**Bloqueadores externos:**
- API de empresa de transporte (etiquetas, tracking, coste por envío).
- Catálogo estructurado de productos Laboratorio (precios, peso, tiempo de elaboración, stock).
- Capacidad real de Laboratorio para producir muestras al ritmo que el sistema dispare.
- Umbrales económicos finales (§6.2 los marca como propuesta inicial; deben ajustarse por Iván).

---

## 4. Dependencias externas — lo que el operador debe proporcionar

| Recurso | Coste estimado | Fase que desbloquea | Estado |
|---|---|---|---|
| `GOOGLE_MAPS_API_KEY` (Places + Routes) | <10€/mes a este volumen | Fase 0 *mejora*, Fase 1 *requerida* para anillos reales | ⬜ |
| Muestra voz Iván 3min + ElevenLabs Pro ($22/mes) + voice clone | ~25€/mes | Fase 1 (canal voz) | ⬜ |
| Cuenta Twilio + número ES + saldo | ~5€/mes + ~0.07€/min | Fase 1 (canal voz) | ⬜ |
| WhatsApp Business API (proveedor Meta o partner) + verificación | 0-50€/mes según proveedor | Fase 1 (canal WhatsApp) | ⬜ |
| Política LSSI/RGPD aprobada por Iván | tiempo, no €€ | Fase 1 (voz) | ⬜ |
| Acuerdo empresa de transporte + API | variable | Fase 2 | ⬜ |
| Catálogo Laboratorio estructurado (CSV/JSON) | tiempo de Iván | Fase 2 | ⬜ |

---

## 5. Plan de ejecución inmediato (esta sesión)

Construyo **Fase 0 completa** en este orden, ejecutando tests tras cada paso:

1. **Esqueleto del paquete** `departments/comercial/` + `__init__.py`.
2. **`icp.py`** — Filtro de cliente ideal de Laboratorio (datos del §5.2/§5.3 del doc, no hardcodeo: cargado de `comercial/datos/icp_laboratorio.yml` o `.json` para que sea editable sin tocar código).
3. **`anillos.py`** — Clasificación geográfica con `DistanceProvider` abstracto. Default: haversine. Adapter para Google Routes con clave opcional.
4. **`lifecycle.py`** — Estados + transiciones + persistencia en Knowledge.
5. **`hipotesis.py`** — Registro de hipótesis (§7.3).
6. **`researcher.py`** — Búsqueda paralela real con N hilos configurables (`concurrent.futures.ThreadPoolExecutor`), dedup por slug + coords, scoring inicial. Integra `ddgs` y deja interface lista para `google_places`.
7. **`enrichment.py`** — Cruce de fuentes, verificación de actualidad ≤90d, extracción de decisor (LLM sobre snippets de LinkedIn/web).
8. **`metricas.py`** — Las 8 métricas del §7.1 con bandas verde/ámbar/rojo.
9. **`reporting.py`** — Reporte ejecutivo del viernes con 5 secciones del §7.4.
10. **`brand_guardian.py`** básico — validador de tono (se usa en Fase 1; lo dejo listo).
11. **`director.py`** — Director Comercial Sintético que orquesta lo anterior y dispara rituales del §7.2.
12. **CLI** `kaizen comercial fase0` (nuevo subcomando en `kaizen.py`).
13. **Tests** unitarios + integración por componente.
14. **Tests E2E** Fase 0 con datos sembrados que reproducen la calidad esperada.
15. **Smoke run real** contra Laboratorio: ejecuta la pasada, mide contra los gates del doc.
16. **Documentar el resultado** en `docs/VALIDACION_FASE0_COMERCIAL.md` con números reales.

**Lo que NO toco en esta sesión:**
- `departments/prospeccion`, `departments/redaccion`, `departments/qa`, `departments/legal`, `departments/finanzas`, `departments/ops` — siguen funcionando como están. El nuevo `comercial/` los usa, no los reemplaza. Migración total a la nueva estructura queda como follow-up cuando Fase 0 esté validada.

---

## 6. Criterio de "funciona" — verificable

Una pasada `kaizen comercial fase0 --empresa laboratorio --objetivo 100` debe terminar con:

```
✓ Researcher: 247 candidatos identificados (de 4 fuentes)
✓ ICP filter: 162 cualificados, 85 descartados (34.4%) ✅ (<40%)
✓ Enrichment: 142 con contacto verificado (87.7%) ✅ (>85%)
✓ Lifecycle: 142 leads en estado 'enriquecido' persistidos
✓ Reporting: docs/REPORTE_FASE0_<fecha>.md generado
✓ Métricas: Researcher VERDE · Enrichment VERDE
✓ Criterio de paso a Fase 1: CUMPLIDO (142 ≥ 100)
```

Si alguno de los gates no se cumple, el sistema reporta concretamente qué falló y **no marca Fase 0 como superada**.

---

## 7. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| `ddgs` rate-limit en pasadas grandes | Retries con backoff (ya implementado en `agentes._fetch_page` y `cli_utils.max_retries`). Diversificación de queries por ciudad/segmento. |
| Sin Google Routes, el filtro logístico es aproximación recta | Haversine como fallback documentado. Interfaz `DistanceProvider` permite enchufar Routes sin tocar el resto. |
| LinkedIn API restringida | Decisión registrada: "automatización supervisada" (el propio doc §9.2 lo admite). El enriquecimiento usa scraping público + LLM, no la API oficial, salvo que el operador la habilite. |
| Coste LLM en pasadas grandes | El Researcher solo usa LLM para clasificar (haiku, barato); Enrichment usa sonnet solo para extraer decisor; ICP es determinista sin LLM. Estimado: <0.50€ por pasada de 100 leads. |
| Persistencia: Neo4j puede no estar disponible | Fallback a `InMemoryKnowledge` ya existe; en Fase 0 esto es aceptable porque el Diario en disco actúa como respaldo legible. Para Fase 2 se exige Neo4j real (la regla "NO SE PIERDE NADA" lo impone). |

---

## 8. Lo que este plan NO resuelve (queda para iteraciones)

- Migración de los departamentos legacy (`prospeccion`/`redaccion`) bajo el paraguas `comercial/`. Coexisten hasta que Fase 0 valide la nueva ruta.
- Stack final de WhatsApp Business (provider directo Meta vs. partner como 360dialog, Twilio Conversations, etc.). Decisión del operador.
- Texto exacto de la política LSSI/RGPD para llamadas comerciales. Necesita revisión legal.
- Catálogo Laboratorio estructurado y motor de upselling — Fase 2.
- Loop de aprendizaje (§9.3) — empieza vacío en Fase 0 y se llena con hipótesis confirmadas a partir de la primera semana real.

---

*Plan derivado de Kaizen_DepartamentoComercial_v0.2.docx · 2026-05-26*

---
Relacionados: [[VALIDACION_FASE0_COMERCIAL]]
