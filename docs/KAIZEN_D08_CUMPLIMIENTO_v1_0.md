# KAIZEN-D08 — DEPARTAMENTO CUMPLIMIENTO
## Serie de dossieres departamentales KAIZEN · Documento 08

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `cumplimiento.*` (payloads en Anexo A).
**Entrada:** calendario de obligaciones (legal, regulatorio, contrato), bitácora de eventos (D00 §3.4), decisiones del operador.
**Diferencia estratégica:** es el cubo **defensivo**. No genera ingresos; asegura que lo que se genera sea defendible ante una inspección, litigio o auditoría. Su ausencia no es invisible: es bomba de tiempo.
**Estado real:** cero líneas de código. Greenfield puro. Existe documentación normativa (Ley 11/2021, RD 1007/2023, Verifactu en D04) como input; el cubo no.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorridos E2E (registro de obligación, auditoría, defensa documental)
- §2 — Anatomía del trabajo de cumplimiento que replica (por qué es el más incómodo)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados: obligación, evidencia, auditoría
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado (§7 es meta, pero lo completamos): regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo (no genera valor; previene pérdida)
- §10 — Kit de despliegue y superficie del auditor
- §11 — Estado real vs. dossier: greenfield con obligaciones reales presentes
- §12 — Programa de construcción a v1.0: bloques D8
- §13 — Batería de pruebas duras
- §14 — Prueba de vida real pre-registrada (VR-D08-01)
- §15 — Riesgos de segundo orden
- §16 — Puerta v1.0: checklist DoD y falsación
- Anexo A — Esquemas de payload `cumplimiento.*` v1
- Anexo B — Calendario de obligaciones modelo (España 2026–2027)

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan. Índice: plantilla D01.

### §0.2 Por qué es diferente
Cumplimiento no es "hacer bien las cosas"; es **dejar rastro de que se hicieron bien**. Es la diferencia entre "no cometimos fraude" y "podemos probar que no lo hicimos ante un juez". El cubo es el guardia de ese rastro.

---

## §1 — MISIÓN, FRONTERA Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Cumplimiento asegura que cada obligación legal, regulatoria o contractual tenga respuesta documentada a tiempo, y que esa respuesta sea verificable si alguien pregunta años después.

### §1.2 Qué NO es — FIJADO
- **No es asesoramiento legal.** No interpreta leyes; es ejecutor de leyes que ya existen.
- **No es abogado.** No defiende en litigio; prepara la defensa documentada para que un abogado pueda usarla.
- **No es "hacer papelería"** sin razón. Cada documento tiene fecha, motivo, auditoría.
- **No congela el negocio.** El cumplimiento es guardrail, no muro; permite que Comercial venda mientras registra.

### §1.3 Recorrido A — LOS PASOS del registro de obligación

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| C1 | Entrada de obligación: ley, decreto, acuerdo genera un "debe hacer X en fecha Y" | Sistema externo o Operador | — | obligación bien formada (nombre, fecha, área responsable) | — |
| C2 | Categorización: regulatoria (ley), contractual (cliente), auditoria externa, interna | Operador | — | categoría versionada | `cumplimiento.obligacion.registrada` |
| C3 | Asignación de responsable: ¿quién debe hacer esto? (operador, gestoría, tercero) | Operador | Operador | responsable identificado | `cumplimiento.obligacion.asignada` |
| C4 | Deadlines: fecha límite, alertas pre-limite (30 días, 7 días, 1 día) | Sistema | automático | fechas sensatas | — |
| C5 | Preparación de evidencia: qué documento/acción probará cumplimiento | Operador + Sistema | Operador decide | checklist de qué va en expediente | `cumplimiento.evidencia.identificada` |
| C6 | Cumplimiento: fecha de realización, documento/acta generada | Operador | Operador | evidencia física (archivo, email, acta notarizada) | `cumplimiento.obligacion.cumplida` |
| C7 | Cierre: arquivamiento de expediente con fecha, evidencia, auditoría de integridad | Sistema | automático | expediente íntegro y firmado (si aplica) | `cumplimiento.expediente.cerrado` |

