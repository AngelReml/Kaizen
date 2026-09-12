# KAIZEN-D07 — DEPARTAMENTO INTELIGENCIA DE MERCADO
## Serie de dossieres departamentales KAIZEN · Documento 07

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `inteligencia.*` (payloads en Anexo A).
**Entrada:** P8 de todos los cubos (D01, D03, D04, D05, D06) + bitácora de eventos (D00).
**Consumidor clave:** D01 (Comercial: ajuste de cadencias, targeting), D06 (Marketing: priorización de segmentos), D05 (Operaciones: modelo de capacidad).
**Diferencia estratégica:** es el cubo **más opcional**. Todo funciona sin él; funciona mejor con él. Su ausencia es degradación elegante, nunca bloqueo.
**Estado real:** cero líneas de código. Greenfield puro. La materia prima (eventos P8) será generada por otros cubos en sus bloques; D07 es quien la procesa.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorridos E2E (análisis de patrón, detección, reporte)
- §2 — Anatomía del trabajo de inteligencia que replica (por qué es productor, no decisor)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados: análisis, alerta, reporte
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo
- §10 — Kit de despliegue y superficie del operador
- §11 — Estado real vs. dossier: greenfield con promesa de degradación elegante
- §12 — Programa de construcción a v1.0: bloques D7
- §13 — Batería de pruebas duras
- §14 — Prueba de vida real pre-registrada (VR-D07-01)
- §15 — Riesgos de segundo orden
- §16 — Puerta v1.0: checklist DoD y falsación
- Anexo A — Esquemas de payload `inteligencia.*` v1

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan. Índice: plantilla D01.

### §0.2 Qué diferencia a D07 de todos los demás
- No tiene cliente directo (cliente de D07 es el operador de Kaizen que quiere entender qué pasa).
- No tiene ROI propio (su valor es qué mejora en otros cubos al usarlo).
- No emite eventos que cierren el ciclo de un pedido (es puro análisis).
- **Su ausencia no rompe nada**: sin D07, Comercial sigue vendiendo, Operaciones sigue produciendo. Con D07, venden mejor y producen más eficiente.

Esto es **degradación elegante por diseño**, no accidente.

---

## §1 — MISIÓN, FRONTERA Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Inteligencia convierte hechos dispersos (eventos, P8, bitácora) en patrones visibles, alertas sobre anomalías y recomendaciones estructuradas. **No decide; propone. No ejecuta; informa.**

### §1.2 Qué NO es — FIJADO
- **No es forecasting mágico.** Trabaja con datos históricos y patrones; no adivina el futuro.
- **No es asesoramiento estratégico.** No dice "deberías hacer X"; dice "cuando hacemos X, esto es lo que típicamente pasa".
- **No es alertas obsesivas.** Detecta anomalías reales, no ruido (falsos positivos destrozan la confianza).
- **No automatizan decisiones.** Todas sus propuestas son para que el operador decida.

### §1.3 Recorrido A — LOS PASOS del análisis de patrón

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| A1 | Definición de patrón: "¿cuál es la tasa de conversión típica por segmento?" | Operador | Operador | — | — |
| A2 | Agregación de datos: recopilar P8 del período (pedidos, contactos, conversiones) | Sistema | — | datos disociados (sin nombre de cliente) | — |
| A3 | Cálculo de patrón: conversión por segmento, días-a-cierre, tasa de churn, costo-de-adquisición | Sistema | — | cálculos reproducibles | `inteligencia.patron.calculado` |
| A4 | Comparación histórica: ¿cambió vs. mes anterior? ¿está dentro de rango esperado? | Sistema | — | desviación con umbral pre-registrado | `inteligencia.patron.desviacion` (si supera umbral) |
| A5 | Generación de reporte: gráficos, tablas, insights en lenguaje natural | Sistema | — | comprensible al operador (no jerga) | `inteligencia.reporte.generado` |
| A6 | Distribución: operador ve reporte en panel o recibe por email | Sistema | — | — | — |

