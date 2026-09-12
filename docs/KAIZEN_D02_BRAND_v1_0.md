# KAIZEN-D02 — DEPARTAMENTO BRAND
## Serie de dossieres departamentales KAIZEN · Documento 02

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `brand.*` (payloads en Anexo A).
**Posición estratégica:** es el primer cubo **consumidor puro** de un servicio del sustrato (`verificacion.validar_borrador`, D00 §5.4). Su éxito demostrará que los contratos de interoperabilidad funcionan en ambas direcciones: no es Comercial que produce; es Brand que consume y devuelve un veredicto.
**Estado real:** `departments/comercial/brand_guardian.py` (~80 líneas, commit `9c11c6e`). **DIVERGENTE-DIFERIDA:** funciona, pero literales de tenant (BG-257) y acoplamiento a Comercial. Recolocación arquitectónica: Bloque D2.0.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorridos E2E (validación preventiva; actualización viva)
- §2 — Anatomía del trabajo humano que replica (la coherencia como tarea estructurada)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados de las directrices y política de marca
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo
- §10 — Kit de despliegue y superficie de cliente
- §11 — Estado real vs. dossier: divergencias con evidencia
- §12 — Programa de construcción a v1.0: bloques D2
- §13 — Batería de pruebas duras
- §14 — Prueba de vida real pre-registrada (VR-D02-01)
- §15 — Riesgos de segundo orden
- §16 — Puerta v1.0: checklist DoD y criterios de falsación
- Anexo A — Esquemas de payload `brand.*` v1
- Anexo B — Semilla de directrices: el manual de marca Kaizen/Laboratorio

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan. Índice: plantilla D01.

### §0.2 Qué distingue este cubo
Brand no es marketing ni asesoría creativa. **Es la automatización de las reglas de coherencia que el dueño ya tiene en la cabeza** (o en un manual). Un dossier de marca tipifica las reglas; el cubo las ejecuta como comité preventivo. Su cliente no es el mercado: es el operador y los otros cubos. Su producto no es "tener marca": es "asegurar que todo lo que sale está dentro de las líneas".

### §0.3 Servicio-no-producto
Brand no se vende solo. **Se vende como capacidad de otro cubo** (Comercial emite borrador → Brand valida → veredicto visible en el cliente). En el contrato tipo, el Anexo III (Mandato Operacional) puede bajar autonomía si los borradores fallan la marca: eso es la presencia de Brand.

---

## §1 — MISIÓN, FRONTERA Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Brand convierte las reglas de coherencia (identidad visual, tono, líneas de producto, exclusiones) en **gates deterministas que todo contenido visible debe cruzar** antes de tocar el exterior.

### §1.2 Qué NO es — FIJADO
- **No es marketing.** No genera demanda; solo vela que la demanda que otros generen sea coherente.
- **No es asesoría creativa.** No dice "esto sería mejor", dice "esto sí o no pasa la puerta".
- **No es censura.** Las reglas las fija el cliente y el operador; el cubo solo las ejecuta.
- **No interfiere en la decisión comercial.** Un borrador que pasa marca sale; uno que la falla, no. El cliente decide si quiere cambiar la directriz o el borrador (paso 7 de D01 §1.3: aprobación humana siempre).

### §1.3 Recorrido A — LOS PASOS de la validación preventiva (consumidor de D00 §5.4)

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| V1 | Solicitud de validación: borrador de Comercial (u otro cubo) llega al servicio `verificacion.validar_borrador` con paquete de políticas = `brand` | Cubo solicitante (D01) | Sistema | — | — |
| V2 | Carga de directrices vigentes para el tenant | Guardián | Sistema | versión de directrices, parámetro tenant | — |
| V3 | Ejecución del comité de marca (presets D00 §5.2, típicamente `COMITE_LIGERO` temperatura 0) contra el borrador | Validador | Sistema | **determinista**: mismo borrador + mismo veredicto siempre | `plataforma.verificacion.emitida` |
| V4 | Categorización del veredicto: {APTO, NO_APTO_POR_MARCA, NO_APTO_POR_POLITICA, AMBIGUO} | Validador | Sistema | distintos escalados (NO_APTO → rechaza en D01 paso 6; AMBIGUO → escala a operador) | — |
| V5 | Respuesta inmediata al solicitante con: veredicto, razones itemizadas, versiones de directrices usadas, hash reproducible | Sustrato §5.4 D00 | Sistema | paquete de respuesta con firma | llamador obtiene `{veredicto, razones, version_directrices, hash}` |
| V6 | Visibilidad: el cliente (en su panel de Comercial) ve qué validaciones pasó cada contacto | Sustrato | Sistema | verificación visible §5.5 D00 | consumido por D01 view |