### §1.4 Recorrido B — LOS PASOS de la auditoría de cumplimiento

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| A1 | Auditoría interna programada: mes/trimestre/año según criticidad | Sistema | — | calendario fijado | — |
| A2 | Selección de obligaciones: ¿qué auditar? (muestra aleatoria, todas, críticas) | Auditor | Auditor | — | — |
| A3 | Verificación: abrir expediente, validar evidencia, verificar fechas | Auditor | Auditor (honesto) | checklist contra requisito | `cumplimiento.auditoria.ejecutada` |
| A4 | Hallazgo: ¿se cumplió correctamente? {CUMPLIDO, CUMPLIDO_PARCIAL, NO_CUMPLIDO, PENDIENTE} | Auditor | Auditor | veredicto honesto, no político | `cumplimiento.hallazgo.documentado` |
| A5 | Acción correctiva (si aplica): "haremos X para que esto no ocurra de nuevo" | Operador | Operador | acción es concreta y rastreable | `cumplimiento.accion_correctiva.planificada` |
| A6 | Reporte de auditoría: informe ejecutivo con hallazgos y tendencias | Auditor | Auditor | comprensible a un tercero (juez, inspector) | `cumplimiento.reporte_auditoria.generado` |

### §1.5 Recorrido C — LOS PASOS de la defensa documental

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| D1 | Evento de alerta externa: inspector llega, litigio inicia, auditoría de tercero programada | Sistema externo | — | — | — |
| D2 | Movilización: extraer expedientes relevantes, verificar integridad (firmas, hashes) | Operador + Sistema | Sistema automático | expedientes con integridad verificable | — |
| D3 | Narrativa defensiva: "aquí está el acta de cumplimiento, aquí están las evidencias, aquí está la auditoría interna que lo validó" | Operador (con asesoría legal) | Operador | historia coherente y documentada | `cumplimiento.defensa.preparada` |
| D4 | Entrega al abogado o inspector: archivos compilados, metadatos probatorios | Operador | Operador | — | `cumplimiento.expediente.entregado` |

---

## §2 — ANATOMÍA DEL TRABAJO DE CUMPLIMIENTO QUE REPLICA

### §2.1 Descomposición

| Función humana | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|
| Responsable legal | "Estos son los reglamentos que afectan a Laboratorio; estos son los plazos" | Registro de obligaciones + calendrier de alertas |
| Administrativo de auditoría | "Hice esto el día tal; aquí está la acta, la firma, el recibo" | Gestor de expedientes + evidencia |
| Auditor interno | "Revisé 10 casos; todos cumplieron. Acá está mi informe" | Validador de expedientes + generador de reporte |
| Abogado defensivo | "Si nos demandan, aquí está todo lo que hicimos bien y cómo lo probamos" | Compilador de defensa documental |

### §2.2 El reparto FIJADO
- **Del cubo:** recordatorio de fechas, solicitud de evidencia, almacenamiento íntegro de expedientes, auditoría automatizada de checklists, compilación defensiva.
- **Del operador:** decisión de cómo cumplir (qué acción tomar), aporte de evidencia (archivos, actas), validación final de expediente.
- **Del abogado/auditor externo:** interpretación final (si el expediente es defensible o no; qué riesgos quedan).

**Regla de oro (FIJADO):** si algo no está documentado en D08, **no existió desde el punto de vista legal**. La ausencia de registro es peor que un registro que dice "no lo hicimos".

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

### §3.1 Registrador de obligaciones — **P·D8.0**
- **Misión:** que ninguna obligación se olvide.
- **E→P→S:** entrada (decreto, contrato, acuerdo, auditoría externa) → parsing de fecha y requisito → registro en calendario → alert schedule.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (registro). **Verificación:** integridad de fecha y texto de obligación.
- **Estado:** cero líneas; es intake.

