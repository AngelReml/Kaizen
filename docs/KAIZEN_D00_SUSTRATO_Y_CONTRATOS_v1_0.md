# KAIZEN-D00 — SUSTRATO Y CONTRATOS COMUNES
## Serie de dossieres departamentales KAIZEN · Documento 00

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (primera emisión canónica; el versionado del dossier lo gobierna §0.7)
**Alcance:** el sistema nervioso compartido de la plataforma Kaizen — todo aquello que un departamento (cubo) puede asumir que existe, con qué contrato, con qué garantías y con qué pruebas.
**Sustituye a:** `KAIZEN_ARQUITECTURA_CANONICA_v1_0.md` como especificación de sustrato (§11.1 detalla qué se absorbe y qué se descarta de aquel documento, punto por punto).
**No sustituye a:** la Tesis de plataforma v2.0 ni su Anexo A (documentos padre de negocio), ni a los dossieres departamentales D01–D08 (hijos de éste), ni al código testeado (que prevalece según §0.3).

---

## ÍNDICE

- §0 — Naturaleza del documento, reglas de lectura y nota de cambio
- §1 — Misión del sustrato y qué NO es
- §2 — Modelo de tenancy: multi-tenant real e invariantes de aislamiento
- §3 — Bus de eventos, Registro Único de Eventos (RUE) y bitácora
- §4 — Autonomía graduada y Mandato Operacional
- §5 — Verificación: comité, QA transversal y verificación visible
- §6 — Contabilidad de coste y router de modelos
- §7 — Superficie de dirección: panel del Director y CLI
- §8 — Seguridad, pánico y cumplimiento del sustrato
- §9 — Persistencia, propiedad del dato y dieta de dependencias
- §10 — Contratos de interoperabilidad: cómo declara un dossier departamental
- §11 — Estado real vs. canon: divergencias, absorciones y descartes
- §12 — Programa de construcción a v1.0: bloques y puertas
- §13 — Batería de pruebas duras del sustrato
- §14 — Prueba de vida real pre-registrada (VR-D00-01)
- §15 — Puerta v1.0: checklist DoD operativo y criterios de falsación
- §16 — Registro Único de Eventos v1 (semilla)
- §17 — Glosario canónico
- Anexo I — Plantilla de declaración de interoperabilidad (para todo Dxx)
- Anexo II — Plantilla de pre-registro de ensayo de vida real

---

## §0 — NATURALEZA DEL DOCUMENTO, REGLAS DE LECTURA Y NOTA DE CAMBIO

### §0.1 Propósito

Este dossier existe para que los ocho dossieres departamentales no tengan que describir, cada uno por su cuenta, cómo se relaciona con los demás. Las relaciones se escriben **una sola vez, aquí, como contrato**. Un dossier departamental declara qué eventos publica, cuáles consume y qué servicios ofrece o requiere **contra el registro de este documento** (§16), rellenando la plantilla del Anexo I. Dos documentos describiendo la misma relación acaban contradiciéndose; ese es el mecanismo exacto de la enfermedad que la auditoría del 2026-07-02 diagnosticó entre `KAIZEN_ARQUITECTURA_CANONICA_v1_0.md` y el código real. D00 es la vacuna: una relación, una fuente.

### §0.2 Convención de estados

Toda afirmación normativa de la serie D lleva uno de estos marcadores:

| Marcador | Significado |
|---|---|
| **FIJADO** | Decisión tomada. Ordena el trabajo posterior. Cambiarla exige REEVALUACION con hechos. |
| **ABIERTO** | Depende de un dato que aún no existe. Se indica qué dato lo cierra y en qué bloque se obtiene. |
| **DIVERGENTE** | El código real difiere de lo aquí especificado. Se indica evidencia (archivo:línea), resolución y bloque que la ejecuta. |
| **DIVERGENTE-DIFERIDA** | Divergencia reconocida cuya resolución se aplaza deliberadamente a la re-arquitectura financiada (pista NEOTEC). No se toca antes. |
| **EXPERIMENTAL** | Existe en el repositorio pero queda fuera de la ruta de producción y fuera del DoD v1.0. |

### §0.3 Regla de precedencia — FIJADO

1. **Sobre comportamiento existente:** código testeado > dossier > intención. Si el código que pasa tests contradice este documento, gana el código: no se cambia por decreto; se documenta como DIVERGENTE y se resuelve por bloque con test. (Herencia directa de la §0.2 del documento canónico anterior, que este dossier absorbe.)
2. **Sobre construcción nueva:** el dossier es la orden de trabajo hasta que el código exista y cruce su puerta; a partir de ahí, el código es la verdad y el dossier se actualiza en la REEVALUACION correspondiente.
3. Un dossier nunca describe un sistema imaginario como si existiera. Todo lo no verificado con ejecución real se marca.

### §0.4 NOTA DE CAMBIO NC-2026-07-08 — Revocación de la Decisión 3

**Hecho:** el Director revocó el 2026-07-08 la Decisión 3 de la serie D ("la serie es especificación, no construcción"), que a su vez descansaba en la nota de disciplina de la Tesis v2.0 §10 ("no construir el segundo cubo antes de vender el primero").

**Resolución:** la construcción de todos los módulos queda autorizada y ordenada. La disciplina no desaparece: **cambia de forma**. Antes protegía la validación por calendario (no construir hasta vender); ahora la protege por evidencia (constrúyelo todo, pero **nada es v1.0 sin prueba de vida real**). La nota de disciplina de la Tesis queda enmendada en su forma y preservada en su intención: ningún cubo se declara producto sin validación observada.

**Consecuencia estructural (FIJADO):** la puerta de VIDA REAL de cada cubo consume un tenant real. La disponibilidad de tenants ordena las v1.0; el teclado ordena las construcciones. Ambas colas avanzan en paralelo sin bloquearse.

### §0.5 Posición en el corpus

```
Tesis v2.0 + Anexo A          → el porqué (mercado, foso, economía)
Serie D (D00–D08)             → el qué y el cómo (especificación ejecutable)
Código del repositorio        → la verdad ejecutable
AUDITORIA_Dxx / REEVALUACION_Dxx → la verdad observada
Contratos firmados (Laboratorio, tipo cliente, LIA) → la verdad jurídica
```

Cuando dos capas se contradicen, manda §0.3. Cuando el contrato jurídico exige algo (p. ej. export del pipeline a la baja, cláusula 9 del contrato tipo), el sustrato lo implementa como primitiva (§2.4, §9.3): **lo firmado se convierte en test**.

### §0.6 Ciclo de vida de todo departamento — FIJADO

```
DOSSIER → CONSTRUCCIÓN por bloques → SUITE (CI, verde) → PRUEBAS DURAS
→ VIDA REAL (pre-registrada) → AUDITORÍA → PUERTA v1.0 → REEVALUACIÓN → dossier vN+1
```

Reglas de proceso con rango de doctrina:

- **R1 — Commit por bloque.** Ningún bloque se cruza sin commit y push. Los 35 días sin historial detectados por la auditoría (último commit real 2026-05-28) quedan prohibidos por doctrina, no por buena intención. La prueba dura §13.8 (restauración) convierte esta regla en test.
- **R2 — Test rojo primero.** Todo bug reconocido se reproduce con un test que falla antes de corregirse.
- **R3 — Pre-registro.** Toda prueba de vida real se registra por escrito (Anexo II) **antes** de ejecutarse: tenant, ventana, N, umbrales. Las porterías no se mueven después.
- **R4 — Evidencia citable.** Toda AUDITORIA_Dxx usa el método del 2026-07-02: archivo:línea o comando con salida literal; las contradicciones se muestran, no se resuelven en silencio.

### §0.7 Versionado del dossier

