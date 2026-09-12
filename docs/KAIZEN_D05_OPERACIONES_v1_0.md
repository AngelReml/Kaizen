# KAIZEN-D05 — DEPARTAMENTO OPERACIONES
## Serie de dossieres departamentales KAIZEN · Documento 05

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `operacion.*` (payloads en Anexo A).
**Entrada:** `comercial.pedido.atribuido` (D01/D04) o `cliente.repeticion.respondida` SI (D03).
**Diferencia estratégica:** es el cubo del **choque con la realidad**. Todo lo que Comercial promete, Operaciones debe cumplir: capacidad real, fechas reales, entregas reales. Si la capacidad dice "sí puedo" cuando es mentira, aquí revienta.
**Estado real:** existe `departments/operaciones/` con manejo de pedidos por JSON (commit `57e6dcd`, "JSON knowledge base storage"); sin sistematización, sin máquina de estados clara, sin integración con el bus.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorridos E2E (flujo de pedido, capacidad viva)
- §2 — Anatomía del trabajo operativo que replica (por qué es el filtro de realidad)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados del pedido en operaciones y límites de capacidad
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo (costo de infra, tiempo de operador)
- §10 — Kit de despliegue y superficie del operador
- §11 — Estado real vs. dossier: el código existe, la integración no
- §12 — Programa de construcción a v1.0: bloques D5
- §13 — Batería de pruebas duras
- §14 — Prueba de vida real pre-registrada (VR-D05-01)
- §15 — Riesgos de segundo orden
- §16 — Puerta v1.0: checklist DoD y falsación
- Anexo A — Esquemas de payload `operacion.*` v1

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan. Índice: plantilla D01.

### §0.2 Por qué es crítico
Operaciones es donde la mentira piadosa de Comercial se encuentra con la verdad del horno. Si Comercial promete "entrega en 48h" y Operaciones tiene cola de 15 días, el cliente come mierda y el sistema colapsa. Este cubo es el guardián de esa coherencia.

---

## §1 — MISIÓN, FRONTERA Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Operaciones convierte cada pedido en un plan: qué se hace, cuándo, con qué recursos; registra el progreso real y alerta cuando el plan se rompe. **No es ejecución física** (el horno lo maneja el operador humano); es **visibilidad y coordinación de la realidad**.

### §1.2 Qué NO es — FIJADO
- **No es control de inventario.** No gestiona un almacén; gestiona pedidos confirmados y la capacidad para hacerlos. Inventario es un parámetro de entrada.
- **No es scheduling automático.** El operador decide la secuencia; el cubo registra la capacidad consumida.
- **No es logística.** No planifica rutas ni transporte (ese es problema de la integración física con el proveedor de logística).
- **No ejecuta la operación.** El operador es quien *hace*; el cubo es quién *ve y recuerda* lo que se hizo.

### §1.3 Recorrido A — LOS PASOS del flujo de un pedido en operaciones

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| O1 | Pedido llega a Operaciones (desde D01/D03 como `comercial.pedido.atribuido` o `cliente.repeticion.respondida`) | Bus | — | pedido bien formado (cliente, producto, fecha pedida, cantidad) | `operacion.pedido.recibido` |
| O2 | Verificación de capacidad: ¿puedo hacerlo en esa fecha? ¿tengo materia prima? | Sistema + Operador | Sistema propone; operador confirma si hay obstáculo | inventario suficiente (parámetro); capacidad disponible en rango de fechas | `operacion.capacidad.consultada` |
| O3 | Si NO: propuesta de reschedule (fecha alternativa) o rechazo | Sistema propone | Operador o cliente decide (vía D03) | — | `operacion.pedido.rechazado` o `.reschedule_propuesto` |
| O4 | Si SÍ: alta en planning (cola del operador, item de producción) | Sistema | automático | sequencing rules (prioridad por cliente LOYAL, urgencia, compatibilidad de receta) | `operacion.pedido.confirmado` |
| O5 | Ejecución: operador produce (horno, empaque, etc.) | Operador | Operador | — | — |
| O6 | Registro de hito: "lote completo", "empaquetado", "listo para envío" | Operador | Operador entra marca (checkbox en panel) o sistema deduce de eventos externos (balanza, cronometro, foto) | timestamp + foto/qr opcional | `operacion.pedido.hito` |
| O7 | Entrega a logística: albarán con peso, dimensiones, cliente, dirección | Sistema + Logística | Logística firma | entrega física confirmada | `operacion.pedido.entregado_a_logistica` |
| O8 | Transito: notificación a cliente (opcional, si integración existe) | Logística o Sistema propone | — | — | consumido por D03/cliente |
| O9 | Entrega final: cliente recibe | Cliente | Cliente | — | señal externa (cliente confirma o sistema deduce) |
| O10 | Cierre de operaciones: inventario ajustado, pedido movido de ACTIVO a COMPLETADO | Sistema | automático | auditoría de materiales gastados vs. recibidos | `operacion.pedido.completado` |