### §3.2 Gestor de evidencia — **P·D8.0**
- **Misión:** que el cumplimiento sea probado.
- **E→P→S:** operador reporta "cumplí X"; qué prueba lo demuestra (archivo, email, acta, atestiguamiento) → almacenamiento seguro + metadatos (firma, hash, timestamp) → expediente armado.
- **Clase:** TRIVIAL. **Autonomía:** operador decide qué es evidencia. **Verificación:** integridad de archivos (hash, no-edición).
- **Estado:** cero líneas; es vault.

### §3.3 Notificador de plazo — **P·D8.0**
- **Misión:** el operador no olvida.
- **E→P→S:** obligación con fecha → hoy + 30 días = alerta (email); hoy + 7 días = alerta (rojo en panel); hoy + 1 día = CRITICA (SMS).
- **Clase:** TRIVIAL. **Autonomía:** automático según calendario. **Verificación:** alerta llegó a tiempo.
- **Estado:** cero líneas; es scheduler.

### §3.4 Validador de expediente — **P·D8.1**
- **Misión:** que cada cumplimiento esté completo antes de archivarse.
- **E→P→S:** operador reporta "cumplí X"; solicita validación → sistema verifica checklist (¿tiene fecha? ¿tiene evidencia? ¿tiene responsable?) → veredicto {COMPLETO, INCOMPLETO, PROBLEMA}.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (validación de checklist). **Verificación:** —.
- **Estado:** cero líneas; es validador.

### §3.5 Auditor automático — **P·D8.1**
- **Misión:** que la auditoría interna sea continua, no anual.
- **E→P→S:** muestra de expedientes versionados (últimos 30 días o semanal) → verificación de integridad (hash, firma) → comparación contra requisito original → veredicto de cumplimiento.
- **Clase:** TRIVIAL (determinista). **Autonomía:** automático según schedule. **Verificación:** resultado reproducible.
- **Estado:** cero líneas; es validador periódico.

### §3.6 Generador de defensa — **P·D8.2**
- **Misión:** cuando alguien pregunta, aquí está todo.
- **E→P→S:** trigger de "alerta externa" (inspector, litigio, auditoría) → selección automática de expedientes relevantes → compilación de narrativa defensiva (timeline, actas, auditoría interna) → formato entregable (PDF/ZIP compilado).
- **Clase:** ESTANDAR. **Autonomía:** REVERSIBLE (compilación). **Verificación:** expediente íntegro (nada faltante o corrupto).
- **Estado:** cero líneas; es compilador.

---

## §4 — MÁQUINA DE ESTADOS: OBLIGACIÓN, EVIDENCIA, AUDITORÍA

### §4.1 Obligación — FIJADO

```
REGISTRADA → ASIGNADA → EN_CURSO → CUMPLIDA → AUDITADA → CERRADA
              ↓                      ↓
           RECHAZADA (no aplica)  INCUMPLIDA (acción correctiva)
                                      ↓
                               ACCION_CORRECTIVA → REAUDITADA → CERRADA
```

| Estado | Significado | Quién entra | Quién sale |
|---|---|---|---|
| REGISTRADA | Obligación en el calendario | Sistema/Operador | Operador (ASIGNADA) |
| ASIGNADA | Responsable identificado | Operador | Operador (EN_CURSO) |
| EN_CURSO | Trabajo en progreso (pre-plazo) | Operador | Operador (CUMPLIDA) o INCUMPLIDA (post-plazo) |
| CUMPLIDA | Plazo cumplido; evidencia aportada | Operador | Sistema (AUDITADA automático) |
| AUDITADA | Auditoría interna verificó | Sistema/Auditor | CERRADA (OK) o acción correctiva (problema) |
| INCUMPLIDA | Plazo pasó sin cumplimiento | Sistema (timeout) | acción correctiva (escalación) |
| ACCION_CORRECTIVA | Remediación en curso | Operador | REAUDITADA |
| CERRADA | Expediente archivado, íntegro, defensible | Auditor/Sistema | inmutable |
| RECHAZADA | Obligación no aplica al tenant (legítimamente) | Operador (con asesoramiento) | CERRADA (con acta de rechazo) |

