# Dossier de estado documental — `docs/`

**Fecha:** 2026-08-02 · **Método:** lectura completa de los 33 `.md` de `docs/` en orden de
creación, contrastada contra el código, el árbol de ficheros y `git`.
**Fuentes de verdad usadas para contrastar:** `docs/DOSSIER_FUNCIONAMIENTO_INTERNO.md` y
`docs/AUDITORIA_2026-08-02.md` (ambos de hoy, escritos desde lectura directa del código).

Este documento no describe el sistema: describe **la documentación del sistema**, y dice
qué parte de ella ya no es cierta.

---

## 0. Veredicto en una página

`docs/` es un **archivo de mayo de 2026**. 29 de los 33 documentos se escribieron entre el
24 y el 28 de mayo; solo 4 son posteriores, y 2 de esos 4 son de hoy. El sistema, en
cambio, ha vivido tres meses más y ha cambiado de arquitectura dos veces.

Los tres problemas de fondo, por orden de gravedad:

1. **Fractura documental.** `docs/` documenta la **primera generación** del sistema (G1:
   `core/` + `departments/`). Las generaciones 2 y 3 —el sustrato canónico, los cubos, el
   comité 3×3, los gates de autonomía, el RUE, el Centro de Mando— viven documentadas en
   **55 ficheros `.md` en la raíz del repo** (`KAIZEN_ARQUITECTURA_CANONICA_v1_0.md`,
   `KAIZEN_D00…D10`, `MAPA_VIVO.md`, `ESTADO_REAL.md`, `INFORME_*`, `MOC_*`) y en la
   carpeta `conceptos/`. Ningún documento de `docs/` anterior a hoy los menciona. Quien
   lea solo `docs/` entenderá **un tercio del sistema y creerá que lo entiende entero**.

2. **Conflicto de autoridad.** Cuatro documentos se declaran, cada uno, fuente de verdad:

   | Documento | Qué se arroga | ¿Sigue siéndolo? |
   |---|---|---|
   | `docs/ARQUITECTURA.md` | «fuente única de verdad del estado del proyecto» | **No.** Describe un stack que en buena parte no corre. |
   | `docs/ROADMAP_KAIZEN.md` | «Plan vigente» (lo afirma `ARQUITECTURA.md`) | **No.** Ninguna de sus fases se cerró formalmente. |
   | `KAIZEN_ARQUITECTURA_CANONICA_v1_0.md` (raíz) | canónico de G3 | Sí, para G3 — pero `docs/` lo ignora. |
   | `docs/DOSSIER_FUNCIONAMIENTO_INTERNO.md` | «cómo funciona por dentro» | **Sí.** Es de hoy y está verificado contra el código. |

   No hay un documento que diga cuál gana. Este dossier propone que gane el último.

3. **Los planes murieron sin acta de defunción.** `PLAN_PRODUCCION.md` sí lleva su nota de
   «superado por». Los demás no. `PLAN_VOZ_BIDIRECCIONAL.md` fue sustituido por
   `PLAN_VOZ_CONVERSACIONAL.md`, y este último fue **desmentido por los hechos** en
   `VALIDACION_V1_VOZ_BIDIRECCIONAL.md` — pero sigue leyéndose como si fuera el plan
   vigente, y termina pidiendo cuatro decisiones que se tomaron hace dos meses.

### La prueba más limpia de que `ROADMAP_KAIZEN.md` está muerto

Su Anexo B, regla 4, exige: *«Cada fase se cierra con un commit etiquetado.
`git tag v0.X`»*. Y el criterio de salida de cada una de las 9 fases repite
«Tag `v0.X` aplicado».

```
$ git tag
rescate/ddgs-20260524
```

**Cero tags de versión.** Ninguna fase del roadmap se ha cerrado nunca según su propio
criterio, en 66 commits y tres meses. Y su Anexo B, regla 7, previó exactamente esto:
*«Si se descubre que el roadmap es inadecuado, se rehace formalmente, no se ignora
silenciosamente.»* Se ignoró silenciosamente.

---

## 1. Cómo datar cualquier documento del repo: el contador de tests

Casi todos los documentos citan el número de tests en verde. Es un fósil que permite
datar un documento sin mirar su fecha, y medir cuánto se ha alejado:

| Tests declarados | Documento que lo dice | Distancia a hoy |
|---:|---|---|
| 44 | `PLAN_PRODUCCION.md` | 872 tests de retraso |
| 52 | `ROADMAP_KAIZEN.md` («Estado actual, commit `9496dbb`») | 864 |
| 107 | `ARQUITECTURA.md` | 809 |
| 176 | `VALIDACION_FASE0_COMERCIAL.md` | 740 |
| 495 | `SIGUIENTE_SESION.md` | 421 |
| 507 | `SISTEMA_NERVIOSO.md` | 409 |
| 669 | `MANUAL_KAIZEN.md` | 247 |
| **916 passed · 1 failed · 7 skipped** | **`AUDITORIA_2026-08-02.md` (hoy)** | **0** |

Regla práctica: **si un documento de `docs/` cita menos de 900 tests, todo lo que afirme
sobre el estado del sistema hay que verificarlo antes de creerlo.**

---

## 2. Ficha por documento

Leídos en orden de creación, que es el orden en que el proyecto los produjo.