### §1.4 Recorrido B — LOS PASOS del monitoreo de capacidad

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| C1 | Día laboral: agregar capacidad en el calendario (p. ej. "hoy, horno puede hacer 50 panes") | Operador | Operador (sabe capacidad del día) | — | `operacion.capacidad.declarada` |
| C2 | Cada pedido confirmado consume capacidad (p. ej. "este lote consume 5 panes worth") | Sistema | automático | suma de consumo por día ≤ capacidad | `operacion.capacidad.consumida` |
| C3 | Si suma > capacidad: alerta y bloqueo (no se acepta más pedidos en esa fecha) | Sistema | **automático: cierra la puerta** | no es decisión; es barrera física | `operacion.capacidad.saturada` |
| C4 | Monitoreo real vs. plan: operador registra avance (hito) | Operador | Operador (o sensor: balanza, tiempo) | — | `operacion.pedido.hito` |
| C5 | Análisis de desviación: plan decía 5h, operador tardó 7h → P8 (útil para ajustar capacidad futura) | Sistema | — | — | asiento P8 |
| C6 | Propuesta de capacidad para mañana basada en trending | Sistema | operador revisa y confirma | — | `operacion.capacidad.propuesta_proximo` |

---

## §2 — ANATOMÍA DEL TRABAJO OPERATIVO QUE REPLICA

### §2.1 Descomposición

| Función humana | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|
| Encargado de producción | "Hoy tengo esta cola de pedidos; puedo hacer X cantidad; eso me lleva hasta las 5pm" | Declarador de capacidad + consumidor automático |
| El dueño mirando la cola | "Este cliente es VIP, ese es churro, esos son urgentes" | Reglas de priorización + alerta de saturación |
| Logistica coordinador | "Esto va a Cieza hoy, eso a Murcia mañana" | Historificador de hitos + entrega a logística |
| Contable de materiales | "Gasté 20kg harina, me quedan 80kg" | Ajuste de inventario post-cierre |

### §2.2 El reparto FIJADO
- **Del cubo:** memoria de lo que se prometió (fecha, cantidad, cliente), capacidad declarada vs. consumida, visibilidad del progreso real (hitos), alertas cuando el plan se rompe.
- **Del operador:** decisión de qué se hace (secuencia), declaración de capacidad, registro del avance, adaptación en tiempo real (cambios de plan, urgencias).
- **De Comercial:** promesa de fecha y cantidad (consumo de capacidad futura).

**Regla de oro (FIJADO):** Operaciones **nunca automatizan una promesa de fecha al cliente**. Si Comercial dice "entrega en 48h" sin consultarle a Operaciones, Operaciones bloqueará la aceptación del pedido con aviso "capacidad saturada". El cliente rechazado vuelve a Comercial (D01 paso 3: reschedule o rechazo), y Comercial reintenta con fecha real. **Así de honesto.**

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

### §3.1 Receptor de pedidos — **E parcial** (input existe vía bus; sistematización en D5.0)
- **Misión:** que ningún pedido se pierda entre Comercial y la cola real.
- **E→P→S:** evento `comercial.pedido.atribuido` o `cliente.repeticion.respondida` con cliente/producto/fecha/cantidad → validación de bien-formedad → alta en la lista de "pendientes de confirmar".
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (recepción). **Verificación:** —.
- **Estado:** el bus existe (D01 emite el evento); el receptor es middleware que se sistematiza.

### §3.2 Validador de capacidad — **P·D5.0**
- **Misión:** la verdad sobre qué se puede hacer.
- **E→P→S:** pedido (cliente, producto, fecha, cantidad) + capacidad declarada por operador para esa fecha + inventario → consulta de viabilidad (¿hay capacidad? ¿hay materia prima?) → respuesta {CONFIRMABLE, RESCHEDULE_SUGERIDO, RECHAZABLE}.
- **Clase:** TRIVIAL (determinista: suma de consumo vs. techo). **Autonomía:** REVERSIBLE (propuesta; operador confirma). **Verificación:** reproducibilidad (mismo pedido + misma capacidad = misma respuesta).
- **Estado:** cero líneas; nueva funcionalidad sobre datos que ya existen.

