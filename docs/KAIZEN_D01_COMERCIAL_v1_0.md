# KAIZEN-D01 — DEPARTAMENTO COMERCIAL
## Serie de dossieres departamentales KAIZEN · Documento 01 · Plantilla de la serie

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0 (sobre de evento §3.2, RUE §16, autonomía §4, verificación §5, coste §6, cumplimiento §8.4). Este dossier es, además, la **prueba de uso** de la plantilla de interoperabilidad de D00: si su §5 no puede rellenarse sin fricción, el defecto es de D00 (checklist D00 §15.1).
**Propietario en el RUE de:** todos los tipos `comercial.*` (payloads en Anexo A).
**Vertical de referencia:** HORECA/obrador (célula Laboratorio). El cubo es vertical por construcción (P2); los parámetros de vertical (§10.2) son datos de despliegue, no código.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorrido E2E de un lead (LOS PASOS)
- §2 — Anatomía del trabajo humano que replica
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados del pipeline y definición formal de Pedido Atribuible
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo: coste de servir, unidades facturables, las tres cifras
- §10 — Kit de despliegue y superficie de cliente
- §11 — Estado real vs. dossier: divergencias con evidencia
- §12 — Programa de construcción a v1.0: bloques C0–C7
- §13 — Batería de pruebas duras del departamento
- §14 — Pruebas de vida real pre-registradas (VR-D01-01, VR-D01-02)
- §15 — Riesgos de segundo orden: riesgo → control → evidencia
- §16 — Puerta v1.0: checklist DoD comercial y criterios de falsación
- Anexo A — Esquemas de payload de los eventos `comercial.*` v1

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Qué es este documento

La especificación ejecutable del primer cubo vendible de Kaizen y la **plantilla estructural** de D02–D08: el índice de este dossier es el índice obligatorio de la serie. Hereda de D00 sin repetirlo: convención de estados (D00 §0.2), precedencia código>dossier>intención (D00 §0.3), ciclo de vida y reglas R1–R4 (D00 §0.6). Lo que D00 garantiza (G1–G5) aquí se **usa**, no se reconstruye.

### §0.2 Base de evidencia

El estado real citado procede de: la auditoría total del 2026-07-02 (hallazgos publicados con archivo:línea), el historial de commits (citados por hash) y la validación de campo documentada en la Tesis (llamada real de 89 s con transcript canónico; corpus 466 leads → 258 llamables → top-60 con dossieres; benchmark sectorial 6–10% de conversión llamada→pedido). Donde el detalle interno de `departments/comercial/` exceda lo publicado por la auditoría, el **Bloque C0** (inventario) produce el mapeo exhaustivo real→canon antes de tocar código: este dossier no rellena huecos por inferencia (R4).

### §0.3 Relación con los contratos firmados

Tres cláusulas de papel se convierten aquí en propiedades del sistema:

| Papel | Sistema |
|---|---|
| Contrato Laboratorio cl. 2.2–2.3 (Pedido Atribuible, repetición 12 meses, beneficio neto) | §4.4 — atribución con cadena causal verificable por hash; ventana de repetición como dato |
| Contrato tipo cl. 3.2 + Anexo II (variable por resultado) | §9.3 — unidades facturables medidas por el libro de coste/eventos, no estimadas |
| Contrato tipo cl. 4 + Anexo III (autonomía y aprobaciones) | §6 — la matriz de este dossier ES el contenido técnico del Anexo III |
| LIA §3 (salvaguardas 1–10) | §7 — cada salvaguarda con su control determinista y su test |

---

## §1 — MISIÓN, FRONTERA Y RECORRIDO E2E DE UN LEAD

### §1.1 Misión en una frase

El cubo Comercial da a una microempresa la **estructura de prospección y memoria comercial de un departamento**, dirigida por las personas que ya tiene: encuentra, investiga, contacta con permiso, recuerda todo, detecta compromisos y atribuye pedidos — con cada acción externa verificada y trazable.

### §1.2 Qué NO es — FIJADO

- **No cierra ventas.** El cierre, el precio y la relación son del cliente y del operador (P7; lección Klarna, Tesis §5).
- **No promete condiciones.** Ningún rol del cubo emite compromisos vinculantes hacia fuera; los *detecta* y los registra para que un humano los confirme (lección Air Canada, Anexo A §A3 de la Tesis).
- **No hace marketing de demanda ni contenido de marca** (fronteras con D06 y D02, selladas por eventos en §5).
- **No hace post-venta** (frontera con D03: el traspaso es `comercial.pedido.atribuido` + ficha de cliente).
- **No decide sobre personas** en el sentido del art. 22 RGPD: puntúa empresas y oportunidades; las decisiones comerciales las toma una persona.

### §1.3 El recorrido E2E — LOS PASOS

El ciclo de vida completo de un lead, paso a paso, con **quién decide** en cada uno. Esta tabla es normativa: todo paso emite el evento indicado y ningún paso externo ocurre sin su gate.