Leyenda: 🟢 vigente · 🟡 parcialmente desactualizado · 🔴 desactualizado · ⚪ histórico
(congelado a propósito; correcto como registro, no como referencia).

---

### 🔴 `VALIDACION_E2E_REAL.md` — 24/5, nunca modificado
Plantilla vacía. Sigue diciendo **«ESTADO: PENDIENTE»** y todos sus checkboxes están sin
marcar, tres meses después.

- **Qué falla:** era el entregable obligatorio de la Fase 0.2 del roadmap, y su ausencia
  bloqueaba formalmente todo lo demás. Se construyó todo lo demás igualmente.
- **Y además ya no aplica:** pide validar `RedisStreamsBus` / `Neo4jKnowledge` /
  `PostgresConfig`. El sistema real **no usa ninguno de los tres** en el camino que corre:
  la verdad comercial vive en `state/knowledge.json` (G1) y `data/kaizen.db` (G3)
  — Dossier §5. El bus Redis, además, **no consume el stream** (auditoría C-07): es un bus
  intra-proceso con log en Redis.
- **Qué hacer:** archivar como «criterio abandonado con la Fase 0» o reescribir contra los
  backends reales. Dejarlo como está es mantener vivo un gate que nadie va a cruzar.

### 🟡 `FINANZAS_SCHEMA.md` — 24/5
El modelo conceptual (`Gasto`/`Categoria`/`Presupuesto`/`Alerta` sobre `KnowledgeStore`)
sigue siendo correcto, y `departments/finanzas/` existe.

- **Qué falta:** hoy hay **cuatro contadores de gasto independientes** (Dossier §9):
  `claude_client.py`, `core/cost_tracker.py`, `core/ledger.py`+`techos.py` y
  `sustrato/coste.py` — más un quinto tope de sesión en `pruebas_produccion/`
  (auditoría G-16). Nada de eso está aquí.