### §3.3 Planificador — **E parcial** (la cola existe; su sistematización es D5.0)
- **Misión:** que el operador no tenga que acordarse de qué va después de qué.
- **E→P→S:** lista de pedidos confirmados para una fecha → secuenciación según reglas (LOYAL priority, urgencia, compatibilidad de receta, Setup time) → propuesta de orden al operador.
- **Clase:** ESTANDAR. **Autonomía:** propone; operador ajusta. **Verificación:** test de ordenamiento según reglas.
- **Estado:** existe como JSON (commit `57e6dcd`); sistematización = integración con bus + eventos.

### §3.4 Registrador de hitos — **P·D5.1**
- **Misión:** que el cliente y el operador sepan dónde está.
- **E→P→S:** operador marca "lote completo" (checkbox en panel, timestamp, foto opcional) → registro de hito con precisión → notificación opcional a cliente (D03).
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (operador decide cuándo registrar). **Verificación:** —.
- **Estado:** cero líneas; nueva capacidad.

### §3.5 Gestor de capacidad — **P·D5.0**
- **Misión:** que la capacidad sea parámetro vivo, no supuesto.
- **E→P→S:** cada mañana, operador declara capacidad (horas, lotes, kg) → sistema la persiste y la pone disponible para validador → al fin del día, ajusta por real vs. plan.
- **Clase:** TRIVIAL. **Autonomía:** operador declara; sistema persiste. **Verificación:** —.
- **Estado:** cero líneas; es interfaz en el panel.

### §3.6 Auditor de inventario — **P·D5.2** (post v1.0)
- **Misión:** que el inventario no se desvíe de la realidad.
- **E→P→S:** al cierre del día, suma de pedidos producidos (harina/mantequilla/etc.) vs. stock residual → alertas si hay discrepancia → propuestas de ajuste.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (análisis; ajuste manual). **Verificación:** —.
- **Estado:** cero líneas; es análisis post v1.0.

---

## §4 — MÁQUINA DE ESTADOS DEL PEDIDO EN OPERACIONES Y LÍMITES

### §4.1 Estados canónicos del pedido — FIJADO

```
PENDIENTE_CONFIRMACION → CONFIRMADO → EN_PRODUCCION → COMPLETADO → ENTREGADO_A_LOGISTICA
         ↓ rechazo
      RECHAZADO (con propuesta de reschedule)
         
EN_PRODUCCION → RETENIDO (problema, requiere decisión)
                    ↓ resuelto o escalado
                 EN_PRODUCCION (o RECHAZADO si no se puede)
```

| Estado | Significado | Quién entra | Quien sale |
|---|---|---|---|
| PENDIENTE_CONFIRMACION | Llegó de Comercial; esperando capacidad | Bus/Receptor | Validador (CONFIRMADO o RECHAZADO) |
| CONFIRMADO | Capacidad validada; entra en plan | Validador | Operador (EN_PRODUCCION) |
| EN_PRODUCCION | Se está haciendo | Operador | registra hitos, sale a COMPLETADO |
| RETENIDO | Problema (materia prima, equipo, humano) | Operador | resolución (EN_PRODUCCION, RECHAZADO, o escalación) |
| COMPLETADO | Hecho; listo para logística | Operador (hito final) | logística (ENTREGADO_A_LOGISTICA) |
| ENTREGADO_A_LOGISTICA | Fuera del horno; esperando envío | Sistema (evento físico) | consumido por D03 |
| RECHAZADO | No se pudo (capacidad, material, problema crítico) | Sistema o Operador | propuesta de reschedule a D01/D03 |

### §4.2 Invariante de saturación — FIJADO (***regla de cierre**)
Si `Σ capacidad_consumida(fecha X) ≥ capacidad_declarada(fecha X)`, la puerta se cierra: **ningún pedido más entra para esa fecha**. No hay sobrecarga. No hay "haremos esfuerzo extra". La verdad física manda.

Implementación: gate determinista en Validador (§3.2). Si cierra, Validador propone RESCHEDULE a siguiente fecha disponible.

