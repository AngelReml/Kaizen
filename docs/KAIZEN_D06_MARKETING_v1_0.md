# KAIZEN-D06 — DEPARTAMENTO MARKETING
## Serie de dossieres departamentales KAIZEN · Documento 06

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `marketing.*` (payloads en Anexo A).
**Entrada:** parámetros de campaña (vertical, segmentos, objetivos de visibilidad).
**Consumidor clave:** D01 (Comercial) recibe leads candidatos; D07 (Inteligencia) alimenta ajustes de targeting.
**Diferencia estratégica:** es el cubo **generador de señal, no conversor**. Comercial vende; Marketing genera oportunidades. Si Marketing propone que "este segmento X es bueno", debe ser verificable con datos, no intuición.
**Estado real:** cero líneas de código. Greenfield puro. Existe marca de Laboratorio (Manual de Marca, commit varias) y estrategia de contenido (Anexo A de la Tesis F4: canal gestorías, futuro). El cubo no.

---

## ÍNDICE

- §0 — Naturaleza, reglas de lectura y posición
- §1 — Misión, frontera y recorridos E2E (campaña de contenido, monitoreo de presencia, oportunidad de segmento)
- §2 — Anatomía del trabajo de demanda que replica (por qué es puente entre Brand y Comercial)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Máquina de estados: campaña, contenido, visibility
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo
- §10 — Kit de despliegue y superficie del operador
- §11 — Estado real vs. dossier: greenfield con contexto estratégico existente
- §12 — Programa de construcción a v1.0: bloques D6
- §13 — Batería de pruebas duras
- §14 — Prueba de vida real pre-registrada (VR-D06-01)
- §15 — Riesgos de segundo orden
- §16 — Puerta v1.0: checklist DoD y falsación
- Anexo A — Esquemas de payload `marketing.*` v1

---

## §0 — NATURALEZA, REGLAS DE LECTURA Y POSICIÓN

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan. Índice: plantilla D01.

### §0.2 No es CRM, no es email blasting, no es "algoritmo que vuelve viral"
Marketing aquí es la función estructurada de generar oportunidades verificables: "en la zona X hay Y hospederías sin sitio web; el nicho de repostería de horno es Z-grande y creciente". Todo con números, no intuición. **El cubo es coordinación de canales (contenido, presencia, segmento targeting) verificada por datos.**

---

## §1 — MISIÓN, FRONTERA Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Marketing pone la marca y el argumento donde hay oído que lo escuche, y mide si ese oído existe y responde. **No es que ventas suban automático; es que Comercial no prospera en el vacío.**

### §1.2 Qué NO es — FIJADO
- **No es ventas.** No cierra; genera lista de "alguien debería hablar con estos".
- **No es relaciones públicas.** No maneja crisis o reputación (ese es cumplimiento, D08).
- **No es branding.** Eso es D02; Marketing solo asegura que Brand esté visible (coherencia en canal).
- **No es adquisición de datos de tercero.** No compra listas de emails; prospera sobre lo que el sistema ya ve.
- **No promete resultados predecibles.** Genera señal; Comercial la convierte. Si Comercial no convierte, no es culpa de Marketing.

### §1.3 Recorrido A — LOS PASOS de una campaña de contenido

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| M1 | Definición de campaña: vertical, segmento diana, objetivo (leads, visibilidad, test), duración | Operador | Operador (con cliente si es caso Laboratorio) | — | — |
| M2 | Selección de canales: web (SEO/SEM), social (LinkedIn/Instagram), email (si existe base), presencia local (Google Maps, Yelp) | Operador + Marketing | Operador | canal tiene API o integración viable; presupuesto encaja | — |
| M3 | Creación de contenido: headline, copy, visuals (alineados con Brand D02) | Operador o IA | Sistema propone; Brand valida | `verificacion.validar_borrador` con paquete de marca | `marketing.contenido.creado` |
| M4 | Aprobación y scheduling | Operador | Operador | verificación Brand OK | `marketing.contenido.aprobado` |
| M5 | Lanzamiento de campaña: publicación en canales, inicio de tracking | Sistema | automático post-aprobación | — | `marketing.campana.lanzada` |
| M6 | Monitoreo en vivo: impresiones, clicks, engagement, costo por interacción | Sistema | Sistema (dashboards) | — | `marketing.campana.metrica` (diario) |
| M7 | Ajuste iterativo: pausa canales débiles, boost canales fuertes (según presupuesto mandato) | Operador | Operador o automático (según nivel §6) | presupuesto no se sobrepasa | `marketing.campana.ajustada` |
| M8 | Cierre de campaña: reporte final, leads generados, ROI estimado (venta real la valida D01/D04) | Sistema | automático | — | `marketing.campana.cerrada` |