### §4.2 Expediente (grupo de evidencias) — FIJADO

```
EN_ARMADO → COMPLETO → VALIDADO → ARCHIVADO
              ↓ falta
           INCOMPLETO (solicitar evidencia faltante)
```

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `cumplimiento.obligacion.registrada` | 1 | A.1 | entrada de obligación (varias/mes típico) | no | bien formada (fecha, requisito) | — | TRIVIAL |
| `cumplimiento.obligacion.asignada` | 1 | A.2 | post-registro | no | responsable identificado | — | TRIVIAL |
| `cumplimiento.alerta.plazo` | 1 | A.3 | automático (30d, 7d, 1d antes plazo) | **sí** (notificación operador) | calendario verificable | — | TRIVIAL |
| `cumplimiento.evidencia.aportada` | 1 | A.4 | operador sube archivo | no | hash, no-edición | — | TRIVIAL |
| `cumplimiento.expediente.validado` | 1 | A.5 | post-cierre de evidencia | no | checklist completado | — | TRIVIAL |
| `cumplimiento.obligacion.cumplida` | 1 | A.6 | operador cierra | **sí** (para auditoría) | fecha + evidencia | — | TRIVIAL |
| `cumplimiento.obligacion.incumplida` | 1 | A.7 | timeout post-plazo | **sí** (alerta crítica) | prueba de timeout | — | TRIVIAL |
| `cumplimiento.auditoria.ejecutada` | 1 | A.8 | periódico (semana, mes) | no | muestra verificada | — | TRIVIAL |
| `cumplimiento.hallazgo.documentado` | 1 | A.9 | post-auditoría | **sí** (si hay problema) | veredicto y evidencia | — | TRIVIAL |
| `cumplimiento.accion_correctiva.planificada` | 1 | A.10 | post-hallazgo negativo | **sí** (tracking) | acción concreta + fecha | — | TRIVIAL |
| `cumplimiento.reporte_auditoria.generado` | 1 | A.11 | periódico (fin de mes) | no | resumen de hallazgos | — | TRIVIAL |
| `cumplimiento.defensa.preparada` | 1 | A.12 | bajo demanda (pre-auditoría, litigio) | no | compilación íntegra | — | TRIVIAL |

### §5.B — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente |
|---|---|---|
| Calendario externo (ley, decreto, auditoría) | Sí (es entrada) | sin él, no hay obligaciones que registrar |
| Bitácora de eventos D00 §3.4 (timeline de decisiones) | No (para contexto defensivo) | sin ella, defensa menos convincente pero funciona |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado |
|---|---|---|
| `cumplimiento.consulta_obligacion(tenant, id)` | → estado, plazo, responsable, evidencia | lectura pura |
| `cumplimiento.generar_defensa(tenant, fecha_inicio, fecha_fin)` | → PDF/ZIP compilado, íntegro, defensible | requiere expedientes cerrados |

### §5.D–F — véase §6, §8, §10

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

**FIJADO:** Cumplimiento es principalmente automático (alertas, auditoría periódica), pero cada decisión de cumplimiento requiere operador.