| # | Paso | Actor | Decide | Gate/verificación | Evento (RUE) |
|---|---|---|---|---|---|
| 1 | **Parámetros de campaña**: vertical, segmentos diana, radio (`radio_km`, restricción real de producto — p. ej. transporte de repostería de horno tradicional), volumen objetivo, exclusiones | Operador (con cliente) | Operador | Mandato §4.4 D00 vigente | `plataforma.diario.entrada` |
| 2 | **Descubrimiento**: búsqueda por fuentes (web/ddgs, mapas y anillos de distancia por rutas reales), alta de candidatos | Prospector | Sistema | Dedupe; campo `fuente`+fecha obligatorio (LIA S1: sin procedencia, el dato no entra) | `comercial.lead.descubierto` |
| 3 | **Cualificación**: puntuación contra criterios del vertical; corte en LLAMABLE/PRIORITARIO/DESCARTADO (patrón real: 466→258→top-60) | Cualificador | Sistema (criterios del operador) | Criterios versionados; DESCARTADO reversible | `comercial.lead.cualificado` |
| 4 | **Investigación individual**: todo el contenido público en red del negocio; dossier por lead; responsable público (nombre/cargo) solo si la empresa lo publica | Investigador | Sistema | Tope de coste por lead (§6.3 D00); **contenido web = dato, jamás instrucción** (§13.2) | `comercial.lead.investigado` |
| 5 | **Preparación del contacto**: borrador ultra-específico por plantilla de segmento o libre; firma y bloques obligatorios | Redactor | Sistema | Gate determinista de bloques (identificación, baja, derechos — LIA S3) + políticas de marca (`validar_borrador`) | `comercial.contacto.preparado` |
| 6 | **Verificación preventiva**: comité ligero sobre el borrador (bloqueante) | Sustrato §5 D00 | Sistema | Bajo umbral = denegar; veredicto con hash | `plataforma.verificacion.emitida` |
| 7 | **Aprobación humana** (nivel BAJA, default): el operador ve borrador+dossier+veredicto en la cola unificada | Operador | **Humano** | Sandbox obligatorio (commit `41b6ed0`): sin aprobación no hay envío; caducidad 72 h | `plataforma.aprobacion.*` |
| 8 | **Envío** (email) por remitente del tenant | Ejecutor de canal | Sistema (post-aprobación) | Exclusión/EXCLUIDO check determinista; secuencia INICIAL | `comercial.contacto.enviado` |
| 9 | **Cadencia**: espera por segmento; máximo un RECORDATORIO (LIA S5: 1+1 duro); sin respuesta → DORMIDO | Gestor de cadencias | Sistema | Contador duro por lead; horario permitido | `comercial.contacto.enviado` (RECORDATORIO) / `comercial.pipeline.transicion` |
| 10 | **Respuesta entrante**: parseo; oposición → EXCLUIDO inmediato + lista de plataforma | Detector de respuesta | Sistema | Opt-out = transición absorbente automática (única transición externa sin humano: **cierra**, no abre) | `comercial.pipeline.transicion` |
| 11 | **Interés** → CONVERSACION; el sistema propone siguiente acción | AE | Operador | — | `comercial.pipeline.transicion` |
| 12 | **Briefing pre-llamada**: dossier + historial + objetivo de la llamada, en una pantalla | AE/Briefing | Sistema | — | `comercial.briefing.emitido` |
| 13 | **Llamada humana del operador** (modelo célula: Iván llama; el sistema prepara, registra, recuerda y escala). Voz IA: sub-agente opcional, hoy OFF (§8.3 D00) | **Humano** (o Voz, OFF) | Humano | Si IA: Robinson + prefijo + disclosure primer turno; cuota diaria del mandato | `comercial.llamada.realizada` |
| 14 | **Detección de compromisos** sobre transcript/respuesta (motor existente validado contra transcript real, commit `cbb4ddd`) | CompromisoDetector | Sistema propone | Gate determinista de confirmación: acción+fecha extraídas ≠ compromiso hasta validación | `comercial.compromiso.detectado` |
| 15 | **Confirmación del compromiso** (crea recordatorios y rituales del AE) | Operador | **Humano** | — | `comercial.compromiso.creado` → COMPROMETIDO |
| 16 | **Pedido**: el cliente lo sirve; el sistema lo registra con su cadena causal | Cliente + Atribuidor | Cliente (hecho) / Sistema (atribución) | §4.4: cadena verificable; sin cadena → PENDIENTE_VALIDACION | `comercial.pedido.atribuido` → PEDIDO |
| 17 | **Traspaso económico**: el hecho atribuible viaja a Finanzas para liquidación (50/50 Laboratorio o variable del contrato tipo) | Bus | — | Consumidor D04 (degradado: informe manual §5.B) | consumido por D04 |
| 18 | **Repetición**: pedidos del mismo cliente final ≤ ventana (12 meses, contrato) se atribuyen como REPETICION | Atribuidor | Sistema | Ventana como dato del tenant | `comercial.pedido.atribuido` |
| 19 | **CUSTOMER**: primer pedido servido y cobrado; ficha de cliente estable; traspaso a D03 cuando exista | Sistema | — | Señal de cobro (D04) o confirmación manual | `comercial.pipeline.transicion` |
| 20 | **Señal del bucle (P8)**: por cada contacto/llamada se captura (segmento, argumento, canal, resultado, tiempo-a-respuesta) → ajusta ranking de argumentos y cadencias del vertical | Sustrato+cubo | Sistema | Frontera de disociación §9.2 D00 para todo uso cross-tenant | asiento P8 (§8.2) |
| 21 | **Reporting**: briefing diario/semanal al Director y vista de cliente con resultado en unidades verificables | Briefing | — | Verificación visible §5.5 D00 | `comercial.briefing.emitido` |

**Regla de lectura de la tabla (FIJADO):** los pasos 7, 13, 15 y la validación de 16 son humanos por diseño, no por inmadurez del sistema. Subir autonomía (§6) mueve el *cómo* de la aprobación (individual→lote→mandato), nunca elimina el gate determinista de las acciones IRREVERSIBLE-EXTERNA.

---

## §2 — ANATOMÍA DEL TRABAJO HUMANO QUE REPLICA

### §2.1 El departamento comercial humano, descompuesto

| Función humana (pyme mediana) | Coste real España 2026 (Anexo A de la Tesis) | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|---|
| SDR / prospector | ~2.900–3.200 €/mes (junior, coste empresa) | Busca, criba, primer contacto, persigue respuestas | Prospector + Cualificador + Redactor + Gestor de cadencias |
| Account Executive | > SDR | Prepara reuniones, gestiona relación, recuerda compromisos, empuja al cierre | AE + CompromisoDetector + Briefing (el cierre queda en humanos) |
| Back-office comercial | parte de un administrativo | Registra, actualiza el CRM (cuando existe), liquida comisiones | Pipeline + Atribuidor (+ D04) |
| Analista de mercado | inexistente en micro | Sabe qué competidor cobra qué y a quién | Investigador (por lead) + D07 (por mercado, cuando exista) |

### §2.2 El reparto FIJADO entre humanos y cubo

- **Del cubo:** memoria perfecta, volumen sin fatiga (258 llamables sin agenda perdida), investigación previa exhaustiva, cumplimiento trazable, disciplina de cadencia, atribución honesta.
- **Del operador:** la voz y la relación (paso 13), el criterio de aprobación (paso 7), la dirección de campaña (paso 1), la confirmación de compromisos (paso 15).
- **Del cliente:** producto, precio, servicio, cierre y la palabra dada.

El argumento de venta correcto (Anexo A §A2.3, ya fijado): *estructura de departamento al precio de una fracción de persona, dirigida por la persona que ya tienes*. Vender sustitución sería repetir Klarna; este dossier lo hace imposible por construcción: los pasos humanos son invariantes.

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

Formato por rol: misión · entrada→proceso→salida · clase de tarea (D00 §6.2) · autonomía por defecto · verificación · estado.

### §3.1 Prospector — **E** (prospección real E2E verificada, commit `931c38c`)
- **Misión:** convertir parámetros de campaña en candidatos con procedencia.
- **E→P→S:** parámetros del paso 1 → búsqueda multi-fuente (web vía `ddgs`, commit `16dac0b`; mapas y **anillos de distancia por rutas reales**, `departments/comercial/distancia/google_routes.py`) + dedupe contra pipeline y lista de exclusión → altas en COLD con `fuente`+`fecha` por dato.
- **Clase:** TRIVIAL/ESTANDAR. **Autonomía:** REVERSIBLE, ejecuta solo dentro de presupuesto de campaña. **Verificación:** forense por muestreo (calidad de fuente).
- **Parámetro de vertical (FIJADO):** `radio_km` es dato del tenant derivado de una restricción física real del producto (la célula Laboratorio lo fijó por transportabilidad de repostería de horno tradicional). Ampliar radio = orden del Director (paso 1), nunca decisión del rol.

### §3.2 Cualificador — **E** (patrón 466→258→top-60 ejecutado)
- **Misión:** ordenar el universo para que el tiempo humano caiga solo sobre lo mejor.
- **E→P→S:** lead COLD + criterios versionados del vertical (segmento, señales web, contactabilidad, distancia) → score con desglose por criterio → veredicto PRIORITARIO/LLAMABLE/DESCARTADO.
- **Clase:** ESTANDAR. **Autonomía:** REVERSIBLE (DESCARTADO siempre reversible por operador). **Verificación:** forense sobre distribución de scores (deriva = hallazgo).