Este documento es un organismo, no una foto. Emisión inicial v1.0. Cada REEVALUACION_D00 produce, si procede, un bump: correcciones sin cambio normativo = v1.x; cambio de contrato (RUE, sobre de evento, invariantes) = v2.0 con ventana de deprecación (§3.5).

---

## §1 — MISIÓN DEL SUSTRATO Y QUÉ NO ES

### §1.1 Misión

El sustrato es el sistema nervioso y el suelo de garantías de la plataforma. Su cliente no es la pyme: son los cubos y el operador. Todo cubo puede asumir que existen, sin construirlas, exactamente **cinco garantías**:

| # | Garantía | Sección |
|---|---|---|
| G1 | **Identidad de tenant** — quién es el cliente de cada dato, evento y acción, con aislamiento probado | §2 |
| G2 | **Bus con bitácora** — publicar y consumir eventos con trazabilidad encadenada por hash | §3 |
| G3 | **Verificación bajo demanda** — comité configurable y validación de borradores como servicio | §5 |
| G4 | **Contabilidad de coste** — cada acción con coste imputado a (tenant, cubo, rol, clase) y techos que muerden | §6 |
| G5 | **Superficie de dirección** — panel y CLI donde el operador ve, aprueba, dirige y configura; y donde el cliente ve su resultado | §7 |

### §1.2 Qué NO es — FIJADO

- **No es un producto vendible.** No tiene precio, no tiene cliente final, no aparece en el catálogo. Su DoD es operativo (§15), no comercial.
- **No es un framework genérico de agentes.** Es el mínimo común de Kaizen; toda pieza que no necesiten al menos dos cubos vive en el cubo que la necesita.
- **No contiene lógica de negocio de ningún vertical.** Argumentarios, cadencias, políticas de marca: eso es de los cubos.

### §1.3 Absorciones — FIJADO

- **QA deja de ser departamento.** La validación de borradores (existente: commit `e2e94d2`, "QA real - validación de borradores") es propiedad transversal P3 de la Tesis y pasa a ser servicio del sustrato: `verificacion.validar_borrador` (§5.4). Una pyme no compra "QA"; compra que todo lo que sale esté verificado.
- **Dirección deja de ser departamento.** El Director (existente: commits `9c11c6e`, `8590a58`) es la superficie de dirección del sustrato (§7), en cumplimiento de P7: el operador como director de empresas sintéticas.
- **RRHH (D09) — ABIERTO:** si su sentido real es el ciclo de vida de los *agentes* (alta, configuración, retirada de roles sintéticos), es sustrato y migrará a este dossier en una reevaluación; si es RRHH del cliente, sigue pospuesto como cubo. Lo cierra la primera demanda real de un tenant.

---

## §2 — MODELO DE TENANCY: MULTI-TENANT REAL E INVARIANTES DE AISLAMIENTO

### §2.1 Definiciones

- **Tenant:** empresa cliente de la plataforma. Hoy existen tres reales: `laboratorio` (Repostería Laboratorio, Cieza), `rial` (Segundo Tenant), `verigest` (VeriGest). El identificador canónico es minúscula ASCII estable; el registro de tenants (§2.3) mapea id → datos legales.
- **Operador:** la persona que dirige la plataforma (hoy, uno).
- **Plataforma:** el ámbito propio de ZapWeave/[S.L.]: código, prompts, know-how, datos agregados disociados.

### §2.2 Invariantes de aislamiento — FIJADO

Estas cinco invariantes son ley para todo código de producción y toda prueba dura las ataca (§13.1):

- **I1 — Lectura:** ningún dato de un tenant es legible desde el contexto de ejecución de otro tenant.
- **I2 — Eventos:** ningún evento cruza tenants. El único canal transversal es el ámbito `plataforma.*`, explícito y sin payload de negocio de tenant.
- **I3 — Configuración y credenciales:** remitente SMTP, números de teléfono salientes, dominios, firmas y mandato son **por tenant**. Prohibido el fallback silencioso a credenciales de otro tenant o de la plataforma.
- **I4 — Coste:** todo gasto queda imputado a su tenant (o a `plataforma` si es overhead), sin bolsa común anónima.
- **I5 — Portabilidad:** export completo y borrado verificable por tenant son primitivas del sustrato (§9.3). Es la implementación de la cláusula 9 del contrato tipo y de los plazos de la LIA §3.8.

**Regla de código derivada (FIJADO):** prohibido todo literal de tenant en rutas de producción (`"laboratorio"` hardcodeado y equivalentes). El bug `departments/comercial/brand_guardian.py:257` (fuerza `company="laboratorio"` para todo tenant, hallazgo crítico de la auditoría) es el espécimen tipo de la clase de defecto que esta regla proscribe. Su corrección es Bloque 1 (§12) y su prohibición se vigila con un gate de CI (grep de literales de tenant en `core/`, `departments/`, `api/`) desde Bloque 2.

### §2.3 Registro de tenants — FIJADO

Archivo canónico en el repositorio (`tenants.yaml` o equivalente, decide Bloque 2), con: `id`, razón social, vertical, estado (`activo/pausado/baja`), referencia a mandato operacional (§4.4), referencia a credenciales (fuera del repo), fecha de alta. Ningún tenant opera sin ficha; ninguna ficha sin mandato.

### §2.4 Baja de tenant — FIJADO

Secuencia obligatoria: pausa de toda acción externa → export del paquete de datos del cliente (pipeline completo, historial, compromisos, diario; formato JSON+CSV reutilizable) → entrega → borrado de DATO_CLIENTE con acta (evento `plataforma.datos.borrados` con hash del acta) → conservación exclusiva de lo exigido por ley y de la lista de exclusión (LIA §3.8, dato mínimo). La lista de exclusión de prospección **no** se borra: honrar la oposición sobrevive al contrato.

### §2.5 Modo degradado

Un solo tenant no es un modo especial: es N=1. El sustrato no distingue; así se garantiza que el paso de 1 a N tenants no reabre diseño (la lección del multi-tenant fachada que la auditoría documentó).

---

## §3 — BUS DE EVENTOS, REGISTRO ÚNICO DE EVENTOS (RUE) Y BITÁCORA

### §3.1 El bus como único canal interdepartamental — FIJADO

Los cubos no se importan entre sí. Toda comunicación entre departamentos viaja por el bus como evento del RUE, o por un **servicio declarado** (§10) con contrato publicado. Gate de CI desde Bloque 3: linter de imports que prohíbe `departments.X` importando `departments.Y` fuera de servicios declarados. El bus existe (commits `26ba638`, `f26573e`, "sistema nervioso - bus de mensajes + bitácora"); este dossier lo canoniza y endurece.

### §3.2 Sobre canónico del evento — FIJADO

Todo evento publicado cumple este sobre (contrato de datos v1):

| Campo | Tipo | Regla |
|---|---|---|
| `event_id` | ULID | Único, ordenable por tiempo. Clave de idempotencia. |
| `ts` | ISO-8601 UTC | Momento de emisión. |
| `tenant_id` | string | Obligatorio. `plataforma` solo para el ámbito transversal (I2). |
| `tipo` | string | Debe existir en el RUE (§16). Convención `<cubo>.<entidad>.<hecho>` en pasado. |
| `schema_version` | entero | Versión del payload de ese `tipo`. |
| `origen` | string | `<cubo>.<rol>` emisor (p. ej. `comercial.prospector`, `plataforma.panel`). |
| `payload` | objeto | Definido por el dossier propietario del `tipo`. |
| `correlacion_id` | ULID | Hilo de trabajo (un lead, una liquidación). |
| `causa_id` | ULID/null | `event_id` del evento que causó éste. Cadena causal auditable. |
| `nivel_autonomia` | enum | Nivel vigente del tenant para la acción (§4). |
| `coste_ref` | ULID/null | Referencia al asiento de coste (§6) si la acción consumió modelo/servicio. |
| `hash_prev`, `hash` | hex | Encadenado por tenant (§3.4). |