| Acción | Clase | CERO | BAJA | MEDIA | ALTA |
|---|---|---|---|---|---|
| Registrar obligación | REVERSIBLE | operador ingresa | operador ingresa | operador ingresa | operador ingresa |
| Alertar plazo (30d, 7d, 1d) | TRIVIAL | automático | automático | automático | automático |
| Solicitar evidencia | TRIVIAL | automático (checklist) | automático | automático | automático |
| Validar expediente | TRIVIAL | propone | automático (checklist) | automático | automático |
| Marcar incumplida (timeout) | TRIVIAL | propone | **automático (cierra plazo)** | automático | automático |
| Ejecutar auditoría periódica | TRIVIAL | — | automático | automático | automático |
| Generar reporte de auditoría | REVERSIBLE | — | operador solicita | periódico automático | periódico automático |
| Compilar defensa | REVERSIBLE | operador solicita | operador solicita | operador solicita | operador solicita |

---

## §7 — CUMPLIMIENTO INTEGRADO (META): REGLA → CONTROL → TEST

| # | Regla | Control | Test |
|---|---|---|---|
| 1 | Obligación no se olvida (fecha + texto registrados) | entrada en calendario con alerta schedule | `test_obligacion_registrada` |
| 2 | Plazo es respetado o timeout | notificación pre-plazo; marca INCUMPLIDA post-plazo | `test_timeout_marca_incumplida` |
| 3 | Evidencia es íntegra (no edición post-hoc) | hash SHA-256 de archivo + timestamp + firma del operador | `test_evidencia_integra` |
| 4 | Expediente es validable (checklist completado) | validación de campos obligatorios antes de CERRADA | `test_expediente_valido` |
| 5 | Auditoría periódica ocurre (no anual, continua) | auditoría automática cada N días/semanas | `test_auditoria_periodica` |
| 6 | Hallazgo es documentado honestamente | veredicto sin censura política; acción correctiva concreta | `test_hallazgo_honesto` |
| 7 | Defensa es compilable (expediente accesible) | función de generación de defensa devuelve PDF/ZIP íntegro | `test_defensa_compilable` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Obligaciones, expedientes, auditorías, hallazgos son **la verdad defensiva** (P9). Pérdida = sin defensa ante inspección. Es pérdida total.

### §8.2 Señal recursiva (D08 produce P8 para sí mismo) — FIJADO
Por cada auditoría periódica:

```
(tenant, periodo, obligaciones_totales, cumplidas, incumplidas, tasa_cumplimiento_pct,
 hallazgos_criticos, acciones_correctivas_pendientes, ts)
```

Ajusta: identificación de áreas problemáticas (si Legal siempre incumple, hay problema sistémico).

### §8.3 Entidades y propiedad
Obligaciones, expedientes, auditorías, defensas → DATO_CLIENTE (exportable, defensible). Calendarios de obligaciones por jurisdicción, templates de acta → DATO_PLATAFORMA. Señales P8 agregadas → DATO_AGREGADO.

---

## §9 — ECONOMÍA DEL CUBO

### §9.1 Coste marginal — ABIERTO (lo cierra VR-D08-01)
D08 es overhead de compliance (sustrato + almacenamiento). Sin cliente directo, es costo puro. Margen: evita multas y litigios. Es **inversión en riesgo**, no en ingresos.

### §9.2 Conversión del riesgo
Datos de cumplimiento → seguros (pólizas más baratas si historial de cumplimiento) + auditorías externas (financieras de inversores, regulatorias) → credibilidad.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DEL AUDITOR

### §10.1 Kit
1. **Calendario de obligaciones:** por jurisdicción, sector (España, autonómico, local; HORECA, general).
2. **Checklist de cumplimiento:** por tipo de obligación (ej. Verifactu: RFA, remisión AEAT, bitácora SIF).
3. **Plantillas de acta:** para documentar cumplimiento (acta de reunión, acta de gestión, acta de auditoría).
4. **Auditoría periodicidad:** semanal/mensual/trimestral según criticidad.
5. **Smoke test:** registrar obligación ficticia, aportar evidencia, validar expediente, generar defensa.