### §1.4 Recorrido B — LOS PASOS del monitoreo de presencia viva

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| P1 | Auditoría de presencia: ¿dónde está la marca? (web, Maps, Yelp, redes sociales del vertical) | Sistema | Sistema | lista de canales versionada | — |
| P2 | Verificación de datos: nombre, dirección, horarios, número de teléfono, fotos, reseñas de otros (no propias) | Sistema | Sistema (crawler o API) | datos = lo que está en la ficha del tenant | `marketing.presencia.auditada` |
| P3 | Detectar oportunidad: si el tenant no está en X pero competidores sí, proponer alta | Sistema | Sistema propone; operador confirma | canal tiene API para alta; no requiere licencia | `marketing.presencia.oportunidad` |
| P4 | Monitoreo de reseñas: si alguien reporta negativo, alerta; si positivo, agradecer | Sistema propone respuesta | Operador (personalización) | respuesta respeta Brand | `marketing.resena.respondida` |
| P5 | Tendencia de reseñas y rating: agregación mes-a-mes | Sistema | — | — | asiento P8 (satisfacción) |

### §1.5 Recorrido C — LOS PASOS de la oportunidad de segmento

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| S1 | Análisis de segmento: "en Cieza hay X hostelería de tamaño Y sin presencia web; receptivos a ayuda" | D07 Inteligencia + Sistema | — | datos públicos (Cámara de Comercio, SIREM) o encuesta muestreo | — |
| S2 | Propuesta de segmento a Comercial: "campana dirigida a este segmento" | Marketing | Comercial acepta o rechaza | criterios de vertical §2.1 D01 | `marketing.segmento.propuesto` |
| S3 | Lanzamiento de campaña dirigida al segmento (si acepta) | Sistema | automático post-aprobación | presupuesto | `marketing.campana.lanzada` |
| S4 | Medición de conversión (Comercial → D01 evento pedido): X leads generados, Y conversiones, Z ROI | D01/D04 + Marketing | — | cifras de pedidos atribuibles al segmento | `comercial.pedido.atribuido` (con marca de segmento) |
| S5 | Feedback a inteligencia: segmento fue bueno o malo para futuras prioridades | Sistema | — | — | asiento P8 |

---

## §2 — ANATOMÍA DEL TRABAJO DE DEMANDA QUE REPLICA

### §2.1 Descomposición

| Función humana | Qué hace de verdad | Rol sintético que la absorbe |
|---|---|---|
| Community manager | "Publicamos en LinkedIn, respondemos comentarios, buscamos gente interesada" | Gestor de canales + monitor de presencia |
| SEO/SEM ejecutor | "Hacemos aparecer en Google cuando alguien busca 'repostería Cieza'" | Optimizer de canales (oferta-demanda local) |
| Copywriter | "Escribimos esto y esto la marca lo aprueba" | Generador de contenido (con validación Brand) |
| Analista de mercado (si existe) | "Estos nichos crecen, estos envejecen" | Detector de segmentos (integración con D07) |

### §2.2 El reparto FIJADO
- **Del cubo:** seguimiento de dónde está la marca, generación de contenido alineado, medición de presencia y engagement, detección de segmentos atractivos.
- **Del operador:** decisión de qué segmentos priorizar (alineado con capacidad D05), aprobación de cambios, manejo de crisis/comentarios negativos.
- **De Comercial:** conversión de leads generados; feedback sobre qué segmento convierte y cuál no.