**Entrega — FIJADO:** semántica *al-menos-una-vez*; los consumidores deduplican por `event_id` y sus efectos son idempotentes. Para eventos ligados a acciones IRREVERSIBLE-EXTERNA, el productor persiste antes de publicar (outbox simple sobre el almacén local). Consumidor ausente o lento jamás bloquea al productor: publicar es *fire-and-forget* con registro.

### §3.3 Registro Único de Eventos (RUE) — FIJADO

El RUE es la tabla maestra de tipos de evento y vive **en el repositorio como dato legible por máquina** (`eventos.yaml`), con este dossier (§16) como su emisión narrativa v1. Reglas de gobierno:

- Cada tipo tiene **un dossier propietario** (quien define su payload y lo versiona). D00 posee `plataforma.*`.
- Un dossier departamental **añade** tipos al RUE mediante su §6 (Anexo I); nunca modifica tipos ajenos.
- CI valida desde Bloque 3 que todo evento emitido en tests corresponde a un tipo del RUE con versión soportada. Evento desconocido = build roja (`plataforma.evento.rechazado` en runtime).

### §3.4 Bitácora encadenada por hash — FIJADO

La bitácora es el registro *append-only* de eventos, **por tenant**, con encadenado:

```
hash_0 = SHA256(tenant_id || fecha_alta)
hash_n = SHA256(hash_{n-1} || json_canonico(evento_sin_campos_hash))
```

Manipular un evento intermedio rompe la cadena desde ese punto y el verificador lo nombra. Comando de sustrato: `kaizen bitacora verificar --tenant <id>`. Esta cadena es, a la vez: la trazabilidad P3 de la Tesis, la evidencia de las salvaguardas 1 y 9 de la LIA (procedencia y trazabilidad de operaciones), y el anexo probatorio de la memoria NEOTEC (desarrollo experimental con registro íntegro). Herencia directa de OpenGravity.

**Diario — ABIERTO (lo cierra Bloque 3):** el Diario existente (commits `931c38c`, `3bf902a`, `8590a58`; consulta desde el Director) se canoniza como **proyección humana de la bitácora por tenant** más entradas narrativas del operador (`plataforma.diario.entrada`). El Bloque 3 inventaría la implementación real y documenta la unificación o su divergencia.

### §3.5 Versionado y deprecación de tipos — FIJADO

Cambio aditivo de payload (campo nuevo opcional) = misma versión mayor. Cambio que rompe = `schema_version`+1; el productor emite ambas versiones durante una ventana de **dos bloques** del consumidor más lento; los consumidores declaran rango soportado en su Anexo I. Retirar una versión sin ventana cumplida = violación de contrato, build roja.

### §3.6 Modos degradados del bus — FIJADO

- **Bus caído:** los cubos encolan localmente (outbox) y continúan su función núcleo (P1: arranque sin dependencias). Al volver, reemisión ordenada por `event_id`.
- **Consumidor opcional apagado:** el productor publica igual; degradación elegante documentada por el consumidor en su Anexo I (qué pierde el sistema sin él).
- **Consumidor obligatorio caído en cadena de aprobación:** las acciones IRREVERSIBLE-EXTERNA quedan retenidas, jamás se ejecutan "por timeout". La seguridad degrada cerrando, nunca abriendo.

---

## §4 — AUTONOMÍA GRADUADA Y MANDATO OPERACIONAL

### §4.1 Clasificación de acciones — FIJADO

Todo cubo cataloga sus acciones en tres clases (su Anexo I las enumera):