### §1.4 Recorrido B — LOS PASOS de la detección de anomalía

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| B1 | Definición de alerta: "conversión < 5% o > 15% es anómalo", "dias-a-cierre > 60 es problema" | Operador | Operador (con sugerencia de sistema) | umbrales pre-registrados | — |
| B2 | Monitoreo en vivo: cada nuevo P8 entra → comparar con rangos | Sistema | — | — | — |
| B3 | Si supera umbral: clasificar (crítica, advertencia, info) | Sistema | — | umbrales ordenados | `inteligencia.alerta.emitida` |
| B4 | Notificación al operador | Sistema | — | canal según urgencia (email/SMS/panel rojo) | — |
| B5 | Contexto de la alerta: "esto pasó porque X está ocurriendo en este segmento" | Sistema propone | — | análisis causal (correlación documentada) | — |
| B6 | Propuesta de acción: "si esto se debe a Y, intenta Z" | Sistema propone | Operador decide si actuar | — | — |

### §1.5 Recorrido C — LOS PASOS del reporte de tendencia

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| C1 | Período de análisis: últimas 4 semanas, mes, trimestre | Operador | Operador | — | — |
| C2 | Selección de métricas: conversión, churn, velocidad, satisfacción, etc. | Operador o Sistema (default) | — | métricas del corpus P8 | — |
| C3 | Agregación temporal: tendencia mes-a-mes, semana-a-semana | Sistema | — | datos ordenados por tiempo | — |
| C4 | Visualización: gráficos de tendencia con línea esperada (baseline) | Sistema | — | legible (no spaghetti charts) | `inteligencia.tendencia.graficada` |
| C5 | Análisis de velocidad: ¿acelerando o ralentizando? Inflexión detectada | Sistema | — | matemática de derivada | `inteligencia.inflexion.detectada` |
| C6 | Reporte ejecutivo: "esto subió/bajó X%, aquí está por qué" | Sistema | — | conexión causal documentada | `inteligencia.reporte.ejecutivo` |

---

## §2 — ANATOMÍA DEL TRABAJO DE INTELIGENCIA QUE REPLICA

### §2.1 Descomposición

| Función humana | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|
| Analista de datos | "Miro estos números, veo que esto cambió, te aviso" | Detector de anomalía + calculador de patrón |
| El dueño pensando | "En nuestro sector, 10% conversión es bueno; 5% es preocupante" | Definidor de umbrales (input humano) + monitor |
| Reportero de negocio | "Te muestro un dashboard de lo que pasó este mes" | Generador de reporte + visualización |
| Investigador de causa | "Esto bajó porque Y empezó a ocurrir aquí" | Correlacionador de eventos + análisis causal |

### §2.2 El reparto FIJADO
- **Del cubo:** agregación de P8, cálculo de patrones, detección de anomalías, generación de reportes.
- **Del operador:** definición de qué es normal/anómalo (umbrales), decisión de qué hacer con alertas, interpretación del "por qué".
- **De otros cubos:** generación honesta de P8 (sin sesgo, datos reales).

**Regla de oro (FIJADO):** D07 **jamás decide nada por el operador**. Propone; el operador ejecuta. El día que D07 cree que "esta alerta es crítica, pausa la campaña automáticamente", ha fallado.

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

### §3.1 Agregador de P8 — **P·D7.0**
- **Misión:** que los datos dispersos estén juntos y disociados.
- **E→P→S:** P8 de D01 (conversión por segmento), D03 (churn), D04 (días-a-cobro), D05 (duración vs. plan), D06 (ROI de campaña) → consolidación en almacén temporal (periodo) → disociación (sin identificación de cliente) → listo para análisis.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (agregación, no decisión). **Verificación:** integridad de datos (todos los P8 llegaron).
- **Estado:** cero líneas; es middleware.