- La «limitación conocida (deuda #13)» que declara sigue abierta, y se ha multiplicado.
- No menciona la **escalera de degradación** de `core/techos.py` (bajar de modelo → diferir
  → pausar), que es hoy el comportamiento real ante el techo.

### 🟡 `COMO_CREAR_UN_DEPARTAMENTO.md` — 24/5
Las 9 secciones del patrón siguen siendo buen consejo. **La unidad de construcción ha
cambiado.**

- Hoy un departamento nuevo es un **cubo**: necesita `cubos/<nombre>/manifest.json`
  declarando qué produce, qué consume, su `nivel_autonomia_defecto` y sus
  `acciones_irreversibles` (Dossier §10). El checklist del documento no pide nada de eso.
- Tampoco menciona los **gates de autonomía** ni el **comité 3×3**, que son hoy lo que
  decide si un departamento puede actuar hacia fuera.
- **Riesgo real:** alguien que siga este checklist al pie de la letra construirá un
  departamento que el sustrato no reconoce.

### 🔴 `CASOS_DE_USO.md` — 24/5, nunca modificado
- La nota final dice *«Versión pública resumida: pendiente de publicar en una URL — tarea
  del operador»*. **Sigue pendiente.** Era criterio de salida de la Fase 1.
- Dice del departamento de Finanzas: *«funcional y probado en memoria. Validación con
  datos reales en Fase 0.2»* — Fase 0.2 nunca se cerró (ver `VALIDACION_E2E_REAL`).
- Su párrafo de honestidad («Laboratorio aún no ha operado el sistema en real») **sigue siendo
  cierto**, y ese es el dato importante: tres meses después, el caso de uso número 1 sigue
  sin cliente operando. Ningún documento posterior lo dice tan claro.

### 🟡 `DESARROLLO_RRHH_POSPONER.md` — 25/5
La **decisión** sigue vigente y bien fundada. El **inventario** no.

- Dice: *«Reales: Prospección, Redacción, Finanzas, QA, Ops, Legal. Cascarones:
  Desarrollo, RRHH»*.
- Hoy (`MANUAL_KAIZEN.md` §4 + Dossier §10) hay **10 cubos constituidos**: comercial,
  brand, marketing, customer_success, inteligencia, finanzas, legal, ops, qa, rrhh. Y
  `rrhh` no es un cascarón: está **constituido y pospuesto**, que es otra cosa.
- «Desarrollo» ya no aparece en la lista de cubos; sí sigue como cascarón en
  `departments/especialistas.py` (auditoría D-11).

### 🔴 `ROADMAP_KAIZEN.md` — 25/5 · 47 KB · **el documento más desactualizado del repo**
Se presenta como el plan vigente. No lo es desde hace meses.

- **Estado declarado:** «commit `9496dbb`», «v0.0», «52 tests verdes», «Adaptadores
  escritos (no validados en vivo) para Neo4j y PostgreSQL». Nada de eso describe hoy.
- **Fase 0 nunca se cerró** (falta `VALIDACION_E2E_REAL`, falta el tag `v0.1`), y sin
  embargo se abrieron las Fases 1 y 5 y se construyó un departamento comercial entero que
  el roadmap no contempla.
- **El camino real que siguió el proyecto no está aquí:** departamento comercial (Fase 0
  de *otro* plan) → voz conversacional → sistema nervioso M1-M8 → sustrato canónico y
  cubos → Centro de Mando y Mesa del Jefe → candado del AI Act. Cinco hitos mayores,
  ninguno previsto.
- **Partes que se construyeron de otra manera:** la Fase 3 pide auth con sesiones, roles y
  audit log con hash chain; existe todo eso, pero en `panel_mando/` (sesiones con TTL de
  servidor, CSRF, `/logout`) y en las **cuatro cadenas de hash** del sustrato — no como
  describe el roadmap. La Fase 4 (despliegue) sigue sin hacerse y ha reaparecido como
  «S5» en el plan del `MANUAL_KAIZEN.md`.
- **Qué hacer:** o se rehace formalmente (su propia regla de gobernanza 7 lo exige) o se
  marca como histórico y se señala al plan real. Lo que no puede seguir es citándose como
  «Plan vigente» desde `ARQUITECTURA.md`.

### 🔴 `ARQUITECTURA.md` — 25/5 · se autodeclara «fuente única de verdad»
Es el documento cuya desactualización más daño hace, porque su primera línea reclama
autoridad total.

| Afirma | Realidad hoy |
|---|---|
| Orquestación: **LangGraph** | Nunca se integró. El propio doc lo marca «diferida»; sigue diferida. |
| Frontend: **React + WebSockets** | HTML plano en `api/static/` + `panel_mando/` (FastAPI + HTML sin JS de framework). |
| Memoria: **Neo4j, un grafo por empresa** | `state/knowledge.json` y `data/kaizen.db` (SQLite). Neo4j nunca se validó en vivo. |
| Config: **PostgreSQL** | Ídem. |
| Ejecutor local: **Shinobi (Node.js)** | No aparece en el árbol. |
| **107 tests verdes** | 916. |
| «8 departamentos» | 10 cubos + los departamentos G1. |
| Fases 1-6 marcadas COMPLETA ✅ | Son las fases de *otro* esquema de fases, distinto del de `ROADMAP_KAIZEN.md`. **Dos numeraciones de fase incompatibles conviven en el mismo repo sin aviso.** |

- **No menciona en absoluto:** el sustrato canónico, los cubos, el comité 3×3, los gates
  de autonomía, el RUE, el pánico (PARAR TODO), las cadenas de hash, el candado del AI
  Act, el registro P9, el Centro de Mando ni la Mesa del Jefe. Es decir: **no menciona
  dos tercios del sistema**.
- **Lo que sí conserva valor:** la tabla de `ClaseTarea` → tier de modelo y el inventario
  de especialistas por departamento (§ *Sub-agentes y routing*) siguen describiendo
  `core/model_router.py` razonablemente, con la salvedad de que los IDs de modelo están
  atrasados (auditoría D-01).

### ⚪ `PLAN_PRODUCCION.md` — 25/5
**El único documento que hace bien lo de morir.** Lleva su nota de superación en cabecera
y se declara «registro del primer veredicto honesto».

- Ironía útil: el sucesor que nombra (`ROADMAP_KAIZEN`) también está muerto, así que la
  cadena de sucesión apunta a un documento fantasma.
- Su veredicto de fondo («NO está listo para producción; los bloques F-H dependen de
  infraestructura, dinero y tiempo que son tuyos») sigue siendo **exacto** tres meses
  después. Los bloques F (operación/despliegue), G (validación con uso real) y H
  (enterprise) siguen sin empezar.

### 🟡 `DEUDA_TECNICA.md` — 25/5, con anexo del 3/7
Sigue siendo un documento honesto y varias de sus deudas están **confirmadas** por la
auditoría de hoy. Pero ha quedado superado y no lo sabe.

| Deuda de mayo | Estado hoy según la auditoría |
|---|---|
| #4 WebSocket sin filtrar por empresa | Abierta. Agravada: `/health` tampoco autentica (E-10). |
| #9 `RedisStreamsBus` sin consumidores | Abierta y confirmada (C-07, C-08). |
| #10 Neo4j/Postgres nunca validados en vivo | Abierta. Y probablemente ya irrelevante: el camino real no los usa. |
| #13 Coste global, no por empresa | Empeorada: hoy son **cuatro** contadores (G-16). |
| #3 Guardián semántico asume buena fe | Confirmada y agravada: **falla en abierto** (B-04, prioridad máxima). |
| DT-26.07.03-3 Dos IDs de Sonnet | Confirmada y ampliada (B-01: tres tablas de tarifas contradictorias, D-01). |
| DT-26.07.03-1 Tests de voz envenenan la quota real | No aparece en la auditoría de hoy; verificar si sigue viva. |

- **Qué hacer:** añadir una nota de cabecera apuntando a `AUDITORIA_2026-08-02.md` (51
  hallazgos) como lista vigente, y conservar esta como historia.

### 🟡 `PLAN_DEPARTAMENTO_COMERCIAL.md` — 26/5
**El plan que sí se ejecutó.** Es el documento de diseño más útil de `docs/`, y por eso
merece mantenimiento.

- **Fase 0:** entregada y validada (463→466 leads, gates superados).
- **Fase 1:** construida a medias y **hoy bloqueada por dos candados que el plan no podía
  prever**:
  - canal email → cerrado en duro desde hoy por el AI Act (auditoría **F-01**);
  - canal voz → bloqueado por `TWILIO_FROM_NUMBER` no conforme a la Orden TDF/149/2025
    (**B-11**).
- **Fase 2** (Account Executive / Manager / Sales Ops): sin empezar.
- La tabla de «Dependencias externas» (§4) está caducada: todas las casillas siguen en
  ⬜, pero varias se resolvieron (Google Maps, ElevenLabs, voice clone, Twilio) y otras
  cambiaron de naturaleza (la LSSI/RGPD ya no es «pendiente de revisar» sino un conjunto
  de candados implementados: Robinson, franja horaria, AI Act, numeración de origen).

### ⚪ `REPORTE_FASE0_20260526_1257.md` y `REPORTE_FASE0_20260526_1326.md` — 26/5
Artefactos generados por máquina. Congelados por naturaleza, correctos como evidencia.

- **Problema menor pero real:** son dos reportes de la misma cosa con **29 minutos de
  diferencia** y cifras distintas (463 vs 465 cualificados; 89,5 % vs 88,7 % ICP). Sin
  contexto, quien los lea no sabe cuál vale. Hoy la cifra buena es **466**.
- Uno de los dos sobra, o hace falta una línea que diga cuál es la pasada canónica.
- Nota de calidad: el primero imprime `91.14470842332614%` — un porcentaje con 14
  decimales en un reporte ejecutivo.

### ⚪ `VALIDACION_FASE0_COMERCIAL.md` — 26/5
Evidencia válida del gate de Fase 0. Como registro, intacto.

- **Cola operativa caducada:** su sección «Lo que sigue (Fase 1)» pide confirmar
  `IVAN_VOICE_ID` («cuál de las 2 voces clonadas»), hacer *claim* de un número desde la
  cuenta Twilio **Trial** y montar `PUBLIC_MEDIA_BASE_URL`. Todo eso se resolvió o cambió
  de forma: hoy hay `IVAN_VOICE_ID` en `.env` y el bloqueo es **normativo** (numeración
  española conforme), no de cuenta.
- «176 passed, 5 skipped».

### 🔴 `PLAN_VOZ_BIDIRECCIONAL.md` — 26/5
Superado por `PLAN_VOZ_CONVERSACIONAL.md`, que se declara «sucesor» — pero **este
documento no lleva ninguna nota de superación**. Se lee como plan vigente.

- Su recomendación (Opción A, integración nativa ElevenLabs↔Twilio) resultó **correcta en
  el fondo y equivocada en el mecanismo**: `VALIDACION_V1` documenta que el
  `<Connect><Stream>` hacia `wss://api.elevenlabs.io/v1/convai/conversation` **no
  funciona** (ElevenLabs CAI no habla el protocolo Twilio Media Streams en ese endpoint);
  la integración real es la API Outbound.
- Termina en una pregunta abierta al operador que se respondió hace dos meses.

### 🔴 `PLAN_VOZ_CONVERSACIONAL.md` — 26/5 · desmentido por los hechos
Es el sucesor, y su **topología recomendada B1a fue descartada por la realidad**.

- El plan §3.1 paso 5 especifica que *nosotros* colocamos la llamada en Twilio con
  `Record=true` y un TwiML con `<Say>` legal + `<Connect><Stream>`. Ese camino
  **se probó y falló** (`VALIDACION_V1`, intento `CA5e132c…`, 20 s).
- **Consecuencia sobre los requisitos no negociables:** el R1 («toda llamada se graba
  automáticamente, sin excepción — `Record=true` en el POST a Twilio») **no se cumple
  como está especificado**: la grabación la produce ElevenLabs, no Twilio, y el propio
  `VALIDACION_V1` lo reconoce en su nota final. El documento nunca se corrigió.
- El R5 (aviso legal literal por `<Say>` determinista, no LLM) se resolvió **por otra
  vía**: las 20 variantes de primer mensaje aprobadas el 3/7 + el gate de literalidad de
  `sustrato/gates.preflight_llamada`. El plan no lo refleja.
- Termina en «§15 Decisión que necesito ahora» con cuatro preguntas ya contestadas.
- **Qué hacer:** anteponer una nota que diga qué de este plan sigue en pie (los cinco
  requisitos R1-R5 como *intención*, el análisis de calidad post-call, la sección del
  reporte del viernes) y qué se descartó (la topología B1a completa).

### ⚪ `VALIDACION_V1_VOZ_BIDIRECCIONAL.md` — 27/5
Excelente registro histórico: la llamada real de 89 segundos con transcript completo. Es,
además, el documento que **desmiente al plan anterior** — y por eso importa conservarlo.

- **Próximos pasos caducados:** pide lanzar el *regulatory bundle* español en Twilio
  («1-3 días laborables»). Han pasado tres meses y `TWILIO_FROM_NUMBER` sigue siendo un
  `+1` estadounidense (auditoría B-11). El bloqueo actual, además, es más estricto de lo
  que el documento suponía: la **Orden TDF/149/2025** prohíbe numeración móvil como origen
  de llamadas comerciales.
- Sus dos bugs: el «aviso legal ablandado por el LLM» se resolvió por la vía de las 20
  variantes literales; el «el agente no cuelga solo» no consta resuelto en ningún sitio.

### 🟡 `DECISIONES_ARQUITECTONICAS.md` — 27/5 · **el hueco documental más grave**
Un log de ADRs es inmutable por diseño, así que los 7 existentes son correctos. El problema
es lo que **no** tiene.

- **Faltan las decisiones más consecuentes del proyecto**, todas posteriores a mayo:
  el sustrato canónico y su bus SQLite; los cubos y su `manifest.json`; el comité 3×3
  (¿por qué 9/9 y no mayoría?); los gates de autonomía CERO/BAJA/MEDIA/ALTA; el RUE y su
  catálogo cerrado de 91 eventos; el registro P9 en SQLite frente a `knowledge.json`; el
  candado del AI Act; la decisión de que `prometer_condiciones_precios` **no exista** como
  acción.
- **La decisión más importante de todas no está aquí**, sino en *docstrings* del código:
  la convivencia de tres generaciones (G1/G2/G3) con tres buses, tres colas de aprobación
  y cuatro contadores, aplazada a «decisión v1.1». El Dossier de hoy la cita literalmente
  desde `core/rue.py`, `core/aprobaciones.py` y `sustrato/bus.py`. **Una decisión
  arquitectónica de ese calibre documentada solo en comentarios de código es exactamente
  lo que este log existe para evitar.**
- **ADR-002 se ha quedado corto:** hablaba de *dos* máquinas de estados coexistiendo. Hoy
  son **tres** (`EstadoLead` de 9, `EstadoPipeline` de 12 y el registro P9 del sustrato con
  FRÍO/CONTACTADO/…/NO_LLAMAR), y la auditoría G-04 demostró que **daban garantías de
  opt-out distintas** — un problema de RGPD, no de estética.

### 🟡 `MODELO_DATOS_LEAD.md` — 27/5 (M1)
Vigente en lo esencial: `LeadDoc`, `from_dict` blando, subdocumentos, `metadatos_extra`.

- **Falta `robinson_ok`**, que hoy es un campo **crítico legal**: el pre-flight de voz lo
  exige explícitamente y `None` significa «no se llama» (Dossier §5 y §11, comprobación 7).
  Que no esté en el modelo de datos documentado es un fallo de peso.
- Falta también `argumento_id` en las interacciones, que es lo que alimenta el bucle P8.
- La deuda `Contacto.nombre_contacto` que anuncia sigue abierta (auditoría D-14).

### 🟡 `MAQUINA_ESTADOS_LEAD.md` — 27/5 (M2)
Uno de los mejores documentos del conjunto. La auditoría destaca este módulo como «limpio».

- **Le falta el aviso de la tercera máquina.** El documento explica por qué 12 estados y no
  9, pero no menciona que el sustrato tiene la suya. Sin ese aviso, la afirmación
  «`DO_NOT_CALL` es terminal duro» se lee como garantía del sistema, cuando hasta hoy el
  otro subsistema permitía sacar un lead de `NO_LLAMAR` con un flag y sin motivo (G-04,
  ya arreglado).

### 🟢 `POLITICA_REINTENTOS.md` — 27/5 (M3)
Vigente. El módulo que describe es, según la auditoría, de los mejor diseñados
(`decidir` no muta, `aplicar` sí; reloj y RNG inyectables).

- **Dos matices no documentados:** (a) las franjas horarias tienen **doble fuente de
  verdad** — este JSON y `pre_flight.py`, donde están *hardcodeadas* (auditoría D-03);
  (b) no hay calendario de festivos: el sistema llamaría un 15 de agosto.

### 🟢 `COMPROMISOS_DETECTOR.md` — 27/5 (M4)
Vigente. Sin discrepancias detectadas.

- Nota: `corpus_compromisos_c0_v1.json` (10/7) vive en esta carpeta y presumiblemente es
  el corpus de evaluación de este detector, pero **ningún documento lo explica**. Es el
  único fichero huérfano de `docs/`.

### 🟢 `BRIEFING.md` — 27/5 (M5)
Vigente. La deuda que él mismo registra (`nombre_contacto` en `metadatos_extra`) sigue
abierta.

### 🟡 `TODO.md` — 27/5
7 deudas del sistema nervioso. Sigue siendo útil, pero está a la vez **atrasado y
eclipsado**.

- **Atrasado:** su ítem «Integración runtime del SDR voz con sistema nervioso» se
  **entregó** el 28/5 como M8 (`SISTEMA_NERVIOSO_M8.md`). El TODO no lo tacha.
- **Eclipsado:** las otras 6 siguen abiertas y reaparecen en la auditoría de hoy con
  identificadores nuevos (D-12 TwilioClient duplicado, D-13 dos máquinas de estados, D-14
  `nombre_contacto`, D-05 rotación de backups). Ahora hay **dos listas de deuda que se
  solapan** (`TODO.md`, `DEUDA_TECNICA.md`) más una tercera que las supera
  (`AUDITORIA_2026-08-02.md`).

### 🟢 `CONSULTA_NATURAL.md` — 27/5 (M6)
Vigente. ADR-005 sigue siendo un invariante activo («no convertir el NLQ en text-to-SQL»,
Dossier §14 punto 10).

### 🟡 `DASHBOARD_DIRECTOR.md` — 27/5 (M7)
Correcto dentro de su alcance (el dashboard de consola con `rich`).

- **Ya no es «el panel»:** hoy hay al menos cuatro superficies distintas —
  `kaizen director` (+ `--html`), el `DashboardDirector` de M7, `api/server.py` (feed de
  eventos) y `panel_mando/` (Centro de Mando + Mesa del Jefe). El documento no dice que es
  uno de varios, y su sección «Lo que NO hace → no incluye dashboards web» quedó falsa: sí
  los hay, construidos por otra vía.

### 🔴 `SIGUIENTE_SESION.md` — 27/5 · **el más peligroso de la carpeta**
Por su nombre y su función, es el primer documento que se abre al empezar a trabajar. Y
lleva **dos meses caducado**, presentándose como si fuera de ayer.

- «Última actualización: 2026-05-27. **Próxima sesión prevista: 2026-05-28**».
- «**495 passed**» → real 916 · 1 failed.
- «Branch `master`, **en sync con `origin/master`**» → el repositorio estuvo **corrupto y
  sin remoto** (auditoría A-01: `fatal: bad object HEAD`, cero packfiles) hasta que se
  recuperó **hoy mismo**. Esa frase fue falsa durante semanas.
- «Crea `empresas/laboratorio/perfil.json` (**no existe aún**)» → existe.
- «**Decisión a tomar hoy**: ¿reanudamos voz y conectamos M8?» → se conectó el 28/5.
- Su §5 «Deuda registrada» ha sido superada por 51 hallazgos.
- La auditoría lo señala explícitamente en **E-09**.

> ⚠️ **Consecuencia práctica:** existe una nota de memoria que recomienda *«al abrir sesión
> nueva en KAIZEN, leer `docs/SIGUIENTE_SESION.md` primero»*. **Ese consejo ya no sirve.**
> El punto de entrada correcto hoy es `docs/DOSSIER_FUNCIONAMIENTO_INTERNO.md` (qué es el
> sistema) + `docs/AUDITORIA_2026-08-02.md` (qué está roto). Conviene actualizar la nota.

### 🟢 `SISTEMA_NERVIOSO_M8.md` — 28/5
Vigente y preciso.

- **Salvedad crítica que no lleva:** su «próximo paso 1» (un endpoint HTTP que reciba el
  webhook real de ElevenLabs y llame a `procesar_transcript_post_llamada`) **existe** en
  `api/server.py`, pero con **las dos firmas de webhook mal implementadas**: la de
  ElevenLabs no usa el formato `t=…,v0=…` sobre `{timestamp}.{body}` (auditoría B-07) y la
  de Twilio se rompe detrás de proxy/ngrok (B-08). La auditoría marca ambas como
  «bloquea M8». Es decir: **M8 está construido y probado, pero el ciclo post-llamada real
  no cierra**, y este documento no lo advierte.

### 🟢 `SISTEMA_NERVIOSO.md` — 28/5
El mejor documento fundacional del repo. La auditoría lo respalda: *«el sistema nervioso
es la pieza mejor diseñada del repo»*.

- Único desfase: «507 passed» y el diagrama termina en M8. No menciona el sustrato ni los
  cubos, que llegaron después y son la capa que hoy gobierna las acciones irreversibles.

### 🟢 `ARGUMENTARIO_LABORATORIO.md` — 28/5
Vigente y bien integrado: el `BrandGuardian` lo carga y bloquea por substring antes del LLM.

- Su última línea anuncia **M9** (inyectar los argumentos validados como
  `dynamic_variables` del agente de voz). **Sigue sin hacerse**, y no aparece en ninguna
  otra lista de pendientes. Es el único sitio del repo donde M9 existe.
- Los precios de competencia son de mayo de 2026 y son de uso interno; conviene fecharlos
  como tales para que nadie los tome por vigentes dentro de un año.

### 🟡 `MANUAL_KAIZEN.md` — 3/7 · el mejor punto de entrada para el operador
Es el documento más legible del conjunto y el único escrito en lenguaje llano. Su §12
contiene **el plan realmente vigente** (S1-S8 hasta el 30 de agosto), que no está en
`ROADMAP_KAIZEN.md`.

Desfases, todos por el mes transcurrido:

- «**669 pruebas en verde**» → 916 · 1 en rojo.
- «El límite está en 14,72 €» → cierto en el `.env`, pero la auditoría **B-02** descubrió
  que ese valor **no lo leía quien gasta el dinero** (`claude_client` y `Guardian` tenían
  16 € *hardcodeados*). Arreglado hoy. El manual describía una garantía que no existía.
- «El comité vota 9 de 9» → correcto, pero hasta hoy era **vulnerable a inyección de
  prompt** a través del nombre de un lead (G-02, arreglado). Y su candado de primer
  mensaje se burlaba con cualquier subcadena del fichero (G-03, arreglado).
- «**HITO DURO AIACT-GATE 2026-08-02**» → **es hoy, y ha cerrado el canal de email en
  duro** (F-01). No hay texto de transparencia aprobado para email; las 20 variantes son
  de voz. El manual no puede saberlo, pero cualquiera que lo lea mañana necesitará saberlo.
- §6 «Dar de alta un cliente nuevo»: su advertencia («el multi-cliente en una sola
  instalación existe a medias; no lo uses para dos clientes de pago») **sigue vigente** y
  es de las cosas más valiosas del documento.

### 🟡 `GUION_VENTA_5_MIN.md` — 4/7
Guión comercial de 5 minutos. Sigue siendo utilizable, con **un riesgo operativo nuevo que
no refleja**.

- El MIN 3 propone ejecutar `RITUAL DE LA MAÑANA.cmd` **en vivo delante del cliente**, que
  compone emails reales. Desde hoy el candado del AI Act hace fallar el envío
  (`AIActSinTransparencia`) y podría hacer fallar la demo según dónde corte el ritual.
- Su regla previa (R4: «en la demo NO se envía nada a nadie») y su plan de contingencia
  («si algo falla, abre `panel/director.html`, nunca depures delante del cliente») siguen
  siendo buenos. **Recomendación: hasta que F-01 se resuelva, usar la foto estática.**
- «Comprueba saldo OpenRouter (>2 $)» — verificar antes de cada demo, no es dato fijo.

### ⚪ `corpus_compromisos_c0_v1.json` — 10/7
Dataset, no documento. **Huérfano**: ningún `.md` de `docs/` explica qué es, cómo se
generó, contra qué se evalúa ni quién lo consume. Presumiblemente alimenta la evaluación
del detector M4.

### 🟢 `AUDITORIA_2026-08-02.md` — hoy
**Lista vigente de lo que está roto.** 51 hallazgos, con distinción explícita entre
arreglados y pendientes, y con reproducciones antes de tocar nada. Es el documento que
convierte a casi todos los anteriores en históricos.

### 🟢 `DOSSIER_FUNCIONAMIENTO_INTERNO.md` — hoy
**Descripción vigente de cómo funciona el sistema.** Debe sustituir a `ARQUITECTURA.md`
como punto de entrada técnico. Su §14 (invariantes) es lo más parecido que hay a un
contrato de lo que no se puede romper.

---

## 3. Los seis huecos: lo que no está documentado en ninguna parte de `docs/`

No es que esté desactualizado — es que **no existe**:

| # | Hueco | Dónde vive hoy la información |
|---|---|---|
| 1 | **El sustrato canónico y los cubos** (G3): bus SQLite, `manifest.json`, registro P9 | `KAIZEN_ARQUITECTURA_CANONICA_v1_0.md` y `KAIZEN_D00…D10` en la **raíz**; `conceptos/SUSTRATO.md`, `conceptos/CUBOS.md` |
| 2 | **Los gates de autonomía y el comité 3×3** — lo que hoy decide si algo sale al mundo | `conceptos/COMITE_3X3.md`, `sustrato/gates.py`, §8 del Dossier |
| 3 | **La plataforma multi-tenant G2**: RUE, pánico (PARAR TODO), techos, ledger, Centro de Mando | `KAIZEN_D10_CENTRO_DE_MANDO_v0_2.md`, `conceptos/CENTRO_DE_MANDO.md`, `AUDITORIA_D00.md` |
| 4 | **El candado del AI Act** y el régimen de transparencia | `conceptos/AIACT_GATE.md`, `cubos/comercial/aiact_primeros_mensajes.md`, F-01 de la auditoría |
| 5 | **El bucle P8** (argumentario que aprende de los resultados) | `cubos/comercial/p8_bucle.py`, §10 del Dossier. Documentado en código, no en prosa. |
| 6 | **La decisión de convivir con tres generaciones** y su plan de unificación | *Docstrings* de `core/rue.py`, `core/aprobaciones.py`, `sustrato/bus.py`. Debería ser un ADR. |

---

## 4. Qué hacer, en orden

Cinco acciones, de mayor a menor rentabilidad. Ninguna requiere tocar código.

**1 · Poner una cabecera de estado en los cinco documentos engañosos.** Dos líneas cada
uno, con fecha y a dónde ir en su lugar:
`SIGUIENTE_SESION.md`, `ARQUITECTURA.md`, `ROADMAP_KAIZEN.md`, `PLAN_VOZ_CONVERSACIONAL.md`,
`PLAN_VOZ_BIDIRECCIONAL.md`. Es media hora y elimina el 80 % del daño.

**2 · Renombrar o vaciar `SIGUIENTE_SESION.md`.** Un fichero que se llama «siguiente
sesión» y describe el 28 de mayo miente por su título aunque nadie lo lea. O se regenera al
final de cada sesión, o se archiva como `SESION_2026-05-27.md`.

**3 · Escribir los ADR que faltan** (huecos 1, 2 y 6 de la tabla anterior). Son decisiones
ya tomadas: solo hay que registrarlas. El ADR de la convivencia G1/G2/G3 es el más urgente,
porque de él cuelga la «decisión v1.1» que nadie ha tomado todavía.

**4 · Unificar las tres listas de deuda.** `TODO.md` + `DEUDA_TECNICA.md` +
`AUDITORIA_2026-08-02.md` se solapan. Dejar la auditoría como lista viva y convertir las
otras dos en histórico con nota de reenvío.

**5 · Decidir qué es `ROADMAP_KAIZEN.md`.** Su propia regla de gobernanza 7 obliga a
rehacerlo formalmente o declararlo inadecuado. El plan real hoy es el S1-S8 del
`MANUAL_KAIZEN.md` §12, que vence el 30 de agosto y que nadie ha revisado desde el 3 de
julio — con el AI Act ya encima.

---

## 5. Tabla resumen

| # | Documento | Creado | Estado | Lo que más urge corregir |
|---:|---|---|:---:|---|
| 1 | `VALIDACION_E2E_REAL.md` | 24/5 | 🔴 | Plantilla vacía desde hace 3 meses; su criterio ya no aplica |
| 2 | `FINANZAS_SCHEMA.md` | 24/5 | 🟡 | Omite los 4 contadores de gasto reales |
| 3 | `COMO_CREAR_UN_DEPARTAMENTO.md` | 24/5 | 🟡 | La unidad hoy es el **cubo** con `manifest.json` |
| 4 | `CASOS_DE_USO.md` | 24/5 | 🔴 | Sigue sin publicarse; Fase 0.2 nunca se cerró |
| 5 | `DESARROLLO_RRHH_POSPONER.md` | 25/5 | 🟡 | Inventario de departamentos obsoleto (hoy 10 cubos) |
| 6 | `ROADMAP_KAIZEN.md` | 25/5 | 🔴 | **Ningún tag `v0.x` existe.** Ninguna fase se cerró jamás |
| 7 | `ARQUITECTURA.md` | 25/5 | 🔴 | Se dice «fuente única de verdad»; ignora 2/3 del sistema |
| 8 | `PLAN_PRODUCCION.md` | 25/5 | ⚪ | Correcto. Su sucesor también está muerto |
| 9 | `DEUDA_TECNICA.md` | 25/5 | 🟡 | Superado por la auditoría de hoy (51 hallazgos) |
| 10 | `PLAN_DEPARTAMENTO_COMERCIAL.md` | 26/5 | 🟡 | Fase 1 hoy bloqueada por AI Act + numeración ES |
| 11 | `REPORTE_FASE0_…1257.md` | 26/5 | ⚪ | Duplicado con el de las 13:26; cifras distintas |
| 12 | `VALIDACION_FASE0_COMERCIAL.md` | 26/5 | ⚪ | «Lo que sigue» caducado |
| 13 | `REPORTE_FASE0_…1326.md` | 26/5 | ⚪ | Ídem #11 |
| 14 | `PLAN_VOZ_BIDIRECCIONAL.md` | 26/5 | 🔴 | Superado y **sin nota de superación** |
| 15 | `PLAN_VOZ_CONVERSACIONAL.md` | 26/5 | 🔴 | Su topología B1a **falló en la práctica**; R1 no se cumple |
| 16 | `VALIDACION_V1_VOZ_BIDIRECCIONAL.md` | 27/5 | ⚪ | Próximos pasos caducados (bundle ES → Orden TDF/149/2025) |
| 17 | `DECISIONES_ARQUITECTONICAS.md` | 27/5 | 🟡 | **Faltan los ADR de todo lo posterior a mayo** |
| 18 | `MODELO_DATOS_LEAD.md` | 27/5 | 🟡 | Falta `robinson_ok` (campo crítico legal) |
| 19 | `MAQUINA_ESTADOS_LEAD.md` | 27/5 | 🟡 | No avisa de la **tercera** máquina de estados |
| 20 | `POLITICA_REINTENTOS.md` | 27/5 | 🟢 | Doble fuente de franjas horarias; sin festivos |
| 21 | `COMPROMISOS_DETECTOR.md` | 27/5 | 🟢 | — |
| 22 | `BRIEFING.md` | 27/5 | 🟢 | — |
| 23 | `TODO.md` | 27/5 | 🟡 | No tacha M8 (entregado); solapado con otras 2 listas |
| 24 | `CONSULTA_NATURAL.md` | 27/5 | 🟢 | — |
| 25 | `DASHBOARD_DIRECTOR.md` | 27/5 | 🟡 | Hoy hay 4 paneles, no 1 |
| 26 | `SIGUIENTE_SESION.md` | 27/5 | 🔴 | **El más engañoso.** «Próxima sesión: 28/5». E-09 |
| 27 | `SISTEMA_NERVIOSO_M8.md` | 28/5 | 🟢 | No avisa de que las firmas de webhook están rotas (B-07/B-08) |
| 28 | `SISTEMA_NERVIOSO.md` | 28/5 | 🟢 | Solo el conteo de tests |
| 29 | `ARGUMENTARIO_LABORATORIO.md` | 28/5 | 🟢 | M9 anunciado aquí y en ningún otro sitio |
| 30 | `MANUAL_KAIZEN.md` | 3/7 | 🟡 | Contiene el plan real (S1-S8); vence el 30/8 |
| 31 | `GUION_VENTA_5_MIN.md` | 4/7 | 🟡 | Demo en vivo con el canal email cerrado desde hoy |
| 32 | `corpus_compromisos_c0_v1.json` | 10/7 | ⚪ | Huérfano: sin documento que lo explique |
| 33 | `AUDITORIA_2026-08-02.md` | 2/8 | 🟢 | **Lista vigente de lo roto** |
| 34 | `DOSSIER_FUNCIONAMIENTO_INTERNO.md` | 2/8 | 🟢 | **Descripción vigente del sistema** |

**Recuento:** 🟢 9 · 🟡 12 · 🔴 7 · ⚪ 6.
De los 34, **19 (56 %) necesitan intervención**; 7 de ellos son activamente engañosos.

---

*Dossier redactado el 2026-08-02 leyendo los 33 documentos en orden de creación y
contrastándolos con el código, el árbol de ficheros y `git tag`. Donde hay incertidumbre,
se dice. Si algo aquí contradice al código, gana el código.*

---
Relacionados: [[MAPA_CONCEPTUAL_DOCS]] · [[DOSSIER_FUNCIONAMIENTO_INTERNO]] · [[AUDITORIA_2026-08-02]]