**Característica única (FIJADO):** Brand es el único servicio donde el veredicto NO_APTO en modo preventivo **detiene el circuito** (paso 6 de D01 rechaza de facto). Otros servicios pueden avisar; Brand cierra puerta.

### §1.4 Recorrido B — LOS PASOS de la actualización viva de directrices

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| U1 | Revisión de resultados: el operador revisa validaciones rechazadas del mes (reporte) | Operador | — | resumen de violaciones por categoría | — |
| U2 | Decisión: la regla está mal o el borrador estaba fuera de líneas | Operador | **Humano** | — | — |
| U3 | Si regla errónea: actualizar directriz (versión+1, efectiva en próxima validación) | Operador | Operador | solicitud en panel → confirmación → actualizacion | `brand.directriz.actualizada` |
| U4 | Si borrador fuera: se deja para análisis de mejora (D07 Inteligencia; futuro) | Operador | — | — | — |
| U5 | Validación retrospectiva (opcional): re-correr rechazados contra nuevas directrices (para medir efecto del cambio) | Brand | Sistema | — | `brand.validacion.retrorregistrada` |

**Característica única:** las directrices **evolucionan con la operación** sin romper la cadena (cada versión es rastreable; cero cambios silenciosos).

---

## §2 — ANATOMÍA DEL TRABAJO HUMANO QUE REPLICA

### §2.1 El trabajo de coherencia, descompuesto

| Función humana | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|
| Dueño con el manual de marca | Hojea el manual, ve si el contenido lo respeta, dice "sí" o "no" | Validador (motor de marca) |
| Administrador de marca | Actualiza el manual cuando la realidad lo exige | Gestor de directrices (input humano) |
| Revisor de consistency post-hoc | Audita lo que salió y clasifica violaciones | Analizador de patrones (futuro D07) |

### §2.2 El reparto FIJADO

- **Del cubo:** ejecución de las reglas sin sesgo, respuesta instantánea, trazabilidad del veredicto, evolución documentada de las directrices.
- **Del operador:** fijación de reglas, interpretación de violaciones, decisión de re-entrenar el motor.
- **Del cliente:** las líneas maestras del dossier de marca (identidad, paleta, tono, qué sí y qué no).

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

### §3.1 Guardián de directrices — **E** (existe como `brand_guardian.py`, recoloque en D2.0)
- **Misión:** mantener las reglas vivas y versionadas, por tenant.
- **E→P→S:** por cada solicitud de validación, carga la versión vigente de directrices (parámetro `tenant_id`) → retorna la versión exacta que va a usarse en la evaluación.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE. **Verificación:** ninguna bloqueante; es lectura.
- **Estado:** existe; BG-257 viola I3 (literal `company="laboratorio"` hardcodeado). Recoloque: parámetro tenant desde mandato/ficha §4.4 D00.

### §3.2 Validador (Comité de marca) — **E** (motor existente)
- **Misión:** ejecutar el veredicto contra borrador + directrices con temperatura 0.
- **E→P→S:** borrador (texto) + versión de directrices → aplicación de prompts versionados contra presets de comité (típicamente `COMITE_LIGERO`, temperatura 0) → veredicto {APTO, NO_APTO_POR_MARCA, NO_APTO_POR_POLITICA, AMBIGUO} con razones itemizadas.
- **Clase:** CRITICA (depende de LLM; determinismo relativo, temperature 0 + replicación). **Autonomía:** REVERSIBLE (no tiene lado effects en el mundo; solo valida). **Verificación:** reproducibilidad (mismo borrador + mismos parámetros = mismo veredicto dentro de tolerancia de modelo).
- **Estado:** existe (commit `9c11c6e`, "marca: validador básico"); categorización de veredicto es nueva.