### §3.2 Calculador de patrón — **P·D7.1**
- **Misión:** que los patrones repetibles sean visibles (no intuición).
- **E→P→S:** agregado de P8 → consulta de pregunta (conversión por segmento, churn por vertical, velocidad de cierre) → cálculo de métrica (promedio, percentil, desviación) → resultado reproducible.
- **Clase:** TRIVIAL (determinista: suma/promedio/std). **Autonomía:** REVERSIBLE (cálculo). **Verificación:** reproducibilidad (mismos datos → mismo resultado).
- **Estado:** cero líneas; es análisis estadístico básico.

### §3.3 Detector de anomalía — **P·D7.1**
- **Misión:** alertar cuando algo se rompe sin que el operador tenga que mirarlo todo.
- **E→P→S:** P8 nuevo entra → comparar contra patrón histórico + umbral pre-registrado → si supera, clasificar (CRITICA, ADVERTENCIA, INFO) → emitir evento + notificación.
- **Clase:** ESTANDAR. **Autonomía:** REVERSIBLE (detección; no acción). **Verificación:** test de false positives (umbral bien calibrado).
- **Estado:** cero líneas; es sistema de alertas.

### §3.4 Correlacionador causal — **P·D7.2**
- **Misión:** cuando X cae, ¿es porque Y pasó? Documentar la correlación.
- **E→P→S:** alerta de anomalía + búsqueda de eventos contemporáneos (en bitácora) → coincidencia de tiempo → propuesta de causa ("conversión bajó el día que pausamos campaña X") → confianza de correlación.
- **Clase:** ESTANDAR (análisis de series temporales). **Autonomía:** propone; operador valida. **Verificación:** correlación documentada (no causalidad; eso es interpretación humana).
- **Estado:** cero líneas; es análisis de coincidencia temporal.

### §3.5 Generador de reporte — **P·D7.2**
- **Misión:** que lo que pasó sea contable.
- **E→P→S:** período + selección de métricas → agregación temporal → gráficos (tendencia, comparativa) → narrativa (resumen de cambios) → reporte ejecutivo.
- **Clase:** TRIVIAL (visualización + texto). **Autonomía:** REVERSIBLE (generación). **Verificación:** legibilidad (no spaghetti charts).
- **Estado:** cero líneas; es visualización y redacción.

### §3.6 Definidor de umbral — **P·D7.0** (interfaz, no rol IA)
- **Misión:** que el operador diga qué es normal en su contexto.
- **E→P→S:** operador en panel: "conversión normal es 8–12%; fuera de esto es alerta" → sistema persiste → detector lo usa.
- **Clase:** REVERSIBLE. **Autonomía:** operador define. **Verificación:** —.
- **Estado:** es interfaz en el panel de D07.

---

## §4 — MÁQUINA DE ESTADOS: ANÁLISIS, ALERTA, REPORTE

### §4.1 Análisis — FIJADO

```
SOLICITADO → EN_PROCESO → COMPLETADO
              ↓ fallo de datos
           ERROR (reintentar o manual)
```

| Estado | Significado | Quién entra | Quién sale |
|---|---|---|---|
| SOLICITADO | Operador pidió análisis | Operador | Sistema (EN_PROCESO) |
| EN_PROCESO | Agregando datos, calculando | Sistema | COMPLETADO o ERROR |
| COMPLETADO | Resultado disponible | Sistema | histórico |
| ERROR | Falta de datos o cálculo falló | Sistema | operador intenta de nuevo o escalación |

### §4.2 Alerta — FIJADO

```
EMITIDA → RECONOCIDA → RESUELTA
   ↓ false positive
DESCARTADA
```

| Estado | Significado | Quién entra | Quién sale |
|---|---|---|---|
| EMITIDA | Anomalía detectada; notificación al operador | Sistema | Operador (RECONOCIDA o DESCARTADA) |
| RECONOCIDA | Operador vio y confirmó que es real | Operador | Operador actúa (RESUELTA) |
| DESCARTADA | Falsa alarma; operador marca como ruido | Operador | histórico; retroalimentación al detector |
| RESUELTA | Operador tomó acción; anomalía se corrigió | Operador | histórico; medición de efecto |