### §4.3 Versionado de capacidad — FIJADO
Cada día tiene versión de capacidad (p. ej. "2026-07-09 v1: 50 lotes, 8h, ½ operador fuera"). Cambios = bump de versión. Trazabilidad: operador ve historial de por qué cambió.

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `operacion.pedido.recibido` | 1 | A.1 | por pedido (varios/día típico) | no | validación de bien-formedad | — | TRIVIAL |
| `operacion.capacidad.consultada` | 1 | A.2 | por validación | no | reproducibilidad (misma capacidad + pedido = misma respuesta) | — | TRIVIAL |
| `operacion.pedido.confirmado` | 1 | A.3 | post-validación OK | **sí** (para D01/D03/D04, confirma PEDIDO/REPETICION) | — | — | TRIVIAL |
| `operacion.pedido.rechazado` | 1 | A.4 | post-validación NO | **sí** (vuelve a D01 reschedule) | propuesta alternativa | — | TRIVIAL |
| `operacion.capacidad.declarada` | 1 | A.5 | diario (operador input) | no | — | — | TRIVIAL |
| `operacion.capacidad.consumida` | 1 | A.6 | por confirmación | no | suma vs. capacidad | — | TRIVIAL |
| `operacion.capacidad.saturada` | 1 | A.7 | cuando suma ≥ techo | **sí** (alerta al operador; bloquea nuevas aceptaciones) | gate determinista | — | TRIVIAL |
| `operacion.pedido.hito` | 1 | A.8 | operador registra (N por pedido) | no | timestamp + foto/qr opcional | — | TRIVIAL |
| `operacion.pedido.completado` | 1 | A.9 | post-último-hito | **sí** (consume D03 para notificación cliente; consume D04 para entrega) | — | — | TRIVIAL |
| `operacion.pedido.entregado_a_logistica` | 1 | A.10 | post-completado, pre-pickup logística | **sí** (notificación cliente, etc.) | albaran con qr | — | TRIVIAL |
| `operacion.inventario.ajustado` | 1 | A.11 | post-cierre pedido | no | auditoría de balance | — | TRIVIAL |

### §5.B — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente |
|---|---|---|
| `comercial.pedido.atribuido` (D01/D04) | **Sí** | sin él, no hay qué producir → estado ESPERANDO_PEDIDOS |
| `cliente.repeticion.respondida` SI (D03) | Sí (es otro tipo de entrada) | repetición no procesada |
| `cliente.satisfaccion.registrada` (D03, futuro) | No | sin feedback cliente no ajusta timing |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado |
|---|---|---|
| `operacion.consulta_capacidad(tenant, fecha)` | → {capacidad_total, consumida, disponible, pedidos_confirmados[]} | lectura pura |
| `operacion.proponer_secuencia(tenant, fecha)` | → orden recomendado | propuesta; operador puede reordenar |

### §5.D–F — véase §6, §8, §10

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

**FIJADO:** Operaciones es determinista en bloqueos (saturación cierra la puerta), pero flexible en ejecución (operador decide cómo y cuándo).

| Acción | Clase | CERO | BAJA (default) | MEDIA | ALTA |
|---|---|---|---|---|---|
| Recibir pedido | REVERSIBLE | propone | recibe automático | recibe | recibe |
| Validar capacidad | TRIVIAL | propone | automático (bloqueante si saturado) | automático (bloqueante) | automático (bloqueante) |
| Confirmar pedido | REVERSIBLE | operador confirma | automático OK / propuesta de reschedule | automático | automático |
| Rechazar/reschedule | REVERSIBLE | operador decide | automático propuesta; operador confirma | automático si hay alternativa libre | — |
| Declarar capacidad del día | REVERSIBLE | operador ingresa (sin asistencia) | operador ingresa; sistema propone basado en ayer | propuesta automática (historia) | — |
| Registrar hito | REVERSIBLE | operador checkbox | operador checkbox | operador o sensor (si existe) | sensor automático (iot, balanza) |
| Procesar saturación | bloqueante | avisa | **bloquea automáticamente** | **bloquea** | **bloquea** |
| Ajustar inventario | REVERSIBLE | manual | operador propone; confirma | automático si reconciliación OK | — |

---

## §7 — CUMPLIMIENTO INTEGRADO: REGLA → CONTROL → TEST