### §3.3 Gestor de directrices — **P·D2.1**
- **Misión:** que las reglas se actualicen sin riesgo de incoherencia.
- **E→P→S:** solicitud de cambio de directriz (operador, con motivo) → validación de sintaxis/integridad → aplicación de versión+1 → timestamp → notificación a usuarios (otros cubos que las consumen).
- **Clase:** TRIVIAL. **Autonomía:** el cambio lo decide el operador; el cubo lo aplica y registra. **Verificación:** test de compatibilidad hacia atrás (nueva versión no rechaza borradores aprobados por versión anterior, salvo cambio deliberado).

### §3.4 Analizador de validaciones — **P·D2.2** (futuro, generador de señal P8)
- **Misión:** medir y avisar cuando la marca se rompe con regularidad.
- **E→P→S:** serie de validaciones del periodo → agregación de NO_APTO por categoría → trending month-on-month → alertas automáticas si supera umbral.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (análisis, no decisión). **Verificación:** —.

---

## §4 — MÁQUINA DE ESTADOS DE LAS DIRECTRICES Y POLÍTICA DE MARCA

### §4.1 Estados de una directriz — FIJADO

```
BORRADOR → ACTIVA → DEPRECADA → ARCHIVADA
  ↓         ↓
CANCELADA  SUSPENDIDA (temporal, para A/B testing)
```

| Estado | Significado | Quién entra | Salida a |
|---|---|---|---|
| BORRADOR | Nueva regla, sin validaciones aún | Operador | ACTIVA (aprobación) o CANCELADA |
| ACTIVA | Siendo usado en validaciones; versión viva | automático al pasar a activa | DEPRECADA (cambio de reemplazo), SUSPENDIDA, ARCHIVADA |
| SUSPENDIDA | Temporalmente desactivada (p. ej. A/B test) | Operador | ACTIVA (reactivar) o DEPRECADA |
| DEPRECADA | Reemplazada por otra; documentación de cambio incluida | Operador (al editar) | ARCHIVADA (histórico) |
| ARCHIVADA | Ya no activa; referencia histórica | automático | ninguno (inmutable) |
| CANCELADA | Nunca fue activa; se desestimó | Operador | ARCHIVADA |

### §4.2 Política de marca — FIJADO (en directrices, por tenant)

Estructura canónica (legible por máquina):

```yaml
Directrices v1.0:
  tenant: laboratorio
  vigencia: [2026-07-08, ~]
  validador_preset: COMITE_LIGERO
  temperatura: 0
  
  identidad:
    nombre: Repostería Laboratorio
    paleta: [#D4A574, #2C3E50, #F5EBE0, #8B4513] # Lora colors
    tipografia: [Cormorant Garamond (títulos), Poppins (body)]
  
  tono:
    - regla: "JAMÁS sobreprometer horno artesanal / tradición si es comprado de tercero"
      categoria: MARCA_CRITICA
      validacion: presencia de palabras ["artesanal", "horno", "tradición"] requiere mención de orígenes reales
    - regla: "PROHIBIDO: comparativas agresivas contra competidores (Grupo Bimbo, etc.)"
      categoria: LEGAL
    - regla: "PERMITIDO: mencionar limitaciones de producto (sólo en horno, tiempos de distribución)"
      categoria: DIFERENCIACION
  
  exclusiones:
    - palabras: ["fabricado en serie", "industrial", "mayorista barato"]
      contexto: cualquier comunicación comercial
    - imagenes: ninguna donde no aparezca horno real o producto acabado
  
  incluciones:
    - REQUERIDO: mención de zona geográfica (Cieza, Murcia) en primer párrafo
    - REQUERIDO: timestamp de disponibilidad real (ej. "pedido hasta las 14h para entrega misma semana")
```

Reglas con una estructura así son **ejecutables por un LLM determinista** (§3.2).