- **REVERSIBLE:** interna, deshacible (crear borrador, mover estado de pipeline con vuelta atrás, programar tarea).
- **IRREVERSIBLE-INTERNA:** destruye información propia (borrados, compactaciones). Exige confirmación o papelera con ventana.
- **IRREVERSIBLE-EXTERNA:** toca el mundo (email real, llamada real, factura emitida, compromiso ante tercero, publicación). **Regla de oro (FIJADO):** toda acción de esta clase pasa por un gate determinista independiente del LLM antes de ejecutarse. El LLM entiende; las reglas deciden. (Anatomía del fracaso, Anexo A §A3: Air Canada, McDonald's — el patrón único es salida probabilística conectada a consecuencia real sin gate determinista en medio.)

### §4.2 Niveles — FIJADO

| Nivel | Semántica operativa |
|---|---|
| **CERO** | El sistema propone; nada sale. El humano ejecuta fuera o con doble confirmación explícita. |
| **BAJA** | El sistema prepara y encola; **cada** acción IRREVERSIBLE-EXTERNA requiere aprobación humana individual (sandbox obligatorio existente: commit `41b6ed0`, "sin envío sin aprobación"). |
| **MEDIA** | Aprobación por lote o por plantilla pre-aprobada; las REVERSIBLE ejecutan solas dentro de presupuesto; las IRREVERSIBLE-EXTERNA fuera de plantilla siguen siendo individuales. |
| **ALTA** | Ejecuta dentro de mandato y límites; solo excepciones y umbrales escalan al humano. **Reservado:** ningún tenant opera en ALTA sin mandato escrito específico y sin historial de MEDIA sin incidentes. |

**Candado de umbrales (FIJADO, existente por diseño según Tesis §5):** los sub-agentes solo pueden endurecer umbrales y bajar su propio nivel efectivo; jamás relajarlos ni subirlo. Todo intento de relajación se rechaza y se registra (`plataforma.autonomia.cambiada` con veredicto `rechazado`). Prueba dura §13.6.

### §4.3 Aprobaciones — FIJADO

Cola de aprobación unificada del sustrato (una por tenant), con máquina de estados estricta:

```
PENDIENTE → APROBADA → EJECUTADA
     ↘ DENEGADA         ↘ (fallo) → REINTENTO/ANULADA
     ↘ CADUCADA (72 h sin decisión)      
APROBADA → REVOCADA (antes de ejecutar)
```

- Ejecución con *claim* atómico: una aprobación se ejecuta **exactamente una vez** (carrera doble-aprobación y aprobar-luego-revocar en batería §13.6).
- Caducidad a 72 h: un envío aprobado y olvidado es un envío peligroso; caduca y vuelve a proponerse si sigue vigente.
- Toda transición emite `plataforma.aprobacion.*` con identidad de quien decide.

### §4.4 Mandato Operacional por tenant — FIJADO

El Anexo III del contrato tipo (matriz de autonomía y aprobaciones) se materializa como **configuración por tenant legible por máquina**: nivel por clase de acción y por cubo, límites duros (máx. llamadas/día — hoy `KAIZEN_VOZ_MAX_LLAMADAS_DIA`, default 25 —, máx. emails/día, techo de coste diario §6.3, horarios permitidos de contacto), y plantillas pre-aprobadas para MEDIA. El sustrato **aplica** el mandato; los cubos lo consultan, no lo copian. Cambiar el mandato = acción del operador con registro; subir de nivel exige además conformidad escrita del cliente (contrato tipo, cláusula 4.2).

---

## §5 — VERIFICACIÓN: COMITÉ, QA TRANSVERSAL Y VERIFICACIÓN VISIBLE

### §5.1 Reconciliación con la realidad — FIJADO

El documento canónico anterior exigía un comité de 3 roles fijos con consenso 9-de-9. El código real (`core/opengravity/`, 1.537 líneas, sin commitear a fecha de auditoría) implementa 17 roles con umbral configurable 0,66/0,70. **Gana el código** (§0.3), y la intención del canon se absorbe como *preset*: el comité es un **servicio configurable** y las configuraciones con nombre sustituyen a la arquitectura única.

### §5.2 Presets de comité — FIJADO

| Preset | Composición | Umbral | Uso previsto | Clase de coste |
|---|---|---|---|---|
| `COMITE_LIGERO` | 3 voces, temperatura 0 | unanimidad | Gate bloqueante barato pre-aprobación (filtra basura antes de la cola humana) | TRIVIAL/ESTANDAR |
| `COMITE_ESTANDAR` | n roles del catálogo | 0,66 | Decisiones de calidad no bloqueantes; validación de borradores complejos | ESTANDAR |
| `COMITE_FORENSE` | muestreo post-hoc | 0,70 | Auditoría de lo ya ejecutado; genera hallazgos, no bloquea | ESTANDAR (lote) |

Reglas: temperatura 0 en todos los presets bloqueantes; prompts de comité **versionados** y su versión registrada en el evento (`plataforma.verificacion.emitida`); desacuerdo por debajo de umbral en modo preventivo = **denegar** (la seguridad cierra, §3.6). El catálogo completo de 17 roles queda documentado en AUDITORIA_D00/B6 con archivo:línea. ABIERTO: qué subconjunto de roles compone `COMITE_ESTANDAR` por tipo de decisión — lo cierra Bloque 6 midiendo acuerdo/coste sobre casos reales.

### §5.3 Modos — FIJADO

- **PREVENTIVO (bloqueante):** corre **antes** de que una acción entre en cola de aprobación (niveles CERO–MEDIA) o antes de ejecutar (ALTA). Obligatorio para toda IRREVERSIBLE-EXTERNA.
- **FORENSE (post-hoc):** muestreo configurable por tenant y cubo sobre lo ejecutado; sus hallazgos (`plataforma.verificacion.hallazgo`) alimentan la REEVALUACION y pueden endurecer umbrales automáticamente (candado §4.2: endurecer sí, relajar jamás).

### §5.4 QA absorbido: validación de borradores como servicio — FIJADO

Contrato del servicio (síncrono, del sustrato):

```
verificacion.validar_borrador(tenant_id, tipo_contenido, contenido, paquetes_politicas[]) 
→ { veredicto: APTO|NO_APTO, razones[], politicas_evaluadas[], version_prompts, hash }
```

- Los **paquetes de políticas** son enchufables: el paquete de marca lo provee el cubo Brand (D02) — con **versión embebida por defecto** mientras el tenant no tenga Brand contratado (arranque sin dependencias, P1). Esto canoniza al Brand Guardian existente como *proveedor de políticas* de este servicio y encuadra el bug BG-257 donde toca: la política es por tenant, el servicio es del sustrato.
- Todo veredicto emite evento con hash: la validación es trazable y citable ante el cliente.

### §5.5 Verificación visible — FIJADO

P3 de la Tesis, elevado a contrato: **la verificación invisible no vende**. Cada cubo declara en su Anexo I qué subconjunto de sus verificaciones ve el cliente en el panel (qué se hizo, qué se verificó, qué produjo). El sustrato provee el mecanismo (§7.3); el cubo decide el contenido. Un cubo sin sección de visibilidad no cruza su puerta v1.0.

---

## §6 — CONTABILIDAD DE COSTE Y ROUTER DE MODELOS

### §6.1 Libro mayor de coste — FIJADO

Todo consumo de modelo o servicio externo genera un asiento: `(ts, tenant_id, cubo, rol, clase_tarea, proveedor, modelo, tokens/unidades, coste_eur, event_id_causa)`. El contador existente (Tesis §8.2, "contador de coste ya existente") se extiende a este esquema en Bloque 4. El libro es la fuente única de: la cifra ABIERTA nº 1 de la Tesis (coste de servir por cubo/mes), el pricing del contrato tipo, y la partida de gasto justificable en ventanilla. **Export mensual CSV por tenant y por cubo es primitiva del sustrato.**

### §6.2 Clases de tarea y router — FIJADO

El router multi-modelo existente (`core/model_router.py`, 8 proveedores; herencia Shinobi: ClaseTarea con enrutado por coste; fail-fast `get_model_for_class`, commit `aa9dcb6`) queda canonizado con cuatro clases:

| Clase | Política de modelo | Ejemplos |
|---|---|---|
| `TRIVIAL` | El más barato validado | Extracción, normalización, resúmenes internos |
| `ESTANDAR` | Barato validado como equivalente (P6: glm-4.7-flash ≈ Haiku 4.5 a ~1/15 del coste) | Redacción asistida, investigación de lead |
| `CRITICA` | Modelo fuerte | Contenido que verá un tercero sin plantilla; decisiones de pipeline ambiguas |
| `COMITE` | Según preset §5.2 | Verificación |

Regla de equivalencia (FIJADO): ningún modelo entra en una clase sin validación registrada (mismo lote de tareas, veredicto de comité forense comparado). La degradación de proveedor cae dentro de la misma clase (prueba dura §13.9), nunca dos clases hacia abajo en silencio.

### §6.3 Techos y escalera de degradación — FIJADO

Se adopta del canon anterior la variable `LIMITE_COSTE_DIARIO_EUR` (una de sus tres ideas supervivientes, §11.1): techo diario **por tenant** (en su mandato §4.4) y techo **global de plataforma**. Al alcanzar techo:

1. Downgrade de clase efectiva (CRITICA→ESTANDAR salvo lista blanca del mandato) →
2. Diferir lo no urgente (colas conservadas, nada se pierde) →
3. Pausar acciones nuevas IRREVERSIBLE-EXTERNA; **las ya aprobadas y urgentes completan** →
4. Evento `plataforma.coste.techo_alcanzado` + aviso al operador.

Jamás parada silenciosa; jamás pérdida de acciones aprobadas. Prueba dura §13.2 (runaway) verifica la escalera completa.

---

## §7 — SUPERFICIE DE DIRECCIÓN: PANEL DEL DIRECTOR Y CLI

### §7.1 Las cuatro primitivas del Director — FIJADO

P7 hecho interfaz. Toda capacidad de dirección se reduce a cuatro verbos, disponibles en panel y CLI:

- **VER:** estado por tenant (pipeline, colas, bitácora/diario, coste del día, nivel de autonomía vigente).
- **APROBAR:** la cola unificada §4.3, con contexto suficiente para decidir sin salir de la vista.
- **DIRIGIR:** órdenes a cubos (lanzar prospección, ampliar radio, preparar liquidación) — cada orden es un evento con `origen: plataforma.panel|cli` e identidad del operador.
- **CONFIGURAR:** mandato, techos, niveles (con las reglas §4.4), tenants (§2.3).

**Contexto de tenant explícito (FIJADO):** toda vista y todo comando operan bajo un tenant seleccionado visible; ningún comando mutador sin tenant explícito. Es la defensa de interfaz contra la clase de error BG-257.

### §7.2 Estado real — DIVERGENTE (resolución en Bloques 1 y 5)

- El panel existe (`api/server.py` + frontend según Manual de Marca, commits `63c9d40`, `187c6a3`; auth por `KAIZEN_TOKEN`).
- La CLI existe pero está **rota en su mitad crítica**: `kaizen.py:1365` redefine el grupo `comercial` declarado en `kaizen.py:276`, dejando inalcanzables ~1.000 líneas, incluidas la aprobación de envíos y el disparo de llamadas (hallazgo crítico de auditoría). Resolución: Bloque 1 renombra/reagrupa con test de humo que invoca **todos** los comandos registrados (`--help` walk) para que una colisión futura rompa CI.

### §7.3 Vista de cliente — FIJADO (construcción en Bloque 6)

Subconjunto de panel de **solo lectura por tenant** para el cliente final: su pipeline, sus verificaciones visibles (§5.5), su resultado en unidades verificables. Autenticación separada del operador, alcance sellado por I1. Es la pieza que convierte P3 en argumento de venta y el panel en parte del producto de cada cubo.

### §7.4 Identidad y registro — FIJADO

Toda acción mutadora desde la superficie registra identidad (operador o cliente-lectura no muta). Sesiones con caducidad. ABIERTO: multi-operador (tokens por persona) — lo cierra la primera incorporación; el esquema de eventos ya lo soporta (`origen` + identidad).

---

## §8 — SEGURIDAD, PÁNICO Y CUMPLIMIENTO DEL SUSTRATO

### §8.1 Secretos y webhooks — FIJADO

- Secretos solo en `.env`/gestor externo; jamás en repo. Escaneo de secretos sobre árbol de trabajo en CI (Bloque 7); la revisión del historial se hace una vez en B7 y se documenta.
- Verificación HMAC de webhooks **obligatoria**: `KAIZEN_VOICE_SIG_BYPASS` debe ser `false`/ausente en producción (hallazgo histórico C3). CI aserta la configuración de producción con test explícito (R2: primero el test que falla si el bypass está abierto).
- Credenciales por tenant donde el canal lo exija (I3): número saliente, remitente, firma.

### §8.2 Interruptores y pánico — FIJADO

Los interruptores maestros existentes (`KAIZEN_ENVIO_HABILITADO`, `SDR_VOICE_ENABLED`) se elevan a **palancas formales de tres niveles**: por clase de acción × por tenant × global. El **pánico** (herencia Shinobi) corta toda acción IRREVERSIBLE-EXTERNA de la plataforma en ≤1 ciclo de evento, conserva colas y estado, emite `plataforma.panico.activado`, y su desactivación exige acción explícita del operador con registro. Prueba dura §13.5 lo verifica bajo carga con envíos ya aprobados en cola.

### §8.3 Voz y art. 50 — FIJADO

Estado operativo: **voz OFF**. De las 8 correcciones de la auditoría de junio, la única no confirmada es el *disclosure* de IA en el agente de voz desplegado (redeploy pendiente). Regla: la voz **no puede reactivarse** hasta que exista test que verifique el disclosure en el primer turno de la conversación desplegada, más el cumplimiento del régimen vigente de llamadas comerciales. La palanca `SDR_VOICE_ENABLED` queda condicionada a ese test en verde (gate de configuración, Bloque 7).

### §8.4 Cumplimiento como primitivas — FIJADO

Lo firmado se convierte en mecanismo del sustrato:

| Obligación (fuente) | Primitiva del sustrato |
|---|---|
| Procedencia registrada de cada dato (LIA §3.1) | Campo `fuente`+`fecha_obtencion` obligatorio en entidades de contacto; sin fuente, el dato no entra |
| Oposición = supresión inmediata + lista de exclusión (LIA §3.4) | Lista de exclusión **por plataforma** (dato mínimo, indefinida) consultada como gate determinista pre-envío/pre-llamada |
| Lista Robinson pre-llamada (LIA §3.6) | Gate determinista en la ruta de llamada; sin consulta registrada, no hay llamada |
| Retención 12 meses sin relación (LIA §3.8) | Tarea de retención por tenant con acta (`plataforma.retencion.ejecutada`) |
| Export a la baja (contrato tipo, cl. 9) | §2.4 |
| Disociación para dato agregado (contratos cl. 6/8.2) | Frontera §9.2: nada cruza a AGREGADO sin función de disociación registrada |

### §8.5 Copias y restauración — FIJADO

- **Código:** R1 (commit por bloque) + push a remoto privado. 
- **Datos:** snapshot diario por tenant (JSON/SQLite) con verificación de integridad; simulacro de restauración en máquina limpia como prueba dura §13.8. El fantasma de los 35 días se exorciza por test, no por promesa.

---

## §9 — PERSISTENCIA, PROPIEDAD DEL DATO Y DIETA DE DEPENDENCIAS

### §9.1 Motor por defecto — FIJADO

Local-first (P6): JSON/SQLite **por tenant** (existente: `JsonKnowledge` por defecto, commit `57e6dcd`, "NO SE PIERDE NADA"). Umbral de migración medido, no intuido — se instrumentan tres métricas por tenant: p95 de latencia de consulta del pipeline, tamaño del almacén, escritores concurrentes. ABIERTO: valores de umbral — los fija la primera medición trimestral en REEVALUACION_D00.

### §9.2 Propiedad del dato — FIJADO (espejo de los contratos)

| Clase | Contenido | Reglas |
|---|---|---|
| `DATO_CLIENTE` | Cartera, precios, pipeline, historial del tenant | Exportable e íntegramente borrable (§2.4). Jamás visible a otro tenant (I1). |
| `DATO_PLATAFORMA` | Código, prompts, metodología, argumentarios genéricos | De ZapWeave/[S.L.] (contratos, cl. 6/9). |
| `DATO_AGREGADO` | Patrones disociados de conversión, cadencias, objeciones por segmento (P8, Data Moat 2.0) | Solo cruza la frontera de tenant mediante función de disociación **registrada** (qué se agregó, cuándo, con qué método). Sin identificación de tenant ni de terceros. |

El bucle resultado→ajuste (P8) es del sustrato en su mecánica (captura y frontera) y de cada cubo en su contenido (qué señal, qué ajuste): cada Dxx lo declara en su Anexo I.

### §9.3 Primitivas de datos — FIJADO

`exportar_tenant(id)`, `borrar_dato_cliente(id, acta)`, `retencion(id)`, `snapshot(id)`, `verificar_bitacora(id)`. Cinco comandos, cinco tests.

### §9.4 Dieta de dependencias — FIJADO

La auditoría encontró Redis, Neo4j, Postgres y LangGraph como dependencias activas e importables; los 7 tests saltados de la suite son exactamente los de backends reales y LLM real: **la suite valida el simulador, no la producción**. Resolución:

- **Neo4j / Postgres:** adaptadores a estado **EXPERIMENTAL** (existen — Block A, commit `9496dbb`, con docker-compose — pero nunca ejecutados contra infraestructura real). Fuera de la ruta de producción y del DoD v1.0; `requirements.txt` se divide en núcleo y experimental. Se reactivan solo si §9.1 dispara umbral, y entonces sus tests corren en CI contra backend dockerizado — nunca "de fe".
- **Redis:** ABIERTO — Bloque 3 inventaría si alguna ruta de producción del bus lo usa. Si no: EXPERIMENTAL. Si sí: entra al DoD con test real dockerizado.
- **LangGraph:** ABIERTO — mismo inventario en Bloque 3; presunción EXPERIMENTAL salvo evidencia de ruta de producción.
- **Tests LLM reales:** siguen gateados tras `KAIZEN_TEST_LLM=1` (commit `d3a46bc`), pero dejan de ser opcionales para cruzar puertas: cada puerta de bloque que toque rutas LLM exige una pasada con LLM real registrada en la AUDITORIA del bloque.

---

## §10 — CONTRATOS DE INTEROPERABILIDAD: CÓMO DECLARA UN DOSSIER DEPARTAMENTAL

### §10.1 La declaración obligatoria — FIJADO

Todo Dxx incluye, cumplimentada, la plantilla del Anexo I: qué **publica**, qué **consume**, qué **servicios** ofrece o requiere. Cada fila se evalúa en cinco dimensiones, siempre las mismas:

1. **Contrato de datos** — tipo RUE + versión de esquema (o firma del servicio).
2. **Modo degradado** — qué hace el departamento si la contraparte no está (P1: nadie requiere a nadie para arrancar).
3. **Verificación aplicable** — qué preset/gate ve pasar esa interacción (§5).
4. **Regla de cumplimiento** — qué obligación de §8.4 la cubre, si toca el exterior.
5. **Coste** — clase de tarea imputada (§6.2).

### §10.2 Reglas duras

- Sin fila en el Anexo I, no hay interacción: lo no declarado no existe (y el linter de imports §3.1 lo hace físico).
- Un servicio síncrono declarado (p. ej. `verificacion.validar_borrador`, futura `brand.politicas`) publica firma, versionado y latencia esperada; su ausencia tiene modo degradado obligatorio.
- Los eventos `plataforma.*` son consumibles por cualquier cubo; los `<cubo>.*` requieren fila de consumo en el dossier consumidor.

---

## §11 — ESTADO REAL VS. CANON: DIVERGENCIAS, ABSORCIONES Y DESCARTES

### §11.1 Resolución de `KAIZEN_ARQUITECTURA_CANONICA_v1_0.md` — FIJADO

Aquel documento queda **sustituido** por D00 y archivado como histórico. Veredicto pieza a pieza (las once contradicciones verificadas por la auditoría, agrupadas):

| Exigía el canon anterior | Realidad verificada | Resolución D00 |
|---|---|---|
| Reconstrucción desde cero en `D:\Kaizen`, árbol `sustrato/` + `cubos/` | 26.130 líneas funcionando, 603 tests verdes | **Descartada la reconstrucción inmediata.** El vocabulario `sustrato/cubos` se adopta ya como lenguaje canónico (este dossier lo usa); la migración física es DIVERGENTE-DIFERIDA: es la pista de re-arquitectura del proyecto de I+D financiable. Los contratos de D00 están escritos para que **ambas** implementaciones (actual y futura) deban satisfacerlos: el contrato sobrevive a la re-arquitectura. |
| Mono-cliente Laboratorio (`CLIENTE_ID`) | Tres tenants reales operando | **Descartado.** Multi-tenant es ley (§2). `CLIENTE_ID` rechazada como variable. |
| Comité de 3 roles, consenso 9-de-9 | 17 roles, umbral 0,66/0,70 configurable | **Absorbido como preset** `COMITE_LIGERO` (§5.2). Gana el código; la intención sobrevive con nombre. |
| Prohibición de Redis/Neo4j/Postgres/LangGraph | Presentes como dependencias activas | **Absorbido como dieta**, no como prohibición: cuarentena EXPERIMENTAL con condiciones de retorno medibles (§9.4). |
| Prohibición de construir segundo departamento "en esta fase" | Cuatro departamentos nuevos ya construidos | **Revocada junto con la Decisión 3** (NC-2026-07-08). La protección migra del calendario a la evidencia (§0.4, §0.6). |
| `LIMITE_COSTE_DIARIO_EUR` | No implementada | **Adoptada** (§6.3, Bloque 4). Idea superviviente nº 1. |
| Auditoría antes que construcción (§0.2 del canon) | Cumplida el 2026-07-02 | **Adoptada como doctrina permanente** (R2, R4, ciclo §0.6). Idea superviviente nº 2. |
| Protocolo de parada obligatorio (§0.6 del canon) | Interruptores sueltos | **Adoptado y endurecido** como pánico formal (§8.2). Idea superviviente nº 3. |

### §11.2 Hallazgos críticos vigentes y su encuadre — DIVERGENTE

| Hallazgo (auditoría 2026-07-02) | Evidencia | Encuadre y bloque |
|---|---|---|
| Brand Guardian fuerza `company="laboratorio"` para todo tenant | `departments/comercial/brand_guardian.py:257` | Violación de I1/I3; espécimen de la regla anti-literales §2.2. **Bloque 1.** |
| Colisión CLI: grupo `comercial` sobrescrito; ~1.000 líneas inalcanzables (aprobación de envíos, disparo de voz) | `kaizen.py:1365` vs `kaizen.py:276` | Rotura de G5/§7. **Bloque 1**, con test de humo permanente. |
| `python-multipart` ausente de `requirements.txt`; 7 tests de webhooks Twilio truenan (500 en producción) al instalar limpio | Ejecución real de suite en entorno limpio | Rotura de instalabilidad. **Bloque 1**, con CI de instalación limpia permanente. |
| 7 tests saltados = backends reales + LLM real | Salida de `pytest` | Resuelto por política §9.4 y regla de puertas con LLM real. **Bloques 2–3.** |
| 35 días sin commit (último real 2026-05-28) | `git log` | Resuelto por R1 + §13.8. **Bloque 1** (puesta al día) y para siempre. |
| Disclosure de voz sin confirmar en despliegue | Código admite redeploy pendiente | Gate §8.3. **Bloque 7.** |

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES Y PUERTAS

Ciclo §0.6 aplicado. Cada bloque termina en **commit + entrada de AUDITORIA_D00** (R1, R4). Orden por dependencia; sin estimaciones de calendario: las puertas ordenan, no las fechas.

### B0 — Auditoría previa · **CUMPLIDO**
Realizada el 2026-07-02 con método de evidencia citable. Este dossier la referencia como línea base; no se repite trabajo hecho.

### B1 — Estabilización quirúrgica
1. Puesta al día del historial: commit de todo el árbol vivo, push a remoto privado, tag `pre-D00`.
2. Test rojo + corrección de BG-257 (tenant parametrizado, literal eliminado).
3. Test rojo + corrección de la colisión CLI (reagrupado; *walk* de `--help` sobre todos los comandos como test de humo permanente); las ~1.000 líneas recuperadas quedan cubiertas por al menos un test de invocación cada ruta crítica (aprobación, disparo de voz — con voz en dry-run).
4. `python-multipart` a `requirements.txt`; CI de instalación limpia (entorno virgen + `pip install -r` + suite completa).
**PUERTA B1:** suite verde en entorno limpio desde `requirements.txt`; los tres defectos con test de regresión en verde; `git log` al día; tag creado.

### B2 — Tenancy endurecido
1. Barrido de imposición de `tenant_id` en toda ruta de producción (core/departments/api).
2. Gate de CI anti-literales de tenant (§2.2).
3. Registro de tenants (§2.3) con las tres fichas reales; credenciales por tenant auditadas (I3).
4. Primitivas §9.3 implementadas: export, borrado con acta, snapshot, retención, verificación de bitácora (esta última puede aterrizar en B3 si la cadena aún no existe: se anota).
5. Clase de test universal de aislamiento implementada (la que heredará todo cubo): dos tenants con datos adversarios, ejecución de toda operación pública, fuga cero.
**PUERTA B2:** batería de aislamiento verde sobre 3 tenants reales + 1 sintético adversario; export y borrado demostrados con acta; gate anti-literales activo en CI.

### B3 — RUE y bitácora canónicas
1. `eventos.yaml` en repo con la semilla §16; validador en CI (evento fuera de registro = build roja).
2. Sobre canónico §3.2 aplicado a todo productor; deduplicación por `event_id` en consumidores; outbox para IRREVERSIBLE-EXTERNA.
3. Cadena de hash por tenant + comando `bitacora verificar`.
4. Inventario Redis/LangGraph (§9.4) con veredicto y, si procede, cuarentena efectiva (split de requirements).
5. Diario: inventario de implementación real y acta de unificación con la bitácora (cierra el ABIERTO §3.4).
**PUERTA B3:** todo evento emitido por la suite valida contra RUE; verificación de cadena en verde sobre bitácoras reales de los 3 tenants; evento desconocido rompe CI (demostrado con test negativo); veredicto de dependencias firmado.

### B4 — Coste y techos
1. Libro mayor §6.1 (extensión del contador existente) con imputación completa.
2. `LIMITE_COSTE_DIARIO_EUR` por tenant (mandato) y global; escalera §6.3.
3. Export CSV mensual por tenant/cubo.
**PUERTA B4:** prueba dura de runaway (§13.2) en verde: techo muerde, escalera se activa en orden, ninguna acción aprobada se pierde, evento emitido; primer export mensual real generado.

### B5 — Autonomía y aprobaciones unificadas
1. Catálogo de acciones por cubo (empezando por Comercial, el existente) con clase §4.1.
2. Mandato por tenant legible por máquina (§4.4) aplicado por el sustrato; los valores actuales (p. ej. cuota de voz 25/día) migran del `.env` al mandato.
3. Cola de aprobación unificada con la máquina de estados §4.3 (claim atómico, caducidad 72 h) visible en panel y CLI.
4. Candado de umbrales con test de intento de relajación rechazado y registrado.
**PUERTA B5:** matriz acción×nivel ejecutada en test para las tres clases de acción en los cuatro niveles; carreras de §13.6 en verde; cambio de mandato registrado con identidad.

### B6 — Verificación como servicio y superficie visible
1. Presets §5.2 sobre el motor de 17 roles existente; prompts versionados.
2. `verificacion.validar_borrador` como servicio del sustrato; paquete de políticas de marca enchufado (embebido por defecto, por tenant).
3. Eventos de verificación + vista de cliente §7.3 (solo lectura, alcance sellado por I1) mostrando verificaciones visibles y resultado.
**PUERTA B6:** determinismo demostrado (mismo borrador → mismo veredicto, N=20, temperatura 0); veredicto trazable con hash en bitácora; un tenant real viendo sus verificaciones en la vista de cliente; pasada con LLM real registrada (§9.4).

### B7 — Seguridad, pánico y restauración
1. Palancas de tres niveles §8.2 + pánico ≤1 ciclo con conservación de colas.
2. Aserción CI de bypass HMAC cerrado; escaneo de secretos (árbol + revisión única de historial documentada).
3. Gate de voz condicionado al test de disclosure (§8.3) — la palanca no abre sin él.
4. Snapshot diario + simulacro de restauración en máquina limpia.
**PUERTA B7:** §13.5 (pánico bajo carga) y §13.8 (restauración) en verde; configuración de producción pasando las aserciones de seguridad; acta del simulacro en AUDITORIA_D00.

**Cierre del programa:** batería §13 completa en verde → ensayo §14 → checklist §15 → REEVALUACION_D00 → v1.0 del sustrato.

---

## §13 — BATERÍA DE PRUEBAS DURAS DEL SUSTRATO

Definidas **antes** de construir (R3 aplicado al diseño). Cada una con umbral binario; "casi" = rojo.

| # | Prueba | Montaje | Umbral de éxito |
|---|---|---|---|
| 13.1 | **Aislamiento adversario** | 2 tenants con datos envenenados (nombres, emails y textos del A diseñados para aflorar en B); ejecución de toda operación pública de sustrato y cubos activos | Fuga cero en salidas, logs, eventos, panel y export; gate anti-literales verde |
| 13.2 | **Runaway de coste** | Agente en bucle consumiendo clase ESTANDAR hasta rebasar techo del tenant | Escalera §6.3 en orden; acciones aprobadas completan; evento emitido; gasto ≤ techo + margen de 1 acción |
| 13.3 | **Caos de bus** | Consumidor caído, consumidor lento, entrega duplicada, entrega desordenada | Productores no bloquean; deduplicación por `event_id` efectiva; cero efectos dobles en IRREVERSIBLE-EXTERNA; reemisión ordenada al recuperar |
| 13.4 | **Integridad de bitácora** | Manipulación de un evento intermedio en frío | `bitacora verificar` falla y nombra el punto exacto de ruptura |
| 13.5 | **Pánico bajo carga** | 100 acciones aprobadas en cola (envíos dry-run) mientras se ejecutan; pánico a mitad | 0 acciones externalizadas tras el corte; estado consistente; reanudación sin pérdida ni duplicado |
| 13.6 | **Carreras de aprobación** | Doble-aprobación concurrente; aprobar-y-revocar concurrente; intento de relajación de umbral por sub-agente | Ejecución exactamente-una-vez; revocación gana si llega antes del claim; relajación rechazada y registrada |
| 13.7 | **Desacuerdo de comité** | Lote de borradores frontera (sembrados: N violaciones conocidas) contra preset preventivo y forense | Preventivo: bajo umbral = denegar, cero falsos APTO sobre las violaciones sembradas; forense: muestreo caza ≥ el % pre-registrado de las sembradas |
| 13.8 | **Restauración** | Máquina limpia + último snapshot + repo remoto | Suite verde; cadenas de hash íntegras; export de tenant idéntico byte a byte al de origen |
| 13.9 | **Degradación de proveedor** | Proveedor primario de una clase devolviendo 5xx | Fallback dentro de la misma clase; coste imputado al proveedor real; forense sobre muestras no detecta caída de clase |
| 13.10 | **Higiene de secretos y config** | Escaneo de árbol; carga de config de producción | Cero secretos en árbol; bypass HMAC cerrado; voz OFF sin su gate |

---

## §14 — PRUEBA DE VIDA REAL PRE-REGISTRADA · VR-D00-01

El sustrato no se vende: su vida real es **sostener la operación real**. Pre-registro conforme al Anexo II (se firma antes de iniciar; las porterías no se mueven):

- **Ventana:** 14 días naturales continuos.
- **Ámbito:** los 3 tenants reales con el cubo Comercial operando su actividad normal.
- **Métricas y umbrales (todos obligatorios):**
  1. Incidentes de fuga entre tenants: **0** (un solo incidente = fallo total del ensayo y reinicio tras corrección).
  2. Eventos válidos contra RUE: **100%** de los emitidos.
  3. Cadena de hash íntegra en los 3 tenants al cierre: **sí**.
  4. Techo de coste: ≥1 activación **provocada** de techo con escalera correcta y sin pérdida de aprobadas.
  5. Pánico: ≥1 simulacro en producción (fuera de horario de contacto) con corte verificado ≤1 ciclo y reanudación limpia.
  6. Export mensual de coste generado y archivado (alimenta cifra ABIERTA nº 1 de la Tesis).
  7. Disponibilidad de la superficie de dirección: las 4 primitivas §7.1 usadas de verdad, con registro.
- **Resultado:** acta VR-D00-01 en AUDITORIA_D00 con salidas literales. Éxito = todos los umbrales; cualquier otro resultado = lista de correcciones + re-ensayo.

---

## §15 — PUERTA v1.0: CHECKLIST DoD OPERATIVO Y CRITERIOS DE FALSACIÓN

### §15.1 Checklist de puerta (todo binario)

- [ ] Puertas B1–B7 cruzadas, cada una con commit y entrada de auditoría.
- [ ] Batería §13 completa en verde, con salidas archivadas.
- [ ] VR-D00-01 superado con acta.
- [ ] RUE publicado en repo y aplicado por CI (test negativo demostrado).
- [ ] Plantilla Anexo I **adoptada por D01** con sus filas validando contra el RUE (la prueba de que los contratos sirven es que el primer cubo declara contra ellos sin fricción).
- [ ] AUDITORIA_D00 al día (método R4) y REEVALUACION_D00 emitida con veredicto.
- [ ] Cero filas DIVERGENTE sin resolver; las DIVERGENTE-DIFERIDA listadas con dueño y condición de reapertura.
- [ ] Este dossier actualizado a la verdad construida (bump §0.7 si procede).

### §15.2 Falsación del sustrato

1. Si el aislamiento (I1–I3) no puede garantizarse sin reescritura mayor → parada de altas de cubos y tenants; la re-arquitectura diferida pasa de futura a inmediata.
2. Si el coste de servir del propio sustrato supera de forma sostenida el **15%** del coste total por tenant (medido en el libro §6.1 durante un mes) → el sustrato pesa demasiado: simplificar antes de crecer. (Umbral inicial; lo recalibra la primera REEVALUACION con datos.)
3. Si dos cubos necesitan sistemáticamente saltarse el bus o el RUE para funcionar → el contrato está mal, no los cubos: se revisa D00, no se parchea alrededor.
4. Si el ensayo VR falla dos veces por la misma causa raíz → esa área vuelve a fase de dossier: construir más no arregla especificar mal.

---

## §16 — REGISTRO ÚNICO DE EVENTOS v1 (SEMILLA)

Propietario de `plataforma.*`: D00. Los tipos `comercial.*` se listan con propietario D01 (payload y versión los fija su dossier; aquí se reserva el nombre). Estado: **E** = existente hoy en alguna forma (evidencia en auditoría/commits), **P** = planificado por bloque.

| Tipo | Propietario | Productor → Consumidores previstos | Estado |
|---|---|---|---|
| `plataforma.tenant.creado` / `.pausado` / `.baja` | D00 | Registro §2.3 → todos | P·B2 |
| `plataforma.aprobacion.solicitada/.concedida/.denegada/.revocada/.caducada` | D00 | Cola §4.3 ↔ superficie §7 | E parcial (sandbox) → canónico en B5 |
| `plataforma.autonomia.cambiada` | D00 | Mandato §4.4 → bitácora, panel | P·B5 |
| `plataforma.verificacion.emitida` / `.hallazgo` | D00 | Comité §5 → cubo solicitante, panel, forense | E parcial (motor existe) → canónico en B6 |
| `plataforma.coste.registrado` / `.techo_alcanzado` | D00 | Libro §6 → panel, escalera | E parcial (contador) → canónico en B4 |
| `plataforma.panico.activado` / `.desactivado` | D00 | Palancas §8.2 → todos | P·B7 |
| `plataforma.diario.entrada` | D00 | Operador/cubos → Diario | E (Diario existe) → mapeo en B3 |
| `plataforma.retencion.ejecutada` / `plataforma.datos.exportados` / `.borrados` | D00 | Primitivas §9.3 → bitácora, acta | P·B2 |
| `plataforma.evento.rechazado` | D00 | Validador RUE → operador | P·B3 |
| `comercial.lead.descubierto` / `.cualificado` / `.investigado` | D01 | Prospector/Investigador → pipeline, panel | E |
| `comercial.contacto.preparado` / `.enviado` | D01 | Redactor/ejecutor → aprobaciones, bitácora | E (vía sandbox) |
| `comercial.llamada.realizada` | D01 | Voz (OFF) → bitácora, compromisos | E (código; palanca cerrada §8.3) |
| `comercial.compromiso.detectado` / `.creado` | D01 | CompromisoDetector/AE → pipeline, panel, Diario | E (validado contra transcript real) |
| `comercial.pipeline.transicion` | D01 | Máquina de estados → panel, atribución | E |
| `comercial.pedido.atribuido` | D01 | Atribución → finanzas (liquidación 50/50), panel cliente | P (definición formal en D01 §5) |
| `comercial.briefing.emitido` | D01 | Briefing → operador/Diario | E |
| `brand.validacion.emitida` | D02 | Paquete de políticas vía §5.4 → solicitante | E (guardian) → contrato en D02 |
| `finanzas.factura.emitida` / `finanzas.cobro.registrado` / `finanzas.liquidacion.calculada` | D04 | Finanzas → panel, contrato Laboratorio Anexo I | P (D04) |

Regla de crecimiento: nombres reservados aquí; payloads y versiones, en el dossier propietario. Todo tipo nuevo entra por PR que toca `eventos.yaml` + Anexo I del dossier correspondiente.

---

## §17 — GLOSARIO CANÓNICO

**Tenant** · empresa cliente con ficha en §2.3. **Cubo** · departamento sintético vendible (D01–D08). **Sustrato** · este documento hecho código: las cinco garantías §1.1. **Operador/Director** · quien dirige la plataforma vía §7. **Rol/Sub-agente** · unidad de trabajo dentro de un cubo. **Evento** · registro §3.2 de tipo RUE. **RUE** · registro único de tipos de evento (§16 + `eventos.yaml`). **Bitácora** · log append-only encadenado por tenant. **Diario** · proyección humana de la bitácora + entradas del operador. **Mandato Operacional** · configuración por tenant de autonomía y límites (§4.4). **IRREVERSIBLE-EXTERNA** · acción que toca el mundo; siempre con gate determinista. **Comité** · servicio de verificación multi-agente (§5). **Clase de tarea** · nivel de coste/capacidad de modelo (§6.2). **DATO_CLIENTE / PLATAFORMA / AGREGADO** · clases de propiedad §9.2. **Puerta** · condición binaria de salida de bloque o de versión. **Ensayo VR** · prueba de vida real pre-registrada (Anexo II). **FIJADO/ABIERTO/DIVERGENTE(-DIFERIDA)/EXPERIMENTAL** · estados §0.2.

---

## ANEXO I — PLANTILLA DE DECLARACIÓN DE INTEROPERABILIDAD (obligatoria en todo Dxx, sección §6 del dossier departamental)

**A. Eventos que PUBLICA**

| Tipo (RUE) | `schema_version` | Payload (resumen) | Frecuencia/volumen esperado | Garantía (outbox sí/no) | Verificación aplicable | Cumplimiento (§8.4) | Clase de coste |
|---|---|---|---|---|---|---|---|

**B. Eventos que CONSUME**

| Tipo (RUE) | Versiones soportadas | Obligatorio/Opcional | **Modo degradado si ausente** (qué pierde el sistema, qué sigue funcionando) | Idempotencia (cómo deduplica) |
|---|---|---|---|---|

**C. Servicios (síncronos) que OFRECE / REQUIERE**

| Servicio | Firma (entrada→salida) | Versión | Latencia esperada | Modo degradado | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|

**D. Catálogo de acciones** (clase §4.1 × nivel por defecto §4.2) · **E. Señal del bucle resultado→ajuste (P8)**: qué captura, dónde ajusta, frontera de disociación · **F. Visibilidad de cliente (§5.5)**: qué ve el tenant en su panel.

---

## ANEXO II — PLANTILLA DE PRE-REGISTRO DE ENSAYO DE VIDA REAL

```
ENSAYO: VR-Dxx-NN            FECHA DE REGISTRO (previa al inicio): ____
DEPARTAMENTO/ÁMBITO: ____    TENANT(S) REAL(ES): ____
VENTANA: __ días (inicio previsto ____)
HIPÓTESIS OPERATIVA: qué debe demostrar el sistema, en una frase.
ACCIONES REALES PREVISTAS: N = ____ (tipo y volumen)
MÉTRICAS Y UMBRALES (binarios, cerrados aquí):
  M1: ____  umbral: ____
  M2: ____  umbral: ____
CRITERIO DE FALLO TOTAL (aborta y reinicia): ____
DATOS QUE ALIMENTA (cifras ABIERTAS de la Tesis / pricing / memoria I+D): ____
FIRMA DEL PRE-REGISTRO (commit hash del registro): ____
--- tras la ejecución ---
ACTA: resultados literales por métrica · VEREDICTO: ÉXITO/FALLO · 
CORRECCIONES DERIVADAS: ____ · DESTINO: AUDITORIA_Dxx + REEVALUACION_Dxx
```

---

*Fin de KAIZEN-D00 v1.0. Emitido el 2026-07-08. Toda afirmación sobre el estado del código procede de la auditoría del 2026-07-02 con evidencia archivo:línea o de mensajes de commit citados por hash; lo no verificado con ejecución real está marcado ABIERTO o DIVERGENTE. Próximo documento de la serie: KAIZEN-D01 (Comercial), que declara contra este registro. La primera línea de trabajo derivada de este dossier no es escribir: es el Bloque 1.*