**Regla de oro (FIJADO):** todo contenido que Marketing genera **pasa por Brand (D02) antes de salir**. Marketing no tiene "versión rápida" sin validación. Si la marca falla, todo falla.

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

### §3.1 Gestor de campaña — **P·D6.0**
- **Misión:** que una campaña sea un plan, no un grito.
- **E→P→S:** definición (vertical, segmento, objetivo, presupuesto, duración) → selección de canales → creación de contenido → aprobación → lanzamiento → monitoreo → cierre.
- **Clase:** ESTANDAR. **Autonomía:** propone fases; operador aprueba cada transición importante (paso M4). **Verificación:** presupuesto no se excede (gate determinista).
- **Estado:** cero líneas; es workflow nuevo.

### §3.2 Generador de contenido — **P·D6.0**
- **Misión:** crear copy/headlines/visuals que llamen oído sin ser ruido.
- **E→P→S:** segmento + vertical + tono de Brand → propuesta de texto/imagen → pasada por validador de Brand (§3.5).
- **Clase:** ESTANDAR (modelo LLM + Brand). **Autonomía:** REVERSIBLE (propone; operador ajusta). **Verificación:** Brand OK es gate.
- **Estado:** cero líneas; es nueva integración con D02.

### §3.3 Validador de Brand (consumidor de D02) — **heredado de D02**
- Usa servicio `brand.validar_borrador` del cubo Brand (D02 §3.2).
- Todo contenido saliente pasa por aquí.
- Marketing no tiene validador propio; consume el de Brand.

### §3.4 Auditor de presencia — **P·D6.1**
- **Misión:** ¿dónde está la marca? ¿es visible?
- **E→P→S:** lista de canales (web, Maps, Yelp, redes) → crawler/API → estado de cada uno (existe, datos actualizados, reviews, ranking) → reporte.
- **Clase:** TRIVIAL (determinista: crawler devuelve estado). **Autonomía:** REVERSIBLE (propone acciones; operador decide). **Verificación:** datos versionados (misma fecha → mismo resultado).
- **Estado:** cero líneas; es infraestructura nueva.

### §3.5 Monitor de engagement — **P·D6.0**
- **Misión:** qué funciona en términos de atracción.
- **E→P→S:** métricas en vivo de campaigns (impresiones, clicks, engagement rate, costo/interacción) → agregación diaria → alertas si performance cae.
- **Clase:** TRIVIAL (solo lectura de APIs de canales). **Autonomía:** REVERSIBLE (propone pausa/boost; operador confirma si BAJA). **Verificación:** —.
- **Estado:** cero líneas; es integración con APIs de canales.

### §3.6 Detector de segmento — **P·D6.2** (futuro, en paralelo con D07)
- **Misión:** encontrar nichos donde hay demanda insatisfecha.
- **E→P→S:** datos públicos (registros mercantiles, directorios, búsquedas Google Trends) + leads rechazados por capacidad de D05 → análisis de tamaño/crecimiento del segmento → propuesta a Comercial.
- **Clase:** ESTANDAR. **Autonomía:** propone; Comercial decide si intenta. **Verificación:** datos verificables (fuente citada).
- **Estado:** cero líneas; es análisis que vive en la frontera D06-D07.

---

## §4 — MÁQUINA DE ESTADOS: CAMPAÑA, CONTENIDO, VISIBILIDAD

### §4.1 Campaña — FIJADO

```
BORRADOR → APROBADA → ACTIVA → PAUSADA / COMPLETADA
              ↓ rechazada
           CANCELADA
```

| Estado | Significado | Quién entra | Quién sale |
|---|---|---|---|
| BORRADOR | Definición sin lanzamiento | Operador | Operador aprueba (APROBADA) o cancela |
| APROBADA | Contenido validado, presupuesto asignado, listo | Operador | Sistema lanza (ACTIVA) o espera slot |
| ACTIVA | Corriendo en canales | Sistema | Operador pausa/boost, o fin de período (COMPLETADA) |
| PAUSADA | Temporal (problema, overspend, decisión) | Operador | Operador reactiva (ACTIVA) o cancela |
| COMPLETADA | Fin de período; no se lanza más; datos archivados | Sistema (timeout) | histórico, no se toca |
| CANCELADA | Cancelada prematuramente | Operador | histórico |