### §4.3 Notación de confidencia — FIJADO
Toda propuesta de correlación lleva confianza: {ALTA, MEDIA, BAJA}. "Conversión bajó el día que X; confianza MEDIA" = se documentó la coincidencia, pero no es prueba.

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `inteligencia.patron.calculado` | 1 | A.1 | bajo demanda o diario | no | reproducibilidad | — | TRIVIAL |
| `inteligencia.patron.desviacion` | 1 | A.2 | si supera umbral | **sí** (para alertas) | supera umbral pre-registrado | — | TRIVIAL |
| `inteligencia.alerta.emitida` | 1 | A.3 | por anomalía detectada | **sí** (notificación al operador) | clasificación crítica/adv/info | — | TRIVIAL |
| `inteligencia.correlacion.propuesta` | 1 | A.4 | análisis post-alerta | no | confianza documentada | — | ESTANDAR |
| `inteligencia.reporte.generado` | 1 | A.5 | bajo demanda o periódico | no | visualización legible | — | TRIVIAL |
| `inteligencia.tendencia.graficada` | 1 | A.6 | bajo demanda | no | matemática verificable | — | TRIVIAL |
| `inteligencia.reporte.ejecutivo` | 1 | A.7 | semanal/mensual (default) | no | narrativa clara | — | TRIVIAL |
| `inteligencia.umbral.definido` | 1 | A.8 | cuando operador ajusta | **sí** (consumida por detector) | rango válido | — | TRIVIAL |

### §5.B — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente |
|---|---|---|
| P8 de D01, D03, D04, D05, D06 | Sí (es materia prima) | sin P8, no hay análisis → D07 queda inactivo (degradación elegante) |
| Bitácora de eventos D00 §3.4 | No (para análisis causal) | sin ella, análisis menos profundo; alertas menos contextuadas |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado |
|---|---|---|
| `inteligencia.consulta_patron(tenant, metrica, periodo)` | → {valor, promedio_historico, desviacion, tendencia} | lectura pura |
| `inteligencia.generar_reporte(tenant, metricas[], periodo)` | → PDF/HTML con gráficos y narrativa | reportes demanda; no recurrentes sin programación |

### §5.D–F — véase §6, §8, §10

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

**FIJADO:** D07 no tiene autonomía de acción (es puro análisis). La matriz es trivial porque todo el cubo es REVERSIBLE.

| Acción | Clase | CERO | BAJA | MEDIA | ALTA |
|---|---|---|---|---|---|
| Definir umbral de alerta | REVERSIBLE | propone | operador define | operador define | operador define |
| Detectar anomalía | TRIVIAL | automático | automático | automático | automático |
| Emitir alerta | TRIVIAL | automático | automático | automático | automático |
| Proponer acción | — | no aplica | propone (operador actúa) | propone | propone |

**Sellado en diseño:** D07 jamás ejecuta nada derivado de sus análisis. Es informe, no comando.

---

## §7 — CUMPLIMIENTO INTEGRADO: REGLA → CONTROL → TEST

| # | Regla | Control | Test |
|---|---|---|---|
| 1 | P8 es disociado (no identifica cliente) | en agregación, eliminar identificadores | `test_p8_disociado` |
| 2 | Patrón es reproducible (mismos datos → mismo resultado) | cálculo determinista (sum/avg/std) | `test_patron_reproducible` |
| 3 | Alerta tiene confianza documentada | evento alerta contiene {clasificacion, confianza, razon} | `test_alerta_documentada` |
| 4 | Correlación no es causalidad (no pretender certeza) | campo confianza ∈ {ALTA, MEDIA, BAJA}; narrativa clara | `test_correlacion_honesta` |
| 5 | Umbral es versionado (cambios rastreables) | cada cambio emite evento + timestamp | `test_umbral_versionado` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Patrones, anomalías, reportes, umbrales son **la inteligencia acumulada** (P9). Pérdida = volver a punto cero; es pérdida de memoria.