| # | Regla | Control | Test |
|---|---|---|---|
| 1 | Pedido rechazado tiene propuesta de reschedule | propuesta_alternativa campo en evento | `test_rechazo_tiene_propuesta` |
| 2 | Capacidad saturada cierra la puerta | gate determinista: suma_consumida ≥ capacidad_declarada → RECHAZADO | `test_saturacion_bloquea` |
| 3 | Hito registrado es recuperable con fecha y foto | almacén con cliente+fecha+tipo_hito como claves | `test_hito_recuperable` |
| 4 | Inventario cuadra post-cierre | suma pedidos producidos vs. stock residual con tolerancia % | `test_inventario_cuadra` |
| 5 | Secuencia respeta prioridades | LOYAL customer y URGENTE pedido aparecen antes en propuesta | `test_secuencia_prioridades` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Plan de producción, hitos, tiempos reales, inventario ajustado son **la verdad operativa** (P9). Pérdida = no saber si se hizo o no; es caos.

### §8.2 Señal P8 — FIJADO
Por cada pedido:

```
(tenant, fecha_plan, fecha_real, duracion_plan_min, duracion_real_min, producto, cantidad,
 material_gastado_vs_previsto_ratio, hitos_realizados_a_tiempo?, cliente_segment, ts)
```

Ajusta: modelos de estimación de tiempo (ajustar plan futuro), detección de problemas crónicos (máquina lenta, ingrediente defectuoso), capacidad futura (tendencias de demanda por producto).

### §8.3 Entidades y propiedad
Plan, hitos, inventario ajustado → DATO_CLIENTE (exportable). Parámetros de secuencia, recetas estandar → DATO_PLATAFORMA. Señales P8 disociadas → DATO_AGREGADO.

---

## §9 — ECONOMÍA DEL CUBO

### §9.1 Coste marginal — ABIERTO (lo cierra VR-D05-01)
Operaciones es overhead de sincronización. Su coste es tiempo del operador (revisar plan, registrar hitos, gestionar capacidad) + sustrato. Margen: cero en v1.0 (es infraestructura interna).

### §9.2 Valor agregado (P8)
Datos de desempeño + ajustes de estimación → modelo de capacidad real que mejora las promesas de Comercial. Comercial menos optimista, operador menos sorprendido. Es el feedback que hace que el sistema converja a realidad.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DEL OPERADOR

### §10.1 Kit
1. **Parámetros de capacidad:** capacidad diaria (lotes, horas, kg), inventario inicial (materia prima, envases), tiempos estándar por tipo de pedido.
2. **Reglas de secuencia:** LOYAL priority, URGENTE priority, compatibilidad de receta (no mezclar categorías seguidas).
3. **Hitos:** lista de estados (`LOTE_COMPLETO`, `EMPAQUETADO`, `LISTO_LOGISTICA`) y cómo se registran (checkbox, foto, sensor).
4. **Integración con D01:** que Comercial vea alertas de saturación (reschedule propuesto).
5. **Smoke test:** pedido ficticio entra, se confirma, registra hitos, sale a logística.

### §10.2 Superficie del operador — FIJADO
- **Panel de producción:** cola del día (pedidos confirmados en orden propuesto), capacidad restante, alertas de saturación, registro de hitos (botones).
- **Historial:** últimos 7 días con tiempos reales vs. plan, problemas registrados (RETENIDO), inventario gastado.
- **Capacidad:** input de hoy (capacidad disponible), histórico de últimas 4 semanas, tendencia.
- **No visible aquí:** datos de cliente (eso es D03), facturas (eso es D04), campañas (eso es D06).

---

## §11 — ESTADO REAL VS. DOSSIER: EL CÓDIGO EXISTE, LA INTEGRACIÓN NO

| Divergencia | Evidencia | Encuadre | Resuelve |
|---|---|---|---|
| Gestión de pedidos por JSON vive en commit sin sistematización | `departments/operaciones/` (auditoría manual) | No está integrada con el bus (no emite eventos) | **D5.0** (integración + eventos) |
| Capacidad declarada no tiene parámetro de input para operador | auditoría de `kaizen.py` | El operador no tiene forma de decir "hoy puedo hacer X" | **D5.0** (parámetro en panel) |
| No hay máquina de estados clara (estados implícitos en JSON) | JSON schema no publicado | Riesgo de incoherencia | **D5.0** (estados formales §4.1) |
| Inventario no ajustado post-cierre | auditoría de flujo | Stock se desvanece sin auditoría | **D5.2** (post v1.0) |

**Honestidad:** el código existe; su integración completa es Bloque D5.0. No es greenfield, pero tampoco está listo para producción.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES D5