### §4.2 Contenido — FIJADO

```
GENERADO → VALIDADO_POR_BRAND → APROBADO → LANZADO → ARCHIVADO
              ↓ rechazado
           REVISADO (itera)
```

La validación por Brand es **blocking**: sin VALIDADO_POR_BRAND, no avanza.

### §4.3 Presencia — FIJADO

```
AUDITADA → OPORTUNIDADES_IDENTIFICADAS → ACTIVAS
```

Estados de presencia por canal (p. ej. Maps): {EXISTE, NO_EXISTE, OUTDATED, BAJO_RANKING}.

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `marketing.campana.lanzada` | 1 | A.1 | por campaña (varios/mes típico) | no | presupuesto encaja | — | TRIVIAL |
| `marketing.campana.metrica` | 1 | A.2 | diario (en vivo) | no | datos versionados (misma fecha = mismos números) | — | TRIVIAL |
| `marketing.campana.ajustada` | 1 | A.3 | cambios de strategy (boost, pausa) | no | presupuesto respetado | — | TRIVIAL |
| `marketing.campana.cerrada` | 1 | A.4 | fin de período | no | ROI estimado citable | — | TRIVIAL |
| `marketing.contenido.creado` | 1 | A.5 | por contenido generado | no | — | — | ESTANDAR |
| `marketing.contenido.aprobado` | 1 | A.6 | post-Brand validation | **sí** (empieza a usarse) | Brand OK | — | TRIVIAL |
| `marketing.presencia.auditada` | 1 | A.7 | semanal o mensual | no | canal status versionado | — | TRIVIAL |
| `marketing.presencia.oportunidad` | 1 | A.8 | cuando se detecta (p. ej. canal nuevo) | no | propuesta a operador | — | TRIVIAL |
| `marketing.resena.respondida` | 1 | A.9 | post-respuesta a reseña | no | tono respeta Brand | — | TRIVIAL |
| `marketing.segmento.propuesto` | 1 | A.10 | análisis (semanal, mensual) | no | Comercial consume | — | TRIVIAL |

### §5.B — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente |
|---|---|---|
| `brand.politicas` (D02, servicio) | **Sí** | sin él, contenido corre sin validación (violación de regla de oro) → falla v1.0 |
| `comercial.pedido.atribuido` (D01, con marca de segmento) | Sí (para medir ROI) | sin atribución, no puedes medir si el segmento convirtió |
| `comercial.lead.descubierto` (D01, donde viene el lead) | No | sin fuente, no sabes si vino de Marketing o de otro lado; impacta ROI |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado |
|---|---|---|
| `marketing.consulta_campana(tenant, id)` | → estado, métricas, ROI | lectura pura |
| `marketing.proponer_contenido(tenant, segmento)` | → draft, validación_brand_pending | requiere aprobación |

### §5.D–F — véase §6, §8, §10

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

**FIJADO:** Marketing no gasta dinero sin aprobación (presupuesto es un límite duro).

| Acción | Clase | CERO | BAJA (default) | MEDIA | ALTA |
|---|---|---|---|---|---|
| Crear campaña (plan) | REVERSIBLE | propone | operador confirma | operador confirma | operador confirma |
| Generar contenido | REVERSIBLE | propone | operador + Brand validation | operador + Brand; template puede ir directo | — |
| Lanzar contenido aprobado | IRR-EXT | no sale | operador autoriza | lanzamiento automático (post-aprobación Brand) | automático; excepto presupuesto-lock escala |
| Pausar/boost campaña (dentro presupuesto) | REVERSIBLE | propone | operador decide | automático si presupuesto OK | automático |
| Gastar presupuesto fuera de plan | IRR-EXT | no | operador aprueba | no disponible | no disponible |
| Responder reseña negativa | IRR-EXT | operador responde fuera | operador en panel (respuesta revisada) | template pre-aprobado | — |