### §4.3 Versionado — FIJADO
Cambio aditivo (nueva regla, no toca las existentes) = bump minor (v1.0 → v1.1). Cambio disruptivo (modifica o retira regla existente) = bump major (v1.0 → v2.0) con período de deprecación de una semana (acepta ambas versiones). Retirar una versión sin período = violación de contrato, build roja (D00 §3.5).

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Servicios que OFRECE

| Servicio | Firma | Validación | Latencia esperada | Modo degradado |
|---|---|---|---|---|
| `brand.validar_borrador(tenant, borrador_texto, version_directrices?)` | borrador → {veredicto, razones[], version_usada, hash} | determinista a temperatura 0; reproducible | <2s | versión embebida (por defecto) si solicitud especifica versión ausente |

### §5.B — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `brand.validacion.emitida` | 1 | Anexo A.1 | por cada solicitud de Comercial (típicamente N contactos/día) | no | reproducibilidad (veredicto) | — | CRITICA |
| `brand.directriz.actualizada` | 1 | A.2 | cambios (típicamente 1–2/mes por tenant) | **sí** (consumida por validador para versión vigente) | transición de estado documentada | — | TRIVIAL |
| `brand.validacion.retrorregistrada` | 1 | A.3 | análisis mensual (operador solicita) | no | — | — | TRIVIAL |

### §5.C — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente |
|---|---|---|
| `comercial.contacto.preparado` (D01 solicita validación) | Sí | Comercial opera en CERO: borradores sin validar (§5.A: versión embebida default, así que degradado a validador por defecto sin la tenant-especifica) |
| `plataforma.aprobacion.concedida` (si hay cambio de directriz) | No | Cambios quedan en BORRADOR; no aplican (no es bloqueo, es que se espera confirmación) |

### §5.D — Catálogo de acciones — véase §6
### §5.E — Señal P8 — véase §8.2
### §5.F — Visibilidad de cliente — §10.3

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

**FIJADO:** Brand no expone autonomía graduada. Es un validador determinista. Su única interfaz es Comercial (u otros cubos) que la consumen. No hay "niveles de marca" para el cliente.

| Acción | Clase | Autonomía |
|---|---|---|
| Validar borrador | CRITICA | automático en todos los niveles (D01 lo consume en BAJA y MEDIA; el veredicto es el gate) |
| Actualizar directriz | REVERSIBLE | operador solicita, aprobación del operador, aplicación automática |
| Análisis retrospectivo | TRIVIAL | operador solicita, sistema ejecuta |

---

## §7 — CUMPLIMIENTO INTEGRADO: REGLA → CONTROL → TEST

| # | Regla | Control | Test |
|---|---|---|---|
| 1 | Determinismo: mismo borrador + directrices = mismo veredicto | Temperatura 0; replicabilidad a través de hashs | `test_veredicto_reproducible` |
| 2 | Versionado sin rotura: nueva versión no rechaza lo que v anterior aprobó (salvo cambio deliberado) | compatibilidad hacia atrás con flags de deprecación | `test_version_compatible` |
| 3 | No existe secreto: directrices legibles, prompts versionados, auditoría de cambios | archivo en repo (versionado en git) | `test_directrices_en_repo` |
| 4 | Transporte de decisión: veredicto viaja a D01 con hash para trazabilidad ante cliente | campo `hash_veredicto` en evento | `test_veredicto_con_hash` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Directrices, versiones, cambios y sus efectos son **la verdad del posicionamiento de marca del tenant** (P9). Consecuencias: export histórico de directrices; rastreabilidad de cada versión.

### §8.2 Señal P8 — FIJADO
Por cada validación:

```
(tenant, categoria_borrador, resultado: APTO|NO_APTO_MARCA|NO_APTO_POLITICA|AMBIGUO, razon_principal, ts)
```

Ajusta: priorización de temas en una próxima A/B, identificación de falsas positivas en el validador.

### §8.3 Entidades y propiedad
Directrices y su historial → DATO_CLIENTE (exportable a la baja). Validaciones (borradores de tercero) → DATO_PLATAFORMA (jamás visible al cliente, solo resultado del veredicto). Señales P8 disociadas → DATO_AGREGADO.

---

## §9 — ECONOMÍA DEL CUBO