### §8.2 Señal recursiva (D07 produce P8 para sí mismo) — FIJADO
Por cada reporte y cada acción tomada derivada de D07:

```
(tenant, tipo_accion_tomada: AJUSTE_CAMPAÑA|CAMBIO_UMBRAL|INVESTIGACION, efecto_medible?, ts)
```

Ajusta: meta-aprendizaje (qué tipos de alertas resultan en cambios útiles vs. ruido).

### §8.3 Entidades y propiedad
Umbrales, patrones, reportes históricos → DATO_CLIENTE (exportable). Modelos de baseline, templates de reporte → DATO_PLATAFORMA. Señales P8 agregadas disociadas → DATO_AGREGADO (comparten base con otros).

---

## §9 — ECONOMÍA DEL CUBO

### §9.1 Coste marginal — ABIERTO (lo cierra VR-D07-01)
D07 es agregación y análisis (sustrato + CPU). Sin cliente directo, es overhead. Margen: mejora en otros cubos que lo usan (menos tiempo de decisión del operador, mejor targeting de Comercial, mejor optimización de Operaciones). Es **inversión en eficiencia**, no ingreso directo.

### §9.2 Ventaja de permuta (P8 recursivo)
Datos de qué alertas resultan en cambios útiles → modelo de "valor de alerta" que optimiza futura generación de reportes. Es meta-mejora.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DEL OPERADOR

### §10.1 Kit
1. **Métricas base:** conversión, churn, velocidad, satisfacción, ROI (del corpus P8 de otros cubos).
2. **Umbrales iniciales:** valores por defecto por vertical (ej. HORECA: conversión 8–12%, churn < 2%).
3. **Canales de notificación:** email/SMS/panel según urgencia.
4. **Integración con otros cubos:** acceso a P8 en tiempo real.
5. **Smoke test:** análisis ficticio, alerta simulada, reporte generado.

### §10.2 Superficie del operador — FIJADO
- **Dashboard de alertas:** activas, reconocidas, descartadas; clasificación y confianza.
- **Patrón explorer:** consultar conversión/churn/etc. por periodo.
- **Reportes históricos:** biblioteca de reportes generados (semanales/mensuales).
- **Definidor de umbral:** UI para cambiar qué es normal (con validación).
- **Correlación viewer:** cuando hay alerta, mostrar eventos contemporáneos (¿qué pasó ese día?).
- **No es:** predicciones (D07 no predice); instrucciones de acción automática (D07 no ejecuta).

---

## §11 — ESTADO REAL VS. DOSSIER: GREENFIELD CON PROMESA

| Item | Estado | Notas |
|---|---|---|
| Código de D07 | No existe | Greenfield puro |
| Materia prima (P8 de otros cubos) | Será generada por sus bloques | D07 no puede empezar hasta que D01, D03, D04, D05, D06 generen P8 |
| Arquitectura de agregación | No existe | D7.0 la implementa |
| Análisis estadístico básico | No existe | D7.1 lo implementa |
| Alertas y correlación | No existe | D7.1 y D7.2 lo implementan |
| Reportes | No existe | D7.2 lo implementa |

**Honestidad sobre dependencia:** D07 no puede empezar en serio hasta que **mínimo D01 + D05 estén en producción** (generando P8). Puede probarse con datos sintéticos en Bloque D7.0, pero vida real requiere que otros cubos hayan cruzado sus puertas.

**Promesa de degradación elegante:** cuando D07 no existe o falla, **nada se rompe**. Comercial sigue vendiendo, Operaciones sigue produciendo. Con D07, venden/producen mejor porque ven los patrones. Sin él, trabajan a ciegas, pero funciona.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES D7

Orden por dependencia: D7.0 (agregación) → D7.1 (patrones + anomalías) → D7.2 (causalidad + reportes). **Bloqueante:** mínimo D01 ✓ + D05 ✓ generando P8. Requiere D00-B1 ✓. Ciclo D00 §0.6; commit por bloque.