---

## §7 — CUMPLIMIENTO INTEGRADO: REGLA → CONTROL → TEST

| # | Regla | Control | Test |
|---|---|---|---|
| 1 | Contenido pasa Brand antes de salir | gate preventivo: VALIDADO_POR_BRAND es obligatorio | `test_contenido_sin_brand_imposible` |
| 2 | Presupuesto no se sobrepasa | suma de spend por período ≤ mandato | `test_presupuesto_respetado` |
| 3 | Campaña tiene métricas registradas | evento `.metrica` diario con impresiones/clicks/costo | `test_metricas_registradas` |
| 4 | ROI es citable (asociado a pedidos atribuibles) | pedidos con marca de segmento/campaña de origen | `test_roi_verificable` |
| 5 | Presencia auditada es reproducible | misma fecha → mismos datos de presencia | `test_presencia_reproducible` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Campañas, contenidos, métricas, presencia y ROI son **la verdad de qué genera demanda** (P9).

### §8.2 Señal P8 — FIJADO
Por cada campaña:

```
(tenant, segmento, canal, fecha_inicio, duracion_dias, impresiones, clicks, engagement_rate,
 costo_total, costo_por_interaccion, leads_generados, conversiones, roi_estimado, ts)
```

Ajusta: priorización de canales (qué funciona mejor), targeting (qué segmento convierte), presupuesto (asignación futura).

### §8.3 Entidades y propiedad
Campañas, contenidos, métricas → DATO_CLIENTE (exportable). Plantillas de contenido, lista de canales → DATO_PLATAFORMA. Señales P8 disociadas → DATO_AGREGADO.

---

## §9 — ECONOMÍA DEL CUBO

### §9.1 Coste marginal — ABIERTO (lo cierra VR-D06-01)
Marketing es gasto en canales (el cubo lo coordina; no es el cubo quien paga). Su coste interno es tiempo de operador (aprobación de contenido, ajustes) + sustrato. Margen: el ROI de la campaña (Comercial convierte, D04 cobra).

### §9.2 Ventaja de permuta (P8)
Datos de canal performance + segmento conversion → modelo de presupuesto futuro que optimiza gasto. Es la inversión incremental que mejora ROI.

---

## §10 — KIT DE DESPLIEGUE Y SUPERFICIE DEL OPERADOR

### §10.1 Kit
1. **Parametrización de canales:** API keys para cada canal (Google Ads, LinkedIn, etc.); credenciales seguras.
2. **Presupuesto por período:** allocation por canal o global con reglas de distribución.
3. **Plantillas de contenido:** headlines, copy, visuals por vertical (reutilizables).
4. **Reglas de Brand:** qué se valida antes de publicar.
5. **Auditoría de presencia:** lista de canales a monitorear.
6. **Smoke test:** crear campaña ficticia, generar contenido, validar con Brand, lanzar en dry-run.

### §10.2 Superficie del operador — FIJADO
- **Panel de campañas:** activas, pausadas, completadas; métricas en vivo.
- **Generador de contenido:** genera + propone, operador edita/aprueba, Brand valida.
- **Monitor de presencia:** auditoría de dónde está la marca; oportunidades.
- **ROI dashboard:** conversiones atribuidas a cada campaña.
- **Presupuesto tracker:** gasto acumulado vs. límite.

---

## §11 — ESTADO REAL VS. DOSSIER: GREENFIELD CON CONTEXTO

| Item | Estado | Notas |
|---|---|---|
| Código de Marketing en repo | No existe | Greenfield puro |
| Manual de Marca Laboratorio | Existe, versionado | Sirve como input; Marketing lo respeta |
| Estrategia de canales (Tesis F4) | Existe en Tesis, no sistematizada | Guía alto nivel; D06 la implementa |
| APIs de canales disponibles | Parciales (Google, LinkedIn, etc.) | D6.0 integra las más comunes |
| Integración con D01 para atribución | No existe | D6.0 lo implementa (marca de segmento/campaña en evento) |
| Datos de presencia (auditoría) | Parciales (búsquedas manuales) | D6.1 sistematiza con crawlers |