### §9.1 Coste marginal (ABIERTO, lo cierra VR-D02-01)
Brand es un gatekeep a servicios del sustrato (`verificacion.validar_borrador`). Su coste incremental es la fracción que la llamada al comité representa en la clase CRITICA. Margen: cero en v1.0 (es parte de la estructura de Comercial).

### §9.2 Ventaja de permuta (P8)
Las señales de validación retroalimentan al pipeline de Inteligencia (D07, futuro): "qué rechaza, con qué frecuencia, cuándo cambió". Eso es insumo de precio para el cliente; Brand produce ese insumo como side-effect.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DE CLIENTE

### §10.1 Kit de despliegue
1. **Dossier de marca del tenant:** estructura §4.2 (cliente la rellena o cede el manual que tiene).
2. **Validación de sintaxis:** que las reglas sean ejecutables (lista blanca de operadores, qué palabras/imágenes se permiten, etc.).
3. **Test de reproducibilidad:** correr 5 borradores ficticios contra la directriz; verificar veredictos idénticos en N pasadas.
4. **Integración con Comercial:** la respuesta del servicio viaja vía evento `brand.validacion.emitida` hasta D01.
5. **Superficie del operador:** panel de directrices vivas, historial de cambios, alertas de violaciones.

### §10.2 Superficie de cliente — FIJADO
- **Lectura:** historial de validaciones (borrador X pasó/falló marca, con razones).
- **No edición:** las directrices las fija el operador, el cliente solo las ve reflejadas en los veredictos.

---

## §11 — ESTADO REAL VS. DOSSIER: DIVERGENCIAS CON EVIDENCIA

| Divergencia | Evidencia | Encuadre | Resuelve |
|---|---|---|---|
| Brand Guardian en Comercial, BG-257 literal de tenant | `departments/comercial/brand_guardian.py:257` | Violación I3; acoplamiento; recoloque necesario | **D2.0** (arquitectura) |
| Validador existe pero no categoriza veredictos | commit `9c11c6e`, ~80 líneas | Sumar categorización y razones itemizadas | **D2.1** (extensión) |
| Directrices no versionadas en el código | auditoría manual | Las directrices viven en tensor/prompt; no hay SoT | **D2.0** (adopción de estructura §4.2) |
| Análisis retrospectivo no existe | no hay trace de validaciones fallidas | Funcionalidad nueva | **D2.2** (futuro post v1.0) |

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES D2

Orden por dependencia: D2.0 (arquitectura) → D2.1 (cubo) → D2.2 (operación). Requiere D00-B1 ✓. Ciclo D00 §0.6; commit por bloque.

### D2.0 — Recoloque arquitectónico (quitar Brand de Comercial)
1. Extracción de Brand Guardian de `departments/comercial/` a módulo independiente.
2. Parametrización de tenant (quitar literal `company="laboratorio"`).
3. Integración con servicio del sustrato `verificacion.validar_borrador` (D00 §5.4).
4. Test de no-regresión: brand_guardian funciona idéntico en su ubicación nueva.
5. **Puerta D2.0:** Brand Guardian reubicado, tests en verde, D01 consume Brand vía servicio (ya no importa el módulo).

### D2.1 — Cubo Brand v1.0
1. Estructura de directrices ejecutables (§4.2 en YAML legible por máquina).
2. Categorización de veredictos (APTO, NO_APTO_POR_MARCA, NO_APTO_POR_POLITICA, AMBIGUO).
3. Razones itemizadas en cada veredicto.
4. Gestor de directrices: cambio de versión, trazabilidad, notificación.
5. Reproducibilidad: mismo borrador → mismo veredicto (test §7.1).
6. Eventos en RUE: `brand.validacion.emitida`, `.directriz.actualizada`.
7. **Puerta D2.1:** Laboratorio (o primer tenant) con dossier de marca en forma ejecutable; 10 validaciones reproducibles; VR-D02-01.