### D7.0 — Agregación de P8 e interfaz de umbral
1. Consolidación de P8 de D01/D03/D04/D05/D06 en almacén temporal.
2. Disociación (eliminación de identificadores de cliente).
3. Panel para definir umbrales por métrica (conversión, churn, etc.).
4. Validación de rango de umbral (p. ej. conversión 0–100%).
5. Persistencia de umbrales versionados.
6. **Puerta D7.0:** ≥50 filas de P8 agregado y limpio + ≥3 umbrales definidos + histórico de cambios de umbral visible.

### D7.1 — Patrones + anomalías
1. Calculador de patrón (promedio, percentil, desviación de P8).
2. Detector de anomalía (comparar cada nuevo P8 contra patrón + umbral).
3. Clasificador de alerta (CRITICA si > 3 desv; ADVERTENCIA si > 1.5 desv; INFO si notable).
4. Notificador (email/SMS/panel según urgencia).
5. Interfaz de reconocimiento/descarte de alerta (retroalimentación).
6. **Puerta D7.1:** ≥5 análisis completados reproduciblemente + ≥3 alertas emitidas y reconocidas por operador + false positive rate < 20%.

### D7.2 — Causalidad + reportes
1. Correlacionador: cuando alerta, buscar eventos en bitácora D00 en ventana temporal.
2. Propuesta de causa: "conversión bajó el día que X; confianza MEDIA".
3. Generador de reporte: gráficos (tendencia, comparativa) + narrativa.
4. Exportador de reporte (PDF, HTML, CSV).
5. **Puerta D7.2:** ≥2 reportes generados legibles + ≥1 alerta con correlación propuesta + operador validó causalidad como correcta o incorrecta (retroalimentación).

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de tenant** | 2 tenants con P8 distintos | análisis A no contamina B |
| 13.2 | **Reproducibilidad de patrón** | Mismo P8, 3 cálculos de conversión % | 3/3 idénticos |
| 13.3 | **Alerta clasificación correcta** | P8 con conversión 2% (umbral 8–12%); clasificación | CRITICA (fuera >2desv) |
| 13.4 | **False positive rate aceptable** | 100 alertas en periodo real; operador valida | <20% descartadas como falsas |
| 13.5 | **Umbral versionado** | Cambio de umbral; consultar versión vieja | versión antigua disponible con timestamp |
| 13.6 | **Correlación documentada** | Alerta + búsqueda de eventos en ventana temporal | propuesta con confianza (no certeza) |
| 13.7 | **Reporte legible** | Generador de reporte de 4 semanas | gráficos sin spaghetti, narrativa clara |
| 13.8 | **P8 disociado** | Verificación de P8 agregado | ningún nombre cliente, identificador específico |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D07-01

Pre-registro conforme a D00 Anexo II:
- **Tenant:** `laboratorio` (con ≥2 meses de P8 reales de D01/D05) · **Ventana:** 2 semanas de operación de D07 · **Acciones:** ≥3 análisis, ≥3 alertas, ≥1 reporte.
- **Métricas y umbrales (binarios):**
  1. ≥50 filas de P8 disociadas y limpias (disponibles en almacén).
  2. ≥3 umbrales definidos por operador (p. ej. conversión 8–12%, churn <2%, dias-cierre <45).
  3. ≥3 alertas emitidas y clasificadas correctamente (severidad alineada con desviación).
  4. False positive rate en alertas ≤ 20% (operador valida).
  5. ≥1 correlación propuesta entre alerta y evento en bitácora (documentada, confianza < 100%).
  6. ≥1 reporte generado legible con gráficos y narrativa.
  7. Operador reconoce/descarta alertas (retroalimentación).