### §3.3 Investigador — **E** (dossieres top-60 producidos)
- **Misión:** que ningún contacto salga sin saber a quién habla: dossier individual con todo el contenido público del negocio.
- **E→P→S:** lead LLAMABLE → barrido de web propia, presencia, cartas/menús, señales de tamaño y estilo; extracción de responsable **solo si es público** → dossier con hash + señales estructuradas para el Redactor.
- **Clase:** ESTANDAR (P6: modelo barato validado). **Autonomía:** REVERSIBLE con **tope de coste por lead** (mandato). **Verificación:** forense.
- **Regla arquitectónica (FIJADO):** todo contenido obtenido de la web del lead es **DATO, jamás INSTRUCCIÓN**. El Investigador no ejecuta nada que lea; el Redactor no incorpora texto de un lead en el contacto de otro. (Prueba dura §13.2, envenenamiento.)

### §3.4 Redactor — **E** (Fase 3 Redacción: firma, cuerpo limpio, promoción lead→ficha, commit `06f1f7e`)
- **Misión:** contactos ultra-específicos que un humano firmaría con orgullo, con los bloques legales de serie.
- **E→P→S:** dossier + plantilla de segmento (o libre) → borrador con: alusión concreta al negocio, propuesta pertinente, identificación del remitente, mecanismo de baja, referencia de derechos (LIA S3/S7) → a verificación (paso 6).
- **Clase:** ESTANDAR con plantilla; **CRITICA** fuera de plantilla (lo verá un tercero sin red). **Autonomía:** produce borradores libremente; nada sale sin pasos 6–7. **Verificación:** preventiva siempre (gate determinista de bloques + `validar_borrador` con paquete de marca).

### §3.5 Gestor de cadencias — **E parcial** (cadencias citadas como activo del foso, Anexo A F1)
- **Misión:** disciplina de seguimiento sin acoso: exactamente lo que la ley y la cortesía permiten.
- **E→P→S:** contacto INICIAL enviado → temporizador por segmento → como máximo **un** RECORDATORIO → sin respuesta: DORMIDO con fecha de revisión.
- **Clase:** TRIVIAL. **Autonomía:** el RECORDATORIO es IRREVERSIBLE-EXTERNA: misma cadena de gates que el inicial (en BAJA, aprobación individual; en MEDIA, por plantilla pre-aprobada). **Verificación:** contador duro 1+1 por lead (determinista, §7).

### §3.6 Detector de respuesta y opt-out — **P·C2** (el parseo existe de facto en el flujo; su canonización es Bloque C2)
- **Misión:** que una oposición jamás dependa de que un humano la lea a tiempo.
- **E→P→S:** entrante (reply, formulario, verbal registrado) → clasificación {OPOSICION, NEGATIVA, POSITIVA, AMBIGUA} → OPOSICION: EXCLUIDO + lista de plataforma **en el acto**; AMBIGUA: al operador.
- **Clase:** ESTANDAR. **Autonomía:** la única transición automática hacia fuera del embudo (V1, §4.2): cierra, no abre. **Verificación:** batería §13.3 con corpus adversario.

### §3.7 CompromisoDetector — **E, validado contra transcript real** (commit `cbb4ddd`; llamada de 89 s como caso canónico)
- **Misión:** que nada de lo dicho se pierda y nada de lo no dicho se invente.
- **E→P→S:** transcript/respuesta → propuestas {acción, fecha, condiciones, confianza} con extracto citado → gate determinista: sin acción+fecha extraíbles y confirmación humana (paso 15), no hay compromiso.
- **Clase:** ESTANDAR. **Autonomía:** propone; jamás comunica al lead. **Verificación:** corpus de validación con precisión/recall pre-registrados — **ABIERTO** (C0 construye el corpus ≥30 casos con trampas: condicionales, negaciones, fechas relativas; hoy existe **una** validación real — una validación no es una suite).

### §3.8 Account Executive (AE) — **E** (rituales, commit `cbb4ddd`)
- **Misión:** la memoria y el ritmo de la relación: próximos pasos, recordatorios, escalado, briefing pre-llamada (paso 12).
- **Clase:** ESTANDAR. **Autonomía:** REVERSIBLE (agenda interna); toda comunicación externa vuelve por el circuito 5→8. **Verificación:** forense.

### §3.9 Atribuidor — **P·C1** (la definición formal §4.4 es nueva; el pipeline y el historial existen)
- **Misión:** convertir "este pedido vino del sistema" de opinión a hecho verificable por hash.
- **E→P→S:** pedido registrado (operador/cliente/canal) → reconstrucción de cadena causal por `correlacion_id` en bitácora → tipo DIRECTA/REPETICION/REGISTRO_EXTERNO → evento con la cadena adjunta.
- **Clase:** TRIVIAL (determinista puro). **Autonomía:** DIRECTA y REPETICION automáticas con cadena completa; REGISTRO_EXTERNO queda PENDIENTE_VALIDACION hasta confirmación del operador. **Verificación:** la cadena ES la verificación; visible para el cliente (§10.3) — la transparencia sobre el dinero es el foso aplicado.

### §3.10 Briefing — **E** (motor de briefing citado en superficie de configuración de la auditoría)
- **Misión:** el estado en una pantalla: pre-llamada (paso 12), diario del tenant, semanal del Director.
- **Clase:** TRIVIAL/ESTANDAR. **Autonomía:** REVERSIBLE. **Verificación:** ninguna bloqueante; es lectura.

### §3.11 Voz IA (sub-agente **opcional**) — **E en código, OFF por palanca** (V0 con aviso legal Twilio, commit `8cbf768`; gate D00 §8.3)
- **Misión (cuando se reactive):** llamadas de cualificación/agenda con revelación de naturaleza IA en el primer turno; **jamás** negociación ni promesas.
- **Gates duros:** disclosure verificado por test en despliegue + Lista Robinson pre-llamada + numeración/prefijo vigente + cuota diaria del mandato (hoy 25) + horario. Sin los cuatro, la palanca no abre (D00 B7).
- **Posición estratégica (FIJADO, Tesis §9):** la voz es opcional por diseño; el cubo vale completo sin ella. Cada endurecimiento regulatorio del canal voz es argumento contra el competidor que improvisa, no una amenaza al cubo.

---

## §4 — MÁQUINA DE ESTADOS DEL PIPELINE Y PEDIDO ATRIBUIBLE

### §4.1 Estados canónicos — FIJADO

```
COLD → CONTACTADO → CONVERSACION → COMPROMETIDO → PEDIDO → CUSTOMER
Laterales: DORMIDO · DESCARTADO · EXCLUIDO (absorbente)
```