### D2.2 — Análisis de validaciones (opcional, post v1.0)
1. Agregación de violaciones por mes y categoría.
2. Alertas automáticas si tasa de NO_APTO supera umbral.
3. Reporte para operador y acceso a D07 (Inteligencia).
4. (No bloquea v1.0.)

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de tenant** | 2 tenants con directrices distintas; mismo borrador validado contra cada una | veredictos distintos y correctos (no hay derrame) |
| 13.2 | **Reproducibilidad** | Mismo borrador + directrices, 20 validaciones | 20/20 identical verdicts (temperature 0) |
| 13.3 | **Cambio de versión sin rotura** | Versión vía aprobada 100 borradores; v1.1 con regla nueva → re-validar los 100 contra v1.1 | los 100 aprueban o fallan por la nueva regla únicamente (ninguno pierde aprobación por regla antigua) |
| 13.4 | **Categorización correcta** | Corpus de borradores marcados correctamente {APTO, NO_APTO_MARCA, NO_APTO_POLITICA, AMBIGUO} | categorización al 100% (precisión, recall) |
| 13.5 | **Trazabilidad del veredicto** | 50 validaciones; extracción de hashes; verificación de que cada hash es único y registrado en evento | 50/50 únicos, 50/50 en evento |
| 13.6 | **Interfaz de servicio** | D01 solicita validación; respuesta contiene {veredicto, razones, version, hash} | todas las cuatro presentes; latencia <2s |
| 13.7 | **Cambio de directriz sin efecto retroactivo indeseado** | Cambio de regla sobre versionado intencionalmente periódico; borradores históricos siguen usando su versión | ningún borrador anterior re-evaluado sin solicitud |
| 13.8 | **Directrices in versioncontrol** | Copia de directrices actuales de 3 tenants; git blame de cada cambio | auditoría de cambios íntegra; rastreabilidad al minuto |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D02-01

Pre-registro conforme a D00 Anexo II:
- **Tenant:** `laboratorio` (o primer tenant de producción) · **Ventana:** 2 semanas de operación de Comercial normal · **Acciones:** N ≥ 20 borradores validados contra dossier de marca.
- **Métricas y umbrales (binarios):**
  1. 100% de borradores enviados tuvieron validación Brand (no saltaron el gate).
  2. Reproducibilidad (§13.2): mismos 5 borradores, 5 validaciones cada uno = 5/5 veredictos idénticos.
  3. Cliente viendo en su panel qué borradores pasaron / fallaron marca.
  4. Operador con acceso a historial de cambios de directriz, cero silent updates.
- **Fallo total:** cualquier veredicto irreproducible o algún borrador sin validación registrada → aborta.

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **Derivera de directrices** (tenant olvida actualizarlas; reglas devient obsoletas) | Recordatorio mensual + trending de NO_APTO → alerta | D2.2 cuando exista |
| **Falsos positivos** (regla rechaza textos válidos) | A/B testing: suspender regla temporalmente; medir impacto | estado SUSPENDIDA (§4.1) |
| **Directrices confusas** (operador no las entiende) | Dossier de marca en lenguaje natural + estructura ejecutable paralela | ambas formas de la verdad §4.2 |
| **Caché de veredictos** (mismo borrador querries cambios pero recibe respuesta antigua) | Invalidación de caché al cambiar versión de directrices | evento `.directriz.actualizada` desata invalidación |
| **Rendimiento** (validaciones lentas con N alta) | Caché de veredictos comunes por tenant | D2.1 puede iterar aquí si es necesario |

---

## §16 — PUERTA v1.0: CHECKLIST DoD Y FALSACIÓN

### §16.1 Checklist
- [ ] D2.0–D2.1 cruzados con commit y acta.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D02-01 ✓ con tenant real.
- [ ] Dossier de marca en forma ejecutable (§4.2) para al menos 1 tenant.
- [ ] Comercial consumiendo Brand vía servicio del sustrato (no importa, no import).
- [ ] Cliente viendo sus validaciones (trazabilidad visible).
- [ ] Reproducibilidad documentada: mismos inputs → mismos outputs.

### §16.2 Falsación
1. Veredicto irreproducible (temperatura fluctúa a pesar de 0) → volver a dossier; investigar determinismo del modelo.
2. Tenant A ve veredictos de tenant B (fuga de aislamiento) → pausa; investigar D00-B2 (lección: no es culpa de D02).
3. Cambio de directriz rompe borradores aprobados históricos → revisitar versionado (§4.3 hay guardrail, pero puede fallar).