Orden por dependencia: D5.0 (integración) → D5.1 (hitos + notificación) → D5.2 (inventario, post v1.0). Requiere D00-B1 ✓. Ciclo D00 §0.6; commit por bloque.

### D5.0 — Sistematización e integración con bus
1. Extracción del JSON existente en `departments/operaciones/` a modelo de datos canónico.
2. Máquina de estados formal (§4.1) con transiciones explícitas.
3. Validador de capacidad (§3.2): suma de consumo vs. techo.
4. Gestor de capacidad: operador declara capacidad diaria (panel).
5. Planificador: secuenciación de pedidos confirmados.
6. Eventos en RUE: `operacion.pedido.recibido`, `.confirmado`, `.rechazado`, etc.
7. Gates deterministas: saturación bloquea automáticamente.
8. **Puerta D5.0:** Laboratorio con ≥10 pedidos en flujo (recibido → confirmado o rechazado) + saturación detectada y bloqueando + Comercial recibiendo propuesta de reschedule + VR-D05-01 semana 1.

### D5.1 — Hitos y notificación al cliente
1. Interfaz de registro de hito (checkbox + timestamp + foto opcional).
2. Tipos de hito versionados (LOTE_COMPLETO, EMPAQUETADO, LISTO).
3. Notificación a D03 al hito "LISTO_LOGISTICA" (cliente viendo progreso).
4. Entrega a logística formal (albaran con QR).
5. **Puerta D5.1:** cliente viendo en su panel en tiempo real que su pedido está en COMPLETADO; operador registrando hitos; notificación a cliente llegando.

### D5.2 — Auditoría de inventario (post v1.0)
1. Agregación de consumo teórico (pedidos completados × receta).
2. Reconciliación con stock residual (input manual del operador o sensor).
3. Alertas si discrepancia > tolerancia %.
4. (No bloquea v1.0.)

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de tenant** | 2 tenants con pedidos/capacidad distintos | pedidos A no aparecen en cola B |
| 13.2 | **Saturación bloquea** | Capacidad = 5 lotes; intenta entrar 6º lote | 6º rechazado automático con propuesta de reschedule |
| 13.3 | **Reproducibilidad de validación** | Mismo pedido + misma capacidad, 5 intentos | 5/5 veredictos idénticos |
| 13.4 | **Secuencia respeta reglas** | 3 pedidos: 1 LOYAL, 1 URGENTE, 1 normal; secuencia propuesta | LOYAL y URGENTE aparecen antes |
| 13.5 | **Hito registrado es recuperable** | Operador registra 5 hitos; re-carga historial | 5/5 idénticos (timestamp, foto si existe) |
| 13.6 | **Inventario cuadra** | 10 pedidos producidos (cantidades conocidas); cierre | suma teórica = stock residual ± tolerancia |
| 13.7 | **Rechazo tiene propuesta** | Pedido rechazado | evento `.rechazado` contiene `propuesta_alternativa_fecha` |
| 13.8 | **Plan vs. real registrado** | Plan: 3h; operador tardó 4h20m; registra → asiento P8 | duración_real y desvío en evento |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D05-01

Pre-registro conforme a D00 Anexo II:
- **Tenant:** `alcayana` (primer tenant con operaciones reales) · **Ventana:** 2 semanas · **Acciones:** ≥15 pedidos completos (recibido → confirmado → completado).
- **Métricas y umbrales (binarios):**
  1. Todos los pedidos llegaron de D01/D03 y fueron recibidos sin pérdida.
  2. ≥1 rechazo por saturación (capacidad cerró); ≥1 propuesta de reschedule emitida y aceptada.
  3. Secuencia propuesta respetó prioridades (LOYAL/URGENTE primero).
  4. Todos los completados tienen ≥1 hito registrado con timestamp.
  5. Operador declaró capacidad cada día (input en panel, no default).
  6. Inventario: suma de consumo teórico cuadra con stock residual ±5%.
  7. Cliente viendo progreso en su panel (hitos visibles).