### §10.2 Superficie del auditor — FIJADO
- **Dashboard de obligaciones:** registradas, en plazo, próximo vencimiento, incumplidas.
- **Expedientes:** lista, estado (EN_ARMADO, COMPLETO, ARCHIVADO), expediente individual con archivos y metadata.
- **Auditoría:** últimas auditorías ejecutadas, hallazgos, acciones correctivas.
- **Reporte de compliance:** tasa de cumplimiento, tendencia, áreas de riesgo.
- **Defensa:** compilador de expedientes para abogado/inspector.

---

## §11 — ESTADO REAL VS. DOSSIER: GREENFIELD CON OBLIGACIONES REALES

| Item | Estado | Notas |
|---|---|---|
| Código de D08 | No existe | Greenfield puro |
| Obligaciones legales España 2026–2027 | Existen; listadas en Anexo B | Entrada para registrador |
| Checklist de cumplimiento Verifactu | Existe en D04 §7 | Copiable a D08 como template |
| Certificados FNMT | Necesarios (no generados aún) | Dependencia externa; requisito antes de v1.0 |
| Auditoría externa | No encargada aún | Recomendación pre-VR |
| Sistema de notificación | Será parte de D8.0 | Usar infraestructura de alertas D00 |

**Honestidad:** Greenfield puro de código, pero con obligaciones reales bien documentadas (leyes existen, plazos son fijos). La diferencia con D07: no hay incertidumbre sobre qué hay que guardar; es ley.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES D8

Orden por dependencia: D8.0 (registro + evidencia + alertas) → D8.1 (validación + auditoría) → D8.2 (defensa + reportes). Requiere D00-B1 ✓. Ciclo D00 §0.6; commit por bloque.

### D8.0 — Registro, evidencia y alertas
1. Registro de obligaciones en calendario (entrada manual o parser de documentos).
2. Gestor de evidencia: operador sube archivos con metadata (hash, timestamp, firma).
3. Notificador de plazo: alertas automáticas (30d, 7d, 1d).
4. Marcación de cumplida/incumplida.
5. **Puerta D8.0:** ≥10 obligaciones registradas + ≥5 con evidencia aportada + alertas de plazo enviadas en tiempo + VR-D08-01 semana 1.

### D8.1 — Validación y auditoría
1. Validador de expediente (checklist).
2. Auditor automático (muestra periódica de expedientes).
3. Generador de hallazgo (veredicto: CUMPLIDO, PARCIAL, NO_CUMPLIDO).
4. Reporte de auditoría (resumen de hallazgos).
5. **Puerta D8.1:** ≥3 auditorías ejecutadas + ≥1 hallazgo documentado (puede ser CUMPLIDO) + reporte legible generado.

### D8.2 — Defensa y reportes
1. Compilador de defensa: extrae expedientes + narrativa + actas.
2. Formato entregable (PDF/ZIP con estructura clara).
3. Reporte de compliance mensual/trimestral.
4. (D8.2 puede quedar post v1.0 si D8.0 y D8.1 están sólidas.)

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de tenant** | 2 tenants con obligaciones distintas | obligaciones A no contaminan B |
| 13.2 | **Alerta de plazo funciona** | Obligación con plazo 7 días; día 7 alerta enviada | alerta llega y operador la recibe |
| 13.3 | **Timeout marca incumplida** | Obligación con plazo 5 días; 6 días después, estado | estado = INCUMPLIDA automático |
| 13.4 | **Evidencia íntegra** | Operador sube archivo; hash generado; archivo modificado externamente | re-cálculo hash ≠ original; CORRUPTO |
| 13.5 | **Expediente validable** | Operador completa checklist; solicita validación | COMPLETO si todos los campos; INCOMPLETO si faltan |
| 13.6 | **Auditoría reproduce resultado** | Mismo expediente, 2 auditorías en semana | 2/2 mismo veredicto (CUMPLIDO o NO_CUMPLIDO) |
| 13.7 | **Defensa compilable** | Genera defensa de periodo con 5 obligaciones cerradas | PDF/ZIP íntegro, todos los expedientes presentes |
| 13.8 | **Reporte de compliance legible** | Genera reporte de mes; 10 obligaciones, 8 cumplidas, 2 incumplidas | tasa 80%, hallazgos claros, sin jerga |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D08-01