**Honestidad:** Greenfield puro de código, pero con estrategia y manual de marca como punto de partida.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES D6

Orden por dependencia: D6.0 (gestor + contenido + Brand integration) → D6.1 (presencia) → D6.2 (segmentos, puede ser paralelo con D07). Requiere D00-B1 ✓ + D02 ✓ (Brand). Ciclo D00 §0.6; commit por bloque.

### D6.0 — Gestor de campaña + generación de contenido
1. Definición de campaña (vertical, segmento, canales, presupuesto, duración).
2. Generador de contenido (headlines, copy) con validación Brand.
3. Lanzamiento en canales (integración con APIs disponibles).
4. Monitoreo de métricas en vivo (impresiones, clicks, costo).
5. Pausa/boost manual de campañas.
6. Reporte de cierre con ROI estimado.
7. **Puerta D6.0:** Laboratorio con ≥2 campañas (p. ej. una por canal: Google, LinkedIn) completadas + contenido pasó Brand validation en 100% + ROI estimado citable + VR-D06-01.

### D6.1 — Auditoría de presencia
1. Integración con crawlers (Google Maps, Yelp, web propio).
2. Verificación de datos en cada canal (nombre, teléfono, horarios, reseñas).
3. Detección de oportunidades (canales donde no está presente).
4. Monitor de reseñas y rating.
5. **Puerta D6.1:** Laboratorio con auditoría completa de presencia + ≥1 oportunidad detectada + operador viendo reseñas en panel.

### D6.2 — Detector de segmento (puede ser paralelo con D07)
1. Integración con D07 Inteligencia (comparte datos y análisis).
2. Propuestas de segmento a Comercial con datos de tamaño/crecimiento.
3. Medición de conversión de segmento (vinculación de leads a pedidos).
4. (Puede quedar post v1.0 si D07 no existe aún.)

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de tenant** | 2 tenants con campañas distintas | campañas A no aparecen en dashboard B |
| 13.2 | **Brand validation bloqueante** | Genera contenido que Brand rechaza | contenido no sale, queda en RECHAZADO |
| 13.3 | **Reproducibilidad de métricas** | Misma campaña en día X, 3 queries → mismos números | 3/3 idénticos |
| 13.4 | **Presupuesto cierra la puerta** | Presupuesto = 100€; intenta gastar 101€ | gasto rechazado; campaña pausa automática |
| 13.5 | **ROI verificable** | Campaña genera 5 leads, 2 convierten en pedido; ROI = 2/5 | pedidos tienen marca de campaña de origen |
| 13.6 | **Presencia reproducible** | Auditoría de Laboratorio en día X vs. día Y (sin cambios) | mismos datos (Maps existe, Yelp existe con N reviews) |
| 13.7 | **Respuesta a reseña respeta Brand** | Reseña negativa; sistema propone respuesta; Brand valida | respuesta pasa Brand OK antes de publicar |
| 13.8 | **Lanzamiento de contenido pre-Brand es imposible** | Intenta publicar sin paso de Brand | lanzamiento rechazado (validación obligatoria) |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D06-01

Pre-registro conforme a D00 Anexo II:
- **Tenant:** `laboratorio` · **Ventana:** 4 semanas · **Acciones:** ≥2 campañas completas (lanzadas, corridas, métricas registradas, cerradas).
- **Métricas y umbrales (binarios):**
  1. 100% del contenido pasó Brand validation antes de salir (ninguno sin validación).
  2. Presupuesto total gastado ≤ presupuesto asignado (no sobrepaso).
  3. ≥1 métrica diaria por campaña (impresiones, clicks, costo).
  4. ≥1 ROI estimado verificable (leads de campaña vinculados a pedidos vía atribución D01).
  5. Auditoría de presencia completada (≥3 canales auditados).
  6. Operador viendo panel de campañas + métricas + presupuesto.
  7. Si reseña negativa llegó: respuesta propuesta y Brand validada antes de publicar.