- **Fallo total:** patrón no reproducible, alerta mal clasificada, P8 no disociado, reporte ilegible → aborta.

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **False positive flooding** (alertas de ruido; operador ignora las reales) | Calibración de umbrales; retroalimentación de descarte | test §13.4; D7.0 reduce falsos por aprendizaje |
| **Correlación confundida con causalidad** (operador actúa como si X causó Y sin serlo) | Campo confianza siempre presente; narrativa clara ("coincidieron en tiempo; no necesariamente causal") | test §13.6; reporte educado |
| **Patrón sesgado** (agregación oculta subgrupo con comportamiento distinto) | Análisis por cohort (segmento, canal, período) disponible | explorabilidad del patrón en dashboard |
| **Dependencia creada** (operador no puede decidir sin D07) | D07 opcional siempre (degradación elegante); panel sin D07 es menos bonito pero funciona | arquitectura: D07 es consumidor de P8, no productor de pedidos |
| **Reporte incomprensible** (jerga, gráficos malos) | Revisión de legibilidad; no spaghetti charts; narrativa en español simple | test §13.7; revisión humana post-VR |

---

## §16 — PUERTA v1.0: CHECKLIST DoD Y FALSACIÓN

### §16.1 Checklist
- [ ] D7.0–D7.2 cruzados con commit y acta.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D07-01 ✓ con Laboratorio.
- [ ] ≥50 filas de P8 disociadas en almacén.
- [ ] ≥3 umbrales definidos y versionados.
- [ ] ≥3 alertas emitidas, clasificadas correctamente, false positive rate <20%.
- [ ] ≥1 reporte con gráficos legibles y narrativa.
- [ ] Aislamiento verificado (tenant A no ve análisis B).
- [ ] Patrón reproducible (mismos datos → mismo resultado).
- [ ] P8 es honestamente disociado (auditoría de identificadores).

### §16.2 Falsación
1. Patrón no reproducible (mismo P8, distinto resultado) → investigar cálculo; revisitar §4.2.
2. False positives >20% (alertas que el operador descarta como ruido) → calibración de umbral mala; revisitar metodología.
3. Reporte ilegible (spaghetti charts, jerga inentendible) → revisión de UX; redacción más clara.
4. P8 contiene identificadores de cliente (fuga de privacidad) → parada; auditoría de disociación en D7.0.

---

## ANEXO A — ESQUEMAS DE PAYLOAD `inteligencia.*` v1

- **A.1 `patron.calculado`**: `{metrica, periodo, valor, promedio_historico, desviacion, trend: UP|DOWN|ESTABLE, confianza}`
- **A.2 `patron.desviacion`**: `{metrica, valor_observado, rango_esperado, desv_std, alerta: true}`
- **A.3 `alerta.emitida`**: `{alerta_id, metrica, severidad: CRITICA|ADVERTENCIA|INFO, razon, timestamp_anomalia, valor_observado}`
- **A.4 `correlacion.propuesta`**: `{alerta_id, evento_correlacionado_id, tiempo_diferencia_min, confianza: ALTA|MEDIA|BAJA, narrativa}`
- **A.5 `reporte.generado`**: `{reporte_id, periodo, metricas[], url_pdf, generado_en_ts}`
- **A.6 `tendencia.graficada`**: `{metrica, periodo, puntos[{fecha, valor}], tendencia_matematica, inflexion?}`
- **A.7 `reporte.ejecutivo`**: `{periodo, resumen_narrativo, cambios_principales[], alertas_del_periodo, recomendaciones}`
- **A.8 `umbral.definido`**: `{metrica, rango_minimo, rango_maximo, version, cambio_por_operador, ts_efectiva}`

---

*Fin de KAIZEN-D07 v1.0. Emitido el 2026-07-08. Productor puro de insights, no decisor. Greenfield puro; dependencia crítica: P8 de otros cubos. Degradación elegante: todo funciona sin él, funciona mejor con él. La regla de oro: propone, no ejecuta. El operador decide siempre. Dependencia de arranque: D00-B1 ✓ + mínimo D01 ✓ + D05 ✓ (generando P8). Siguiente y último de la serie: D08 (Cumplimiento).*