Pre-registro conforme a D00 Anexo II:
- **Tenant:** `alcayana` (o holding Iván + mujer: ambas S.L. con obligaciones reales) · **Ventana:** 4 semanas · **Acciones:** ≥10 obligaciones registradas, ≥5 cumplidas documentadas, ≥1 auditoría ejecutada.
- **Métricas y umbrales (binarios):**
  1. 100% de obligaciones registradas con fecha clara (ninguna borrosa).
  2. ≥5 con evidencia aportada y hash verificable (no corrupción).
  3. Alertas de plazo (30d, 7d) enviadas a tiempo y recibidas.
  4. ≥1 expediente validado como COMPLETO.
  5. ≥1 auditoría ejecutada con veredicto documentado (puede ser CUMPLIDO).
  6. Operador genera defensa compilada (PDF/ZIP con expedientes).
  7. Aislamiento: obligaciones de tenant A no visibles en B.
- **Fallo total:** obligación no registrada, alerta no llega, evidencia corrupta, expediente no validable, auditoría no reproducible → aborta.

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **Obligación olvidada** (ley nueva, no registrada) | Monitoreo externo de cambios legales; operador input manual | entrada manual de calendario; auditoría externa revisará |
| **Evidencia editada post-hoc** (operador modifica archivo para "cubrir" incumplimiento) | Hash no coincide; archivo marcado CORRUPTO; auditoría debe investigar | test §13.4; no hay forma de disimular edición |
| **Timeout no marca incumplida** (bug: plazo pasa pero estado sigue EN_CURSO) | Sistema marca automáticamente; alerta CRITICA emitida | test §13.3; gate determinista |
| **Auditoría falsa** (operador marca CUMPLIDO sin verificar) | Auditoría automática compara contra checklist; honestidad requerida | test §13.6; reproducibilidad |
| **Defensa falta expediente** (compilador pierde una carpeta) | Integridad verificada pre-compilación (cantidad de archivos, hashes) | test §13.7 |
| **Reporte oculta hallazgos** (auditor político dice que todo está bien) | Verificación de muestras: auditor no puede inventar cumplimiento | diseño: auditor automático vs. operador político (conflicto) |

---

## §16 — PUERTA v1.0: CHECKLIST DoD Y FALSACIÓN

### §16.1 Checklist
- [ ] D8.0–D8.1 cruzados con commit y acta.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D08-01 ✓ con Alcayana/holding.
- [ ] ≥10 obligaciones registradas con plazo claro.
- [ ] ≥5 con evidencia aportada, hash verificable, no corrupta.
- [ ] Alertas de plazo (30d, 7d, 1d) llegando a operador.
- [ ] ≥1 expediente validado como COMPLETO.
- [ ] ≥1 auditoría ejecutada con veredicto documentado.
- [ ] Defensa compilable (PDF/ZIP íntegro).
- [ ] Aislamiento verificado (tenant A no ve B).

### §16.2 Falsación
1. Obligación no registrada (llegó ley nueva, no está en calendar) → sistema de monitoreo legislativo falla o input manual falla.
2. Alerta no llega (plazo hoy; operador no se enteró) → notificador falla; investigar §5.A.
3. Evidencia corrupta (archivo editado; hash no coincide) → integridad de almacén falla; revisitar D8.0.
4. Auditoría inconsistente (misma obligación, veredictos distintos en semana) → reproducibilidad falla; investigar §7.
5. Defensa falta expediente (compilador olvidó una carpeta) → integridad pre-compilación falla; revisitar D8.2.

---

## ANEXO A — ESQUEMAS DE PAYLOAD `cumplimiento.*` v1