---

## ANEXO A — ESQUEMAS DE PAYLOAD `brand.*` v1

- **A.1 `validacion.emitida`**: `{borrador_id, tenant_id, veredicto: APTO|NO_APTO_MARCA|NO_APTO_POLITICA|AMBIGUO, razones: [{regla_id, descripcion}], version_directrices, hash_reproducible}`
- **A.2 `directriz.actualizada`**: `{tenant_id, directriz_id, version_anterior, version_nueva, cambio_descripcion, ts_efectiva, }`
- **A.3 `validacion.retrorregistrada`**: `{tenant_id, periodo, borradores_reevaluados, cambios_de_veredicto[{borrador_id, version_anterior, version_nueva}]}`

---

## ANEXO B — SEMILLA DE DIRECTRICES: MANUAL DE MARCA KAIZEN/LABORATORIO

Ejemplo ejecutable (formato §4.2):

```yaml
Directrices v1.0:
  tenant: laboratorio
  vigencia: [2026-07-08, ~]
  validador_preset: COMITE_LIGERO
  temperatura: 0
  
  IDENTIDAD:
    nombre_legal: Repostería Laboratorio
    nombre_marca: Laboratorio
    claim: "Horno de leña, tradición sin atajos"
    paleta_color:
      primario: "#D4A574"    # Lora (pan tostado)
      secundario: "#2C3E50"  # Carbon (estabilidad)
      accent: "#8B4513"      # Marrón oscuro (horno)
      neutral: "#F5EBE0"     # Crema
    tipografia:
      titulos: "Cormorant Garamond, serif"
      body: "Poppins, sans-serif"
    imagenes_requeridas:
      - horno de leña en frame
      - producto acabado con zoom
  
  TONO:
    - id: "MARCA.ARTESANIA"
      regla: "JAMÁS usar 'artesanal' sin contexto de horno real o tiempo real"
      palabras_prohibidas_solas: [artesanal, hecho a mano, tradicional]
      palabras_requeridas_con: [horno leña, Cieza Murcia, horneado]
      categoria: MARCA_CRITICA
      accion: NO_APTO_POR_MARCA
    
    - id: "LEGAL.COMPETENCIA"
      regla: "PROHIBIDO: menciones directas de competidores"
      palabras_prohibidas: [Grupo Bimbo, Bimbo, Industrial, "pan de fábrica"]
      categoria: LEGAL
      accion: NO_APTO_POR_POLITICA
    
    - id: "DIFERENCIACION.LIMITACIONES"
      regla: "PERMITIDO: ser claro sobre limitaciones (solo horno, tiempo distribución)"
      palabras_permitidas: [distribuimos hasta X km, bajo pedido, tiempo espera]
      categoria: PERMITIDA
      accion: APTO
    
    - id: "IDENTIDAD.GEOGRAFIA"
      regla: "REQUERIDO: mención de zona en primer párrafo"
      busqueda: primer 100 caracteres debe incluir [Cieza, Murcia] o equivalente
      categoria: MARCA_IMPORTANTE
      accion: AMBIGUO (advertencia, pero no rechaza)
  
  EXCLUSIONES:
    imagenes:
      - "pan cortado con máquina automática"
      - "fábrica o línea de producción"
    palabras:
      - fabricado en serie
      - producción industrial
      - mayorista
  
  INCLUSIONES:
    timestamps:
      - "disponible hasta las 14h para entrega misma semana"
      - "bajo pedido, plazo: [N] días"
```

*Fin de KAIZEN-D02 v1.0. Emitido el 2026-07-08. Primer cubo consumidor puro de un servicio del sustrato (`verificacion.validar_borrador`). Su éxito demuestra que los contratos de interoperabilidad funcionan bidireccionalamente. Recoloque arquitectónico de Brand Guardian es D2.0 (no entra en el programa si no se hace limpia la separación). Dependencia de arranque: D00-B1 ✓ + D00-B6 ✓ (el servicio de validación). Siguiente de la serie: D03 (Atención al Cliente).*