| Estado | Significado | Entrada por | Salida a |
|---|---|---|---|
| COLD | Descubierto y cualificado; sin contacto | paso 2–3 | CONTACTADO, DORMIDO, DESCARTADO, EXCLUIDO |
| CONTACTADO | ≥1 contacto saliente vivo (INICIAL o RECORDATORIO) | paso 8 | CONVERSACION, DORMIDO, EXCLUIDO |
| CONVERSACION | Respuesta positiva/neutra; diálogo abierto | paso 10–11 (o inbound directo COLD→CONVERSACION) | COMPROMETIDO, DORMIDO, DESCARTADO, EXCLUIDO |
| COMPROMETIDO | ≥1 `compromiso.creado` vigente | paso 15 | PEDIDO, CONVERSACION (compromiso vencido), EXCLUIDO |
| PEDIDO | ≥1 `pedido.atribuido` | paso 16 | CUSTOMER, EXCLUIDO |
| CUSTOMER | Pedido servido y cobrado (señal D04 o confirmación manual) | paso 19 | (relación viva; repeticiones §4.4; traspaso D03) |
| DORMIDO | Pausa deliberada con fecha de revisión | cadencia agotada / decisión | COLD/CONVERSACION al despertar |
| DESCARTADO | No encaja (criterio) | paso 3 / operador | reversible por operador |
| EXCLUIDO | Opt-out, Robinson, exigencia legal | **cualquier estado** | **ninguno** (absorbente; reapertura solo con consentimiento expreso documentado) |

### §4.2 Invariantes — FIJADO (todas con test en C1)