- **A.1 `obligacion.registrada`**: `{obligacion_id, nombre, tipo: LEY|REGULATORIA|CONTRACTUAL, fecha_limite, area_responsable, descripcion}`
- **A.2 `obligacion.asignada`**: `{obligacion_id, responsable_id, asignado_en_ts}`
- **A.3 `alerta.plazo`**: `{obligacion_id, dias_restantes, urgencia: CRITICA|ADVERTENCIA|INFO, fecha_vencimiento}`
- **A.4 `evidencia.aportada`**: `{evidencia_id, obligacion_id, archivo_name, hash_sha256, timestamp, operario_firma?}`
- **A.5 `expediente.validado`**: `{expediente_id, checklist[{campo, presente, requerido}], veredicto: COMPLETO|INCOMPLETO}`
- **A.6 `obligacion.cumplida`**: `{obligacion_id, fecha_cumplimiento, evidencia_ref[], acta_cumplimiento_hash}`
- **A.7 `obligacion.incumplida`**: `{obligacion_id, fecha_timeout, alerta_emitida}`
- **A.8 `auditoria.ejecutada`**: `{auditoria_id, muestra[{obligacion_id, veredicto}], fecha_ejecucion, auditor_ref}`
- **A.9 `hallazgo.documentado`**: `{hallazgo_id, obligacion_id, veredicto: CUMPLIDO|PARCIAL|NO_CUMPLIDO, evidencia, motivo}`
- **A.10 `accion_correctiva.planificada`**: `{accion_id, hallazgo_id, descripcion, fecha_target, responsable}`
- **A.11 `reporte_auditoria.generado`**: `{reporte_id, periodo, resumen_cumplimiento_pct, hallazgos_criticos, acciones_correctivas_abiertas}`
- **A.12 `defensa.preparada`**: `{defensa_id, fecha_solicitud, expedientes_compilados[], narrativa_defensiva, formato: PDF|ZIP, timestamp_integridad}`

---

## ANEXO B — CALENDARIO DE OBLIGACIONES MODELO (ESPAÑA 2026–2027)

(Selección de obligaciones típicas para HORECA-SME + software de gestión. No exhaustivo; auditoría legal externa requerida.)

| Obligación | Tipo | Plazo | Frecuencia | Área responsable | Cumplimiento v1.0 |
|---|---|---|---|---|---|
| Verifactu (RD 254/2025) | Regulatoria | 01-07-2027 (IRPF) / 01-01-2027 (Sociedades) | Por emisión de factura | Finanzas | D04 ✓ |
| RRSIF (RD 1007/2023) | Regulatoria | 01-01-2027 (Sociedades) | Por emisión de factura | Finanzas | D04 ✓ |
| Seguridad Social | Regulatoria | Mensual (día 10–15) | Mensual | RRHH/Administración | Operador manual |
| IVA (declaración trimestral) | Regulatoria | Día 20 mes siguiente trimestre | Trimestral | Finanzas | Operador manual |
| IR (declaración anual) | Regulatoria | 01-07 año siguiente | Anual | Finanzas | Operador manual |
| Contabilidad (auditoría) | Regulatoria | 31-05 año siguiente | Anual | Contable | Gestoría |
| GDPR (derechos de sujeto) | Regulatoria | Responder en 30 días | Por solicitud | Legal/IT | Operador manual |
| Contratos cliente (custodia) | Contractual | Indefinido | — | Legal | Operador (vault D08) |
| Auditoría interna de cumplimiento | Interna | Mensual/trimestral | Periódica | Cumplimiento | D8.1 automático |

---

*Fin de KAIZEN-D08 v1.0. Emitido el 2026-07-08. El cubo defensivo. Greenfield puro de código, con obligaciones reales y plazos fijos. La regla de oro: si no está documentado en D08, no ocurrió legalmente. Dependencia de arranque: D00-B1 ✓ + calendario de obligaciones externos. Fin de la serie de dossieres departamentales D00–D08. Próximo: construcción (bloques), testing, integración en producción.*