- **Fallo total:** contenido publicado sin Brand validation, presupuesto rebasado, métrica no registrada → aborta.

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **Contenido sin Brand sale igual** (validación saltada) | Gate determinista: estado VALIDADO_POR_BRAND es obligatorio | test §13.8 |
| **Gasto runaway** (acumula y supera presupuesto) | Suma de spend real vs. mandato con alerta en 90% | test §13.4 |
| **Reseña negativa sin respuesta contextuada** (destruye marca) | Panel de reseñas; Brand valida respuesta antes de publicar | test §13.7 |
| **Metrics no registrado; no sabes ROI** (inversión a ciegas) | evento `.metrica` diario es obligatorio | test §13.3 |
| **Campañas no atribuidas a Comercial** (no sabes si generaron leads) | marca de campaña/segmento en `comercial.pedido.atribuido` | test §13.5 |
| **Presencia desactualizada** (cliente ve info vieja) | Auditoría semanal/mensual; alertas si datos out-of-sync | test §13.6 |

---

## §16 — PUERTA v1.0: CHECKLIST DoD Y FALSACIÓN

### §16.1 Checklist
- [ ] D6.0–D6.1 cruzados con commit y acta.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D06-01 ✓ con Laboratorio.
- [ ] 100% del contenido pasó Brand validation.
- [ ] Presupuesto nunca superado (bloqueante).
- [ ] ≥2 campañas completadas con ROI estimado y verificable.
- [ ] Presencia auditada en ≥3 canales.
- [ ] Operador viendo panel con métricas en vivo.
- [ ] Aislamiento tenant verificado (campañas A no contamina B).

### §16.2 Falsación
1. Contenido publicado sin Brand validation → puerta cerrada; revisitar §6 y §13.8.
2. Presupuesto sobrepasado → arquitectura de bloqueo falla; investigar gate.
3. ROI no verificable (leads no vinculados a pedidos) → falta de atribución en D01; investigar marca de segmento/campaña.
4. Métrica no registrada → persistencia de eventos falla; revisitar D00 bus.

---

## ANEXO A — ESQUEMAS DE PAYLOAD `marketing.*` v1

- **A.1 `campana.lanzada`**: `{campana_id, tenant_id, segmento, canales[], presupuesto_asignado, duracion_dias, ts_inicio}`
- **A.2 `campana.metrica`**: `{campana_id, fecha, impresiones, clicks, engagement_rate, costo_total, costo_por_click}`
- **A.3 `campana.ajustada`**: `{campana_id, cambio: PAUSA|BOOST, razon, presupuesto_reasignado?}`
- **A.4 `campana.cerrada`**: `{campana_id, duracion_real_dias, total_spend, total_impresiones, leads_generados, conversiones_estimadas, roi}`
- **A.5 `contenido.creado`**: `{contenido_id, tipo: HEADLINE|COPY|IMAGEN, version_draft, validacion_brand_pending: true}`
- **A.6 `contenido.aprobado`**: `{contenido_id, validacion_brand_ref, veredicto: APTO, fecha_aprobacion}`
- **A.7 `presencia.auditada`**: `{tenant_id, auditorias[{canal, existe, datos{nombre, telefono, horarios, rating}, timestamp}]}`
- **A.8 `presencia.oportunidad`**: `{tenant_id, canal_propuesto, razon, datos_publicos_referencia}`
- **A.9 `resena.respondida`**: `{resena_id, respuesta_texto, validacion_brand_ok: true, publicada_en: CANAL}`
- **A.10 `segmento.propuesto`**: `{segmento_descripcion, tamaño_estimado, fuente_datos, crecimiento_pct, propuesta_a_comercial}`

---

*Fin de KAIZEN-D06 v1.0. Emitido el 2026-07-08. Generador de demanda, no conversor. Todo contenido pasa Brand validation (regla de oro). Greenfield puro de código, con Manual de Marca y estrategia de Tesis como punto de partida. Dependencia de arranque: D00-B1 ✓ + D02 ✓ (Brand validation) + D01 ✓ (atribución). Siguiente de la serie: D07 (Inteligencia de Mercado).*