- **Fallo total:** pedido perdido, saturación no bloquea, hito no registrado, inventario no cuadra → aborta.

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **Pedido perdido entre D01 y producción** | evento `operacion.pedido.recibido` con timestamp; auditoría de entrada vs. almacén | test §13.1 |
| **Saturación falsa negativa** (suma falla, entra pedido extra) | gate determinista: suma_consumida ≥ capacidad → bloquea; test de suma aritmética | test §13.2 |
| **Operador no declara capacidad** (asume "como ayer") | panel con input forzado; si no llena, default = 0 (cierra todo) | D5.0 diseño: default es cero para forzar input |
| **Hito faltante; cliente no sabe dónde está su pedido** | obligatorio ≥1 hito por pedido antes de entrega a logística | gate: no sale sin al menos LISTO_LOGISTICA |
| **Inventario se desvía** (ingrediente se pierde, alguien confunde stock) | reconciliación diaria (teórico vs. real) con tolerancia; alertas | test §13.6 |
| **Rechazo sin reschedule** (cliente se entera cuando es tarde) | evento `.rechazado` contiene `propuesta_alternativa_fecha` obligatoria; D01 la procesa | test §13.7 |
| **Duración real no se registra; plan nunca mejora** | operador registra hito-final con timestamp; P8 calcula desvío | test §13.8 |

---

## §16 — PUERTA v1.0: CHECKLIST DoD Y FALSACIÓN

### §16.1 Checklist
- [ ] D5.0–D5.1 cruzados con commit y acta.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D05-01 ✓ con Laboratorio u otro tenant.
- [ ] Panel del operador con cola, capacidad restante, registro de hitos.
- [ ] Saturación bloquea automáticamente (puerta cierra, no "haremos esfuerzo").
- [ ] Rechazo tiene propuesta de reschedule a Comercial.
- [ ] Cliente viendo hitos en su panel (trazabilidad visible).
- [ ] Inventario cuadrado post-cierre (no se pierde materia prima).
- [ ] Ningún pedido perdido entre D01 y la cola.

### §16.2 Falsación
1. Pedido perdido (llegó de D01; no está en almacén) → investigar persistencia; parada.
2. Saturación no bloquea (entra 6º lote cuando cap=5) → gate roto; revisitar §4.2.
3. Hito no registrado (pedido completado sin timestamp) → arquitectura de registro falla; revisitar D5.1.
4. Inventario no cuadra >tolerancia → fricción operativa; ajustar recetas o tolerancia, no ignorar.

---

## ANEXO A — ESQUEMAS DE PAYLOAD `operacion.*` v1

- **A.1 `pedido.recibido`**: `{pedido_id, cliente_id, producto_id, cantidad, fecha_solicitada, ts_recepcion}`
- **A.2 `capacidad.consultada`**: `{fecha_consulta, capacidad_disponible, consumida_proyectada, veredicto: CONFIRMABLE|RESCHEDULE_SUGERIDO|RECHAZABLE}`
- **A.3 `pedido.confirmado`**: `{pedido_id, fecha_produccion_confirmada, secuencia_propuesta}`
- **A.4 `pedido.rechazado`**: `{pedido_id, motivo: CAPACIDAD_SATURADA|INVENTARIO_INSUFICIENTE|OTRO, propuesta_alternativa_fecha}`
- **A.5 `capacidad.declarada`**: `{fecha, capacidad_lotes, capacidad_horas, capacidad_kg, operario_referencia}`
- **A.6 `capacidad.consumida`**: `{fecha, suma_consumida, capacidad_total, disponible}`
- **A.7 `capacidad.saturada`**: `{fecha, capacidad_total, consumida, pedidos_rechazados[]}`
- **A.8 `pedido.hito`**: `{pedido_id, tipo_hito: LOTE_COMPLETO|EMPAQUETADO|LISTO_LOGISTICA, timestamp, foto_ref?, notas?}`
- **A.9 `pedido.completado`**: `{pedido_id, hitos_totales, duracion_total_min, material_gastado{}, ts_completado}`
- **A.10 `pedido.entregado_a_logistica`**: `{pedido_id, albarán_qr, peso_kg, dimensiones, cliente_entrega, direccion, ts}`
- **A.11 `inventario.ajustado`**: `{fecha, producto_id, teórico_consumido, real_gastado, stock_residual, discrepancia_pct, acta}`

---

*Fin de KAIZEN-D05 v1.0. Emitido el 2026-07-08. El cubo del choque con la realidad. Código existe (commit 57e6dcd); integración y eventos son Bloque D5.0. Saturación cierra puerta automáticamente (no hay "haremos esfuerzo"). Dependencia de arranque: D00-B1 ✓ + D01 ✓ (pedidos). Siguiente de la serie: D06 (Marketing/Demanda).*