- **V1:** la transición →EXCLUIDO existe desde todo estado y es **automática e inmediata** ante oposición (paso 10). Única transición externa sin humano: cierra el canal, no lo abre.
- **V2:** ningún contacto saliente a lead en EXCLUIDO o DORMIDO (gate determinista pre-envío/pre-llamada; violarlo es imposible, no "prohibido").
- **V3:** COMPROMETIDO exige compromiso vigente; vencido sin pedido → vuelve a CONVERSACION con señal al AE.
- **V4:** PEDIDO exige `pedido.atribuido` con cadena; CUSTOMER exige señal de cobro (degradado sin D04: confirmación manual del operador, registrada).
- **V5:** transición fuera del grafo = rechazada y registrada (`pipeline.transicion` con veredicto `rechazado`); el grafo solo se amplía por reevaluación de este dossier.
- **V6:** todo cambio de estado lleva `disparador ∈ {SISTEMA, OPERADOR, EVIDENCIA, OPTOUT}` y `causa_ref` — la máquina de estados es determinista; el LLM propone, la máquina decide (patrón anti-McDonald's).

### §4.3 Mapeo con el código real — DIVERGENTE (resuelve C0)

El pipeline COLD→CUSTOMER existe (Anexo A F2 de la Tesis lo cita como activo del foso) y la promoción lead→ficha está commiteada (`06f1f7e`). Los nombres y el conjunto exacto de estados en código no constan en los hallazgos publicados de la auditoría: **C0 produce la tabla estado-real → estado-canónico** con archivo:línea; toda divergencia se documenta y la migración, si la hay, se hace con test de equivalencia sobre el historial existente (ningún lead pierde su pasado).

### §4.4 Pedido Atribuible — definición formal (FIJADO; hace ejecutable el contrato)

Un pedido es atribuible si y solo si cumple una de las tres vías:

1. **DIRECTA:** existe en la bitácora del tenant una cadena causal íntegra con el mismo `correlacion_id` desde un evento de origen del sistema (`lead.descubierto` o primer `contacto.enviado`/`llamada.realizada`) hasta `pedido.atribuido`, verificable por el encadenado de hash (D00 §3.4). La cadena viaja **dentro** del evento (campo `cadena[]`).
2. **REPETICION:** pedido del mismo cliente final con primer pedido atribuible previo, dentro de la **ventana del tenant** (dato de contrato; Laboratorio: 12 meses desde el primero, cl. 2.2). Automática.
3. **REGISTRO_EXTERNO:** pedido llegado por fuera del canal pero de un lead existente del sistema (cláusula anti-puenteo). Nace `PENDIENTE_VALIDACION`: exige lead en pipeline + declaración con fecha + confirmación del operador. Nunca se auto-atribuye.

**Propiedades:** sin doble atribución (un `pedido_id`, una vía, un lead); disputable con evidencia — ambas partes ven la cadena (la verificación visible aplicada al dinero: §10.3); la liquidación (50/50 o variable) es de D04 y **consume** este evento, jamás lo recalcula.

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia esperada | Outbox | Verificación | Cumplimiento (D00 §8.4) | Coste |
|---|---|---|---|---|---|---|---|
| `comercial.lead.descubierto` | 1 | Anexo A.1 | decenas–cientos/campaña | no | forense muestreo | procedencia S1 | TRIVIAL |
| `comercial.lead.cualificado` | 1 | A.2 | = descubiertos | no | forense (deriva de score) | — | ESTANDAR |
| `comercial.lead.investigado` | 1 | A.3 | = llamables | no | forense | S1/S2 (fuentes, contacto corporativo) | ESTANDAR |
| `comercial.contacto.preparado` | 1 | A.4 | = contactos previstos | no | **preventiva** (gate bloques + marca + comité ligero) | S3, S7 | ESTANDAR/CRITICA |
| `comercial.contacto.enviado` | 1 | A.5 | ≤ límites de mandato | **sí** | post-aprobación §4.3 D00 | S3–S5, exclusión V2 | canal |
| `comercial.llamada.realizada` | 1 | A.6 | humana: sesiones; IA: OFF | **sí** | gates de voz §3.11 | S6, art. 50 | canal |
| `comercial.compromiso.detectado` | 1 | A.7 | por conversación | no | gate determinista + humano | — | ESTANDAR |
| `comercial.compromiso.creado` | 1 | A.8 | confirmados | **sí** | humano (paso 15) | — | TRIVIAL |
| `comercial.pipeline.transicion` | 1 | A.9 | continuo | no | invariantes V1–V6 | V1/V2 (opt-out) | TRIVIAL |
| `comercial.pedido.atribuido` | 1 | A.10 | el que importa | **sí** | cadena causal §4.4 | — | TRIVIAL |
| `comercial.briefing.emitido` | 1 | A.11 | diario/semanal/pre-llamada | no | — | — | TRIVIAL |

### §5.B — Eventos/servicios que CONSUME

| Origen | Obligatorio | Modo degradado si ausente | Idempotencia |
|---|---|---|---|
| `plataforma.aprobacion.concedida/denegada/revocada/caducada` (D00) | **Sí** para toda IRREVERSIBLE-EXTERNA | **No hay degradado que abra**: sin cola de aprobación, el cubo opera en CERO (propone, nada sale). La seguridad degrada cerrando. | por `aprobacion_id` |
| `verificacion.validar_borrador` (servicio D00 §5.4) con paquete de marca | Sí (preventivo) | Paquete de marca del tenant ausente → **versión embebida por defecto** (P1); servicio caído → borradores quedan en PREPARADO, nada avanza a aprobación | síncrono |
| `plataforma.verificacion.emitida` (comité) | Sí en paso 6 | = anterior: retención, jamás bypass | por `event_id` |
| `plataforma.coste.techo_alcanzado` (D00) | No | Escalera §6.3 D00 la aplica el sustrato; el cubo solo ajusta prioridades de cola | por `event_id` |
| `finanzas.cobro.registrado` (D04) | No | Sin D04: CUSTOMER por confirmación manual del operador (V4); liquidación por informe mensual manual desde `pedido.atribuido` | por `event_id` |
| `brand.politicas` (servicio D02, futuro) | No | Embebido por defecto hasta que el tenant contrate Brand — el arranque sin dependencias es contractual, no aspiracional | síncrono versionado |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado | Nota |
|---|---|---|---|
| `comercial.consulta_pipeline(tenant, filtros)` | → leads+estados+historial | lectura pura; sin efectos | Base de la vista de cliente §10.3 y del NLQ del Director |
| `comercial.registrar_pedido_externo(tenant, lead_id, evidencia)` | → PENDIENTE_VALIDACION | — | La puerta anti-puenteo del contrato, como API |

### §5.D — Catálogo de acciones × clase — véase §6 (tabla única, evita duplicidad)
### §5.E — Señal P8 — véase §8.2
### §5.F — Visibilidad de cliente — véase §10.3

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

Contenido técnico del Anexo III del contrato tipo. Clases según D00 §4.1; niveles según D00 §4.2. **Default de todo tenant nuevo: BAJA.**

| Acción | Clase | Gates deterministas (siempre, en todo nivel) | CERO | BAJA (default) | MEDIA | ALTA |
|---|---|---|---|---|---|---|
| Descubrir/cualificar/investigar lead | REVERSIBLE | presupuesto campaña; tope coste/lead; procedencia | propone lista | auto | auto | auto |
| Preparar borrador | REVERSIBLE | bloques obligatorios; marca; comité ligero | auto | auto | auto | auto |
| **Enviar email INICIAL** | **IRR-EXT** | exclusión V2 + bloques + verificación preventiva | no sale | aprobación **individual** | por **plantilla pre-aprobada** y lote diario del mandato | mandato + límites; excepciones escalan |
| **Enviar RECORDATORIO** | **IRR-EXT** | contador 1+1 + los del inicial | no sale | individual | plantilla | mandato |
| **Llamada IA** | **IRR-EXT** | palanca OFF; si ON: Robinson+prefijo+disclosure+cuota+horario | — | individual | plantilla de guion | no disponible sin historial MEDIA sin incidentes |
| Transición de pipeline (grafo §4.1) | REVERSIBLE | invariantes V1–V6 | propone | auto (grafo) | auto | auto |
| **Transición →EXCLUIDO por opt-out** | especial | V1 | **auto en todos los niveles** (cierra) | auto | auto | auto |
| Crear compromiso | REV→IRR-EXT al comunicarse | gate acción+fecha; confirmación | propone | confirmación humana (paso 15) | confirmación humana | confirmación humana — **no sube con el nivel** |
| Atribuir pedido DIRECTA/REPETICION | REVERSIBLE (registro) | cadena íntegra / ventana | propone | auto con cadena | auto | auto |
| Validar REGISTRO_EXTERNO | IRR-INT (afecta liquidación) | evidencia mínima | humano | humano | humano | humano — **no sube** |
| Despertar DORMIDO / revertir DESCARTADO | REVERSIBLE | fecha revisión | propone | operador | operador | auto con criterio del mandato |
| Export/borrado de datos del tenant | IRR-INT | primitivas D00 §9.3 con acta | humano | humano | humano | humano |

**Candado (herencia D00 §4.2):** los roles solo endurecen. Y dos filas están selladas por diseño: compromisos y validación externa **no se automatizan con el nivel** — son exactamente los puntos donde los cinco fracasos célebres del Anexo A de la Tesis metieron probabilística sin gate.

---

## §7 — CUMPLIMIENTO INTEGRADO: REGLA → CONTROL → TEST

P5 hecho tabla ejecutable. Cada fila termina en un test con nombre en la suite (C2 los implementa; §13 los ataca).

| # | Regla (fuente) | Control determinista en el cubo | Test |
|---|---|---|---|
| 1 | Procedencia registrada (LIA S1) | Alta de dato de contacto **rechaza** sin `fuente`+`fecha` | `test_lead_sin_fuente_no_entra` |
| 2 | Solo contacto profesional (LIA S2, art. 19 LOPDGDD) | Se admite el contacto **que el negocio publica** (aunque sea buzón genérico); se rechaza el personal de tercero no vinculado; responsable con nombre solo si es público, con fuente | `test_contacto_no_publicado_rechazado` |
| 3 | Identificación + baja + derechos en primera comunicación (LIA S3/S7, LSSI) | Gate de **bloques obligatorios**: el envío es imposible si el cuerpo no contiene los tres bloques (comprobación estructural, no LLM) | `test_envio_sin_bloques_imposible` |
| 4 | Oposición = supresión inmediata + exclusión (LIA S4, art. 21 RGPD) | V1 automática + lista de plataforma (dato mínimo, indefinida) consultada pre-envío/pre-llamada | `test_optout_absorbente`, `test_lista_exclusion_gate` |
| 5 | Cadencia máxima 1+1 (LIA S5) | Contador duro por lead; el tercer contacto **no existe** como ruta de código | `test_tercer_contacto_inexistente` |
| 6 | Robinson + numeración/prefijo + horario en llamadas (LIA S6) | Gates en la ruta de llamada; sin consulta Robinson registrada no hay marcación; ventana horaria del mandato | `test_llamada_sin_robinson_imposible` |
| 7 | Disclosure IA primer turno (art. 50, desde 02-08-2026) | Palanca de voz condicionada al test de despliegue (D00 §8.3) | `test_voz_sin_disclosure_no_abre` |
| 8 | Retención 12 meses sin relación (LIA S8) | Job de retención del sustrato aplicado a leads sin transición en ventana; acta | `test_retencion_leads` |
| 9 | Sin decisiones automatizadas art. 22 (LIA S10) | Los scores puntúan **empresas/oportunidades**; toda decisión con efecto sobre persona pasa por humano (matriz §6) | revisión C2 + acta |
| 10 | No puenteo / atribución honesta (contratos) | §4.4 vía 3: PENDIENTE_VALIDACION obligatorio | `test_registro_externo_no_autoatribuye` |

**Efecto de mercado (FIJADO, Tesis P5):** esta tabla, exportada con sus tests en verde, es el "pack de cumplimiento" que se enseña al cliente y, si toca, a la AEPD. Para el competidor extranjero es fricción; aquí es una sección del dossier.

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
El pipeline, el historial por lead, los compromisos y la cadena de atribución son **la verdad comercial del tenant** (P9: el cubo es sistema de registro o no es cubo). Consecuencias operativas: export completo a la baja (D00 §2.4) incluye leads, historial, compromisos, dossieres y cadenas; sustituir a Kaizen = perder la memoria del departamento, y esa gravedad de datos es coste de cambio que no colapsa con el tiempo de ingeniería (Anexo A, F2).

### §8.2 La señal del bucle — FIJADO (instrumentación en C3)
Por cada contacto y llamada se captura un asiento P8:

```
(tenant, segmento, argumento_id/plantilla_id, canal, secuencia,
 resultado ∈ {SIN_RESPUESTA, NEGATIVA, POSITIVA, COMPROMISO, PEDIDO},
 t_respuesta, ts)
```

**Ajusta:** ranking de argumentos por segmento (qué convierte en qué perfil), cadencia por segmento (cuándo insistir), priorización del Cualificador. **Frontera (D00 §9.2):** el uso cross-tenant solo admite (vertical, segmento, tipo_argumento, tasas) disociados — jamás textos con datos ni identidades. Un competidor con el mejor modelo del año no hereda las llamadas reales a hosteleros de la zona: el activo lo fabrica el tiempo de operación, no la inteligencia (Data Moat 2.0).

### §8.3 Entidades y propiedad
`Lead`, `Ficha de cliente`, `Contacto`, `Compromiso`, `Pedido`, `Dossier` → DATO_CLIENTE. `Plantillas y argumentario genérico del vertical` → DATO_PLATAFORMA. `Asientos P8 disociados` → DATO_AGREGADO. Sin ambigüedades: cada tabla del almacén lleva su clase.

---

## §9 — ECONOMÍA DEL CUBO: COSTE DE SERVIR, UNIDADES, LAS TRES CIFRAS

### §9.1 Coste de servir — instrumento (cierra la cifra ABIERTA nº 1)
```
coste_servir(tenant, mes) = Σ asientos LLM (cubo=comercial)         [libro D00 §6.1]
                          + coste de canal (email/telefonía imputada)
                          + prorrata de sustrato (≤15%, D00 §15.2)
                          + horas de operador imputables al tenant (registro de sesiones)
```
Sale del libro y del registro de sesiones, no de una estimación. Primer informe real: puerta C4. El precio definitivo del cubo (banda FIJADA 250–900 €/mes, Tesis §4.3) se decide **solo** con este número delante; criterio de falsación heredado: coste de servir estructural >40% del precio de banda = consultoría disfrazada, no plataforma.

### §9.2 Valor generado — instrumento (cifra nº 2)
`Σ beneficio_neto(pedidos atribuibles del mes)` con costes directos del **Anexo I del contrato Laboratorio** (por eso su cumplimentación es condición del primer devengo). El cubo aporta los pedidos y su cadena; los márgenes los aporta el papel firmado.

### §9.3 Unidades facturables candidatas (Anexo II del contrato tipo) — ABIERTO hasta C4/VR-01
Variable por `pedido.atribuido` (preferente: counter-positioning que el SaaS por asiento no puede copiar, Anexo A F5) · por `compromiso.creado` · tramos de leads activos. La elección final exige coste medido y un mes de operación real; queda pre-registrada como salida de VR-D01-01.

### §9.4 Presupuestos operativos
Del mandato del tenant: techo diario €, tope €/lead investigado, límites de envíos/llamadas. La escalera de techo es del sustrato (D00 §6.3); el cubo solo reordena su propia cola al recibirla.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DE CLIENTE

### §10.1 Por qué el kit es sección obligatoria — FIJADO
La cifra ABIERTA nº 3 de la Tesis (tiempo de segundo despliegue < 20% del primero) es la diferencia entre producto y artesanía. El kit convierte lo que hoy es memoria del operador en checklist cronometrable; **cada despliegue se cronometra por fase** desde el primero, o la cifra 3 nunca tendrá denominador.

### §10.2 Checklist de despliegue de un tenant en el cubo Comercial
1. **Alta administrativa:** ficha en registro de tenants (D00 §2.3) + mandato inicial (BAJA, techos, horarios, ventana de repetición) + contrato firmado con Anexos I–III cumplimentados.
2. **Canales:** remitente y dominio del tenant (o subdominio de envío) con SPF/DKIM/DMARC verificados; warm-up si el dominio es nuevo; teléfono saliente si habrá voz (hoy no). *(La deliverability es infraestructura del producto: un dominio quemado es un cubo muerto — §15.)*
3. **Carga de vertical:** argumentario del sector, segmentos diana con criterios de cualificación, `radio_km` y restricción de producto que lo justifica, precios/condiciones verificados del cliente, competencia mapeada. Formato: paquete de vertical versionado (DATO_PLATAFORMA parametrizado + DATO_CLIENTE).
4. **Plantillas:** juego inicial por segmento con bloques obligatorios integrados; aprobación del cliente de las plantillas MEDIA-elegibles.
5. **Cumplimiento:** LIA referenciada con datos del tenant, entrada en el RAT, capa informativa publicada (URL), lista de exclusión conectada.
6. **Panel:** vista de cliente activada (§10.3); credencial de solo lectura entregada.
7. **Smoke E2E en dry-run:** un lead sintético recorre los 21 pasos sin salida real; acta.
8. **Primera sesión real supervisada:** campaña acotada (N pequeño) con el operador delante; revisión a 48 h.

### §10.3 Superficie de cliente — FIJADO (sobre D00 §7.3, contenido de este cubo)
El tenant ve, en solo lectura: su pipeline por estados con historial por lead · contactos realizados con su verificación (qué gate pasó cada envío) · compromisos vigentes y vencidos · **pedidos atribuidos con su cadena causal legible** · el informe mensual en unidades de resultado (contactos, compromisos, pedidos), no en "actividad de IA". La transparencia sobre la atribución es el argumento que desarma la objeción "¿y cómo sé que vino de vosotros?" antes de que exista.

### §10.4 Material de venta del cubo
One-pager del cubo Comercial (problema→estructura→prueba→precio) + el caso Laboratorio con cifras cuando F1 lo publique + el pack de cumplimiento §7 como anexo técnico para el comprador cauto. **ABIERTO:** redacción final tras VR-01 (el caso manda sobre el copy).

---

## §11 — ESTADO REAL VS. DOSSIER: DIVERGENCIAS CON EVIDENCIA

| Hallazgo | Evidencia | Encuadre | Resuelve |
|---|---|---|---|
| Brand Guardian fuerza `company="laboratorio"` | `departments/comercial/brand_guardian.py:257` (auditoría) | Violación I1/I3 del sustrato; el guardián se recoloca como paquete de políticas por tenant del servicio `validar_borrador` | **D00-B1** (el fix), D02 (la recolocación) |
| Colisión CLI deja inalcanzables aprobación de envíos y disparo de voz (~1.000 líneas) | `kaizen.py:1365` vs `:276` (auditoría) | Rotura de la superficie G5 sobre las rutas de ESTE cubo | **D00-B1** + walk de comandos permanente |
| Teléfono de contacto con fallback hardcodeado en guion de voz | `KAIZEN_TELEFONO_CONTACTO` (auditoría, catálogo de hardcodes) | Violación I3 (config por tenant) | **C0** cataloga todos los hardcodes del cubo; **C2** los migra a mandato/ficha |
| Estados reales del pipeline sin mapeo publicado | auditoría §6 no citada en detalle | §4.3 | **C0** (tabla real→canon con archivo:línea) |
| CompromisoDetector validado contra **un** transcript | commit `cbb4ddd` + Tesis (llamada 89 s) | Una validación no es una suite | **C0** (corpus ≥30 con trampas) + §13.4 |
| Disclosure de voz sin confirmar en despliegue | auditoría (redeploy pendiente) | Voz OFF; gate D00 §8.3 | **D00-B7**; aquí solo se hereda |
| Cadencias: activo citado, implementación no auditada en detalle | Anexo A F1 | §3.5 | **C0** inventario; **C2** contador duro |

Regla viva: esta tabla se actualiza en cada AUDITORIA_D01; una fila DIVERGENTE sin dueño y bloque es una violación de R4.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES C0–C7

Dependencias externas: **C1+ requieren D00-B1 cruzado** (bugs quirúrgicos); C6 requiere D00-B6. Ciclo D00 §0.6; commit por bloque (R1); sin fechas: puertas.

- **C0 — Inventario y corpus.** Mapeo estados reales→canon, catálogo real de acciones, catálogo de hardcodes del cubo, corpus del detector (≥30 casos con trampas: condicionales, negaciones, fechas relativas, compromisos de tercero). **Puerta:** tablas con archivo:línea; corpus etiquetado y congelado; **cero código nuevo**.
- **C1 — Pipeline canónico + Atribuidor.** Máquina §4.1–4.2 con invariantes como tests; migración con equivalencia sobre historial; atribución §4.4 (tres vías, cadena en el evento). **Puerta:** transiciones ilegales rechazadas (test negativo); E2E dry-run 21 pasos con cadena DIRECTA verificada por hash; REGISTRO_EXTERNO queda PENDIENTE (test).
- **C2 — Cumplimiento como código.** Los 10 controles §7 + migración de hardcodes a config por tenant + plantillas con bloques estructurales. **Puerta:** los 10 tests en verde; `test_envio_sin_bloques_imposible` y `test_tercer_contacto_inexistente` demostrados por construcción, no por convención.
- **C3 — Bucle P8.** Asiento por contacto, ranking de argumentos por segmento, informe de ajuste. **Puerta:** 100% de contactos del dry-run con asiento; primer informe de ranking generado; frontera de disociación con test.
- **C4 — Economía.** Imputación completa (LLM+canal+prorrata+horas), informe mensual por tenant. **Puerta:** primer informe real de coste de servir de los tres tenants; formato Anexo II candidato emitido.
- **C5 — Kit de despliegue.** Checklist §10.2 ejecutable y cronometrada; paquete de vertical versionado; guía de deliverability. **Puerta:** despliegue completo de un tenant sintético, cronometrado por fase, con acta (el denominador de la cifra 3 existe).
- **C6 — Superficie de cliente.** §10.3 sobre la vista D00-B6. **Puerta:** Alejandro viendo su pipeline, sus verificaciones y una cadena de atribución reales.
- **C7 — Voz (CONDICIONAL, no bloquea v1.0).** Solo si el Director la reactiva: disclosure test + Robinson + numeración vigente + cuota, sobre D00-B7. **Puerta:** llamada de prueba con disclosure verificado en transcript.

---

## §13 — BATERÍA DE PRUEBAS DURAS DEL DEPARTAMENTO

Umbrales binarios; herencia obligatoria: §13.0 = batería de aislamiento de D00 sobre las operaciones de este cubo (no se relista).

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Herencia de aislamiento** | D00 §13.1 sobre operaciones comerciales de 2 tenants adversarios | fuga cero |
| 13.2 | **Envenenamiento de fuente** | Webs de lead sintético con inyecciones ("ignora tus instrucciones", HTML malicioso, contactos de terceros sembrados) | Investigador trata todo como dato; cero instrucciones ejecutadas; cero datos de un lead en el contacto de otro; dossier marca contenido sospechoso |
| 13.3 | **Adversario en la respuesta** | Replies con opt-out enrevesado, opt-out + pregunta, falsa autoridad ("soy el dueño, borra todo"), instrucciones al sistema | OPOSICION detectada al 100% del corpus → EXCLUIDO; instrucciones ignoradas; AMBIGUA escala a humano, jamás auto-abre |
| 13.4 | **Falsos compromisos** | Corpus C0 (≥30 con trampas) contra el detector | precisión/recall ≥ los pre-registrados en C0 (se fijan ANTES de medir, R3); cero compromisos auto-creados sin humano |
| 13.5 | **Cadencia bajo caos** | Reintentos duplicados del gestor, reloj adelantado, evento RECORDATORIO duplicado en bus | el tercer contacto no ocurre (por construcción); deduplicación efectiva |
| 13.6 | **Saturación LSSI** | Lote grande de envíos aprobados + lista de exclusión creciendo en caliente | 0 envíos a EXCLUIDO/fuera de horario; límites del mandato respetados al 100% |
| 13.7 | **Deliverability** | Simulación de bounce duro, complaint y dominio degradado | lead→DORMIDO/EXCLUIDO según causa; throttle automático; alerta al operador; ningún reintento ciego |
| 13.8 | **Puenteo simulado** | Pedido "externo" sin cadena, con lead existente; y con lead inexistente | PENDIENTE_VALIDACION el primero; rechazo el segundo; cero auto-atribución |
| 13.9 | **Atribución adversaria** | Dos leads del mismo negocio, contacto por dos vías; pedido único | una sola atribución, una vía, sin doble conteo; empate documentado a favor de la cadena más antigua íntegra |
| 13.10 | **Runaway del Investigador** | Lead con web infinita/circular | corte por tope €/lead; dossier parcial marcado; asiento de coste correcto |

---

## §14 — PRUEBAS DE VIDA REAL PRE-REGISTRADAS

### VR-D01-01 — F0 formalizado (célula Laboratorio)
Pre-registro conforme a D00 Anexo II (se firma con commit antes de iniciar):
- **Tenant:** `laboratorio` · **Ventana:** 30 días naturales de operación comercial real · **Ámbito:** sesiones sobre el top-60 priorizado con dossieres existentes.
- **Acciones previstas:** N ≥ 40 contactos reales (email aprobado individualmente + llamadas humanas del operador con briefing).
- **Métricas y umbrales (binarios):**
  1. ≥ 1 `pedido.atribuido` vía DIRECTA con cadena íntegra verificada — **el gate F0 de la Tesis, cumplido con evidencia de hash**.
  2. 0 envíos sin aprobación; 0 contactos a EXCLUIDO/DORMIDO; 0 terceros contactos (cumplimiento 100%).
  3. 100% de contactos con asiento P8; primer ranking de argumentos emitido.
  4. Informe de coste de servir del mes (cifra 1) y de valor generado con márgenes del Anexo I firmado (cifra 2) — **las dos cifras dejan de ser ABIERTAS**.
  5. Cliente usando la vista §10.3 (≥1 sesión registrada de Alejandro).
- **Referencia externa, no umbral:** benchmark sectorial 6–10% conversión llamada→pedido (se compara, no se exige: N=40 no da potencia estadística; la Tesis exige el primer pedido, no una tasa).
- **Fallo total:** cualquier incumplimiento de la métrica 2 → aborta, corrige, re-ensaya.

### VR-D01-02 — Replicabilidad (cifra nº 3)
- **Tenant:** el primer HORECA distinto de `laboratorio` que entre en operación comercial — candidato natural hoy: `rial` (ya dado de alta como tenant); alternativa: Meritxell (pendiente de alta administrativa).
- **Pre-registro:** tras el acta de VR-01 (el kit C5 debe existir); **umbral:** tiempo total de despliegue cronometrado ≤ 20% del esfuerzo Laboratorio reconstruido en C5 + primer contacto real aprobado saliendo por el circuito completo.
- **Qué decide:** si Kaizen es producto o proyectos (criterio de falsación nº 3 de la Tesis §8.3, ahora con instrumento).

---

## §15 — RIESGOS DE SEGUNDO ORDEN: RIESGO → CONTROL → EVIDENCIA

| Riesgo | Control | Evidencia de que funciona |
|---|---|---|
| **Puenteo** (pedidos por fuera para evitar el variable) | Cláusula contractual + vía REGISTRO_EXTERNO fácil + señal de discrepancia (actividad alta sobre un lead + silencio de pedidos → aviso al operador) | §13.8 + informe de discrepancias en VR-01 |
| **Quema de dominio** (deliverability) | Subdominio de envío, warm-up, límites del mandato, monitor de bounce/complaint con throttle | §13.7 + métricas de entrega en VR-01 |
| **Falsos compromisos** (prometer lo no dicho) | Gate determinista + confirmación humana sellada en la matriz §6 + corpus | §13.4 |
| **Saturación/reputación LSSI** | 1+1 duro, exclusión indefinida, horario, tono del Redactor verificado por marca | §13.6 + cero quejas en VR-01 |
| **Inyección desde fuentes/replies** | Regla dato≠instrucción (§3.3) + sandboxing del Investigador | §13.2–13.3 |
| **Dependencia del operador único** | Todo retomable por dossier+bitácora; autonomía graduada reduce horas/tenant; el briefing es la memoria externa | horas de operador/tenant medidas en C4, decrecientes entre VR-01 y VR-02 |
| **Calidad/frescura de fuentes** | Procedencia+fecha obligatorias; caducidad de dossieres (re-investigar > X meses) | forense sobre muestra |
| **Estacionalidad HORECA** | Señal P8 por mes en cadencias; DORMIDO con fecha estacional | ranking C3 segmentado por temporada (dato, no opinión) |

---

## §16 — PUERTA v1.0: CHECKLIST DoD COMERCIAL Y FALSACIÓN

### §16.1 Checklist (todo binario)
- [ ] C0–C6 cruzados con commit y acta (C7 solo si voz reactivada).
- [ ] Batería §13 en verde con salidas archivadas; herencia §13.1 incluida.
- [ ] **VR-D01-01 superado**: F0 de la Tesis cumplido con cadena de hash; cifras 1 y 2 medidas y publicadas en REEVALUACION_D01.
- [ ] **Comprable:** precio y unidades del Anexo II fijados con el coste medido delante (banda 250–900 respetada o desviación justificada con número).
- [ ] **Onboardeable:** kit C5 con cronometraje; VR-D01-02 pre-registrado (su ejecución abre la v1.1, no bloquea la v1.0 si aún no hay segundo tenant operando — la cartera manda, NC-2026-07-08).
- [ ] **Operable:** un tenant real en BAJA con cola de aprobación unificada, mandato aplicado.
- [ ] **Visible:** cliente real usando su vista con atribución legible.
- [ ] Pack de cumplimiento §7 exportable con sus 10 tests en verde.
- [ ] Tabla §11 sin filas DIVERGENTE sin dueño; dossier actualizado a la verdad construida (bump §0.7 D00).

### §16.2 Falsación del cubo (heredada de la Tesis §8.3, ahora con instrumentos)
1. Coste de servir estructural > 40% del precio de banda (medido ≥2 meses en C4) → no hay plataforma, hay consultoría disfrazada: rediseñar coste (P6) antes de vender más.
2. VR-02 ≥ 20% del esfuerzo del primero → no hay producto, hay proyectos: el kit vuelve a dossier.
3. La verificación visible no altera ninguna decisión de compra en las 10 primeras ventas → el foso elegido no es foso: reposicionar (§10.4) con los datos de por qué compraron.
4. El detector no alcanza sus umbrales pre-registrados en dos iteraciones de corpus → la detección vuelve a fase de diseño; mientras tanto opera en modo propuesta-con-extracto obligatorio (más fricción, cero invención).

---

## ANEXO A — ESQUEMAS DE PAYLOAD `comercial.*` v1

Campos del sobre (D00 §3.2) omitidos; solo payload. `?` = opcional. Todo `_ref` es hash/URI a objeto en el almacén del tenant.

- **A.1 `lead.descubierto`**: `{lead_id, nombre, segmento?, ubicacion{municipio, distancia_km}, contacto{web?, email?, tel?}, fuentes[{tipo, url, fecha}], score_inicial?}`
- **A.2 `lead.cualificado`**: `{lead_id, score, criterios[{id, valor, peso}], veredicto: PRIORITARIO|LLAMABLE|DESCARTADO, criterios_version}`
- **A.3 `lead.investigado`**: `{lead_id, dossier_ref, señales[{tipo, valor, fuente_url}], responsable_publico?{nombre, cargo, fuente_url}, coste_investigacion_ref}`
- **A.4 `contacto.preparado`**: `{lead_id, contacto_id, canal: EMAIL, plantilla_id?|LIBRE, borrador_ref, bloques_ok: true, marca_veredicto_ref, comite_ref?}`
- **A.5 `contacto.enviado`**: `{contacto_id, lead_id, canal, secuencia: INICIAL|RECORDATORIO, aprobacion_id, remitente_id, ts_envio}`
- **A.6 `llamada.realizada`**: `{lead_id, llamada_id, tipo: HUMANA|IA, duracion_s, transcript_ref?, resultado: {SIN_CONTACTO|CONVERSACION|COMPROMISO_PROPUESTO|NEGATIVA}, robinson_ref? (IA), disclosure_ok? (IA)}`
- **A.7 `compromiso.detectado`**: `{lead_id, origen{tipo: TRANSCRIPT|REPLY, ref}, extracto, propuesta{accion, fecha?, condiciones?}, confianza}`
- **A.8 `compromiso.creado`**: `{compromiso_id, lead_id, accion, fecha, responsable: OPERADOR|CLIENTE|LEAD, origen_evento_id}`
- **A.9 `pipeline.transicion`**: `{lead_id, de, a, disparador: SISTEMA|OPERADOR|EVIDENCIA|OPTOUT, causa_ref, veredicto: APLICADA|RECHAZADA}`
- **A.10 `pedido.atribuido`**: `{pedido_id, lead_id, cliente_final_id, fecha_pedido, importe_bruto?, via: DIRECTA|REPETICION|REGISTRO_EXTERNO, estado: ATRIBUIDO|PENDIENTE_VALIDACION, cadena[event_id...], ventana_repeticion_hasta}`
- **A.11 `briefing.emitido`**: `{ambito: PRE_LLAMADA|DIARIO|SEMANAL, destinatario: OPERADOR|CLIENTE, contenido_ref, leads_incluidos[]}`

Versionado y deprecación: reglas D00 §3.5; propietario de cambios: este dossier.

---

*Fin de KAIZEN-D01 v1.0. Emitido el 2026-07-08 declarando contra KAIZEN-D00 v1.0. Estado real citado por auditoría (archivo:línea) o commit (hash); lo demás, ABIERTO o DIVERGENTE con dueño y bloque. Este índice es la plantilla obligatoria de D02–D08. Dependencia de arranque: D00-B1. Primer trabajo derivado propio: C0 (inventario y corpus), que no escribe código: mide. Siguiente dossier de la serie por reloj de mercado: KAIZEN-D04 (Finanzas/Verifactu, fecha legal 01-01-2027).*
