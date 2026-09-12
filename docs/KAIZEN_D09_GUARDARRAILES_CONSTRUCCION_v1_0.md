# KAIZEN-D09 — GUÍA DE CONSTRUCCIÓN, FE DE ERRATAS Y GUARDARRAÍLES
## Serie de dossieres KAIZEN · Documento transversal (no es un departamento)

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-09
**Versión:** 1.0
**Naturaleza:** auditoría adversaria de D00–D08 v1.0 + contrato de disciplina para el agente constructor (Claude Code u otro).
**Regla de precedencia:** las Resoluciones (§3) y Erratas (§2) de este documento **corrigen** a D00–D08 v1.0 con efecto inmediato. Los dossieres NO se editan en silencio (coherencia con su propia disciplina de versionado): cada uno incorporará su lista de cambios (§10) al emitir v1.1. Hasta entonces, ante conflicto entre un dossier v1.0 y D09, **gana D09**.
**Método:** lectura completa de los 9 documentos + verificación cruzada por grep de cada referencia inter-dossier (servicios declarados vs. consumidos, eventos declarados en Anexos A vs. consumidos en §5.B, nombres de bloques, literales de tenant, fechas legales). Todo hallazgo cita archivo:línea. Nada de memoria.

---

## ÍNDICE

- §0 — Para quién es este documento y cómo usarlo
- §1 — Resumen de auditoría: los siete hallazgos que más duelen
- §2 — Fe de erratas verificadas (archivo:línea, error → corrección, severidad)
- §3 — Resoluciones vinculantes (contradicciones entre dossieres, resueltas)
- §4 — Gaps de contrato que bloquean construcción
- §5 — Guardarraíles de producción (GR: lo que fallará en el mundo real tal como está escrito)
- §6 — Guardarraíles regulatorios con reloj (GL: fechas que no negocian)
- §7 — Disciplina del agente constructor (DC: reglas operativas innegociables)
- §8 — Grafo de dependencias integrado y reloj inverso
- §9 — Checklist pre-código (binaria; si hay un NO, no se escribe código)
- §10 — Mapa de cambios v1.1 por documento

---

## §0 — PARA QUIÉN ES ESTE DOCUMENTO Y CÓMO USARLO

Este documento tiene dos lectores:

1. **El agente de IA que construya** (Claude Code o equivalente). Para él, D09 es lectura obligatoria ANTES de cualquier bloque, junto con D00. Las reglas DC (§7) son su contrato de conducta. Las resoluciones R (§3) le dicen qué hacer cuando dos dossieres se contradicen — que se contradicen, y aquí está la prueba.

2. **El operador (Iván)**, como registro de qué estaba roto en los v1.0 y por qué los v1.1 dirán lo que dirán.

Regla de lectura: nada en este documento es opinión estilística. Cada errata tiene línea. Cada contradicción tiene las dos líneas que chocan. Cada guardarraíl de producción nombra el mecanismo real de fallo.

---

## §1 — RESUMEN DE AUDITORÍA: LOS SIETE HALLAZGOS QUE MÁS DUELEN

1. **La clase de error BG-257 se reprodujo en los propios dossieres.** El tenant `laboratorio` aparece como `alcayana` en dos pre-registros VR (D05:356, D08:365). El mismo tipo de literal mal escrito que motivó la cirugía B1 está en la documentación que gobierna la construcción. Si el agente constructor copia el pre-registro literal, el VR corre contra un tenant inexistente. Lección: el error de literal no es un despiste puntual, es una clase de error sistémica → el lint anti-literal (DC-04) no es opcional.

2. **El servicio de validación de marca tiene TRES nombres y una referencia rota.** `verificacion.validar_borrador` (D00 §5.4, el real), `brand.validar_borrador` (D02:200, declarado por D02 como servicio propio), `brand.politicas` (D00:447 "futura", D01:260 "No obligatorio", D06:215 "**Sí** obligatorio"). D06 declara OBLIGATORIO un servicio que D02 jamás declara. Un constructor implementaría dos o tres endpoints para la misma cosa. Resuelto en R-03: un solo nombre.

3. **D04 se contradice a sí mismo en el punto más caro.** D04:148 ordena "fallo de remisión = bloqueo de nueva emisión del obligado hasta que se resuelva". D04:488 y D04:537 ordenan lo contrario: "reintento indefinido **sin bloqueo**". Si AEAT cae dos horas y gana la línea 148, el negocio del obligado se para. Resuelto en R-01: la emisión nunca se bloquea por fallo de remisión.

4. **La cadena de hash inmutable choca frontalmente con el derecho de supresión GDPR.** D00 hash-encadena la bitácora por tenant; los eventos de D01 llevan datos personales de leads (A.1: nombre, email, teléfono). Un lead ejerce supresión (art. 17 RGPD, y la propia LIA la promete) → no puedes borrar sus eventos sin romper la cadena que D00 declara verificable. Ningún dossier resuelve esto. Resuelto en R-07: PII por referencia o crypto-shredding; la cadena hashea ciphertext, el borrado destruye la clave.

5. **El fail-safe de capacidad de D05 está invertido.** D05:375: si el operador no declara capacidad, "default = 0 (cierra todo)" → el sistema **rechaza automáticamente** pedidos (acción IRREVERSIBLE-EXTERNA: le dice al cliente que no) por un olvido de UI. El fail-safe correcto para IRR-EXT es NO ACTUAR, no actuar-negando. Resuelto en R-08: sin declaración → pender en modo manual, jamás auto-rechazar.

6. **El sustrato promete un determinismo que los LLM no dan.** D00 PUERTA B6 exige "mismo borrador → mismo veredicto, N=20, temperatura 0" y D02 §13.2 exige "20/20 idénticos". En producción, temperatura 0 NO garantiza determinismo bit a bit (batching no determinista del proveedor, actualizaciones de modelo). Ese test fallará intermitentemente y el constructor perderá días persiguiendo un fantasma. Resuelto en R-02: la reproducibilidad es propiedad del sistema (caché por hash), no del modelo.

7. **El Anexo B de D08 — el calendario del cubo de CUMPLIMIENTO — contiene fechas legales erróneas.** "IR 01-07 año siguiente" (la campaña de Renta termina el 30-06); "Contabilidad (auditoría) 31-05" (no corresponde a ningún plazo estándar: legalización de libros 30-04, depósito de cuentas ~30-07, IS modelo 200 hasta 25-07); falta el Impuesto de Sociedades, pagos fraccionados y retenciones. Un cubo de cumplimiento sembrado con fechas mal es peor que no tenerlo: genera falsa seguridad. Resuelto: Anexo B = PLACEHOLDER, prohibido sembrarlo en producción sin validación de gestoría (GL-05).

Hallazgos adicionales de contrato: D04 declara que Comercial consume `finanzas.liquidacion.aprobada` (D04 §5.A) pero D01 solo declara consumir `finanzas.cobro.registrado` (D01:259) — el productor cree tener un consumidor que no existe. Y D06 §5.B espera `comercial.pedido.atribuido` "con marca de segmento", campo que el payload A.10 de D01 no tiene. Ambos resueltos (R-04, R-15).

---

## §2 — FE DE ERRATAS VERIFICADAS

Severidades: **BLOQUEANTE** (rompe construcción o ley) · **GRAVE** (fallará en producción) · **MEDIA** (contamina la construcción) · **MENOR** (higiene).

| # | Documento:línea | Error (texto actual) | Corrección | Severidad |
|---|---|---|---|---|
| E-01 | D05:356 | Tenant `alcayana` en pre-registro VR-D05-01 | `laboratorio` | **MEDIA** — VR contra tenant inexistente; misma clase que BG-257 |
| E-02 | D08:365 | Tenant `alcayana` en pre-registro VR-D08-01 | `laboratorio` | **MEDIA** |
| E-03 | D04:148 | Referencia a "§15.5" | §15 es tabla sin numeración; además la frase entera cae por R-01 | MENOR (contenido: **GRAVE**, ver R-01) |
| E-04 | D04:168 | "factura mensal" | "factura mensual" | MENOR |
| E-05 | D04:201, 228 | "Propriedades" (×2) | "Propiedades" | MENOR |
| E-06 | D04:486 | "retentar" | "reintentar" | MENOR |
| E-07 | D04:487 | "a mano si falta falta" | "a mano si hace falta" | MENOR |
| E-08 | D04:490 | "intentto" | "intento" | MENOR |
| E-09 | D04:569 | "corregir before any sale" | "corregir antes de cualquier venta" | MENOR |
| E-10 | D02:465 | "bidireccionalamente" | "bidireccionalmente" | MENOR |
| E-11 | D02–D08 cabeceras | "Fecha de emisión: 2026-07-08" en documentos emitidos el 09 | Unificar fecha real de emisión en v1.1 | MENOR |
| E-12 | D08 Anexo B | "IR (declaración anual) — 01-07 año siguiente" | Campaña de Renta finaliza **30-06** | **GRAVE** (fecha legal errónea en el cubo de cumplimiento) |
| E-13 | D08 Anexo B | "Contabilidad (auditoría) — 31-05" | No corresponde a plazo estándar (libros: 30-04; depósito cuentas: ~30-07; IS: 25-07). Fila a rehacer | **GRAVE** |
| E-14 | D08 Anexo B | Verifactu (RD 254/2025) y RRSIF (RD 1007/2023) como dos obligaciones separadas | Es un único régimen (el RD 254/2025 modifica plazos del RD 1007/2023); una fila | MEDIA |
| E-15 | D08 Anexo B | Ausencias: Impuesto de Sociedades (mod. 200, 1–25 julio), pagos fraccionados (mod. 202/130/131), retenciones (mod. 111/115), resúmenes anuales | Añadir en v1.1 tras validación de gestoría | **GRAVE** (por omisión) |
| E-16 | D05 §5.A/A.7 | Evento `capacidad.saturada` incluye `pedidos_rechazados[]` duplicando payloads de A.4 | Referenciar solo `pedido_id[]`; regla general: eventos referencian, no copian | MEDIA |
| E-17 | D07 §14 | Exige "≥3 alertas" Y "false positive rate ≤20%" | Con n=3, un solo falso = 33%: métrica no medible. Ver R-17 | MEDIA |
| E-18 | D03/D05/D08 §12 | "VR-DXX-01 semana 1" como puerta de bloque | Los pre-registros VR no definen hitos parciales por semana. Definirlos o eliminar la referencia | MEDIA |
| E-19 | D04:561 | Nombre propio del responsable en la spec técnica | Sustituir por rol ("administrador/responsable de emisión de la S.L.") | MENOR |
| E-20 | D06:131 | "Usa servicio `brand.validar_borrador` del cubo Brand (D02 §3.2)" | Ver R-03: el servicio es `verificacion.validar_borrador` del sustrato | MEDIA |

---

## §3 — RESOLUCIONES VINCULANTES

Cada resolución: el conflicto con evidencia, la regla que queda fijada, y los dossieres afectados. Desde la emisión de D09, estas reglas SON el contrato.

### R-01 — La emisión nunca se bloquea por fallo de remisión (D04)
**Conflicto:** D04:148 ("bloqueo de nueva emisión del obligado hasta que se resuelva") vs. D04:488 y D04:537 ("reintento indefinido sin bloqueo de factura").
**Resolución:** en modo VERI*FACTU la obligación es generar el registro conforme e intentar la remisión; la indisponibilidad de AEAT no suspende la facturación del negocio. La emisión de nuevas facturas **solo** se bloquea si la integridad de la bitácora local falla (no puede calcularse la huella encadenada) — eso sí es fallo propio. Fallo de remisión = alerta + reintento exponencial en background + contador visible en panel; nada más.
**Afecta:** D04 §3.5 (reescribir la frase de línea 148), §15.

### R-02 — Reproducibilidad de veredictos: propiedad del sistema, no del modelo (D00, D02)
**Conflicto con la realidad:** D00:529 (PUERTA B6, "N=20, temperatura 0") y D02:336 ("20/20 identical verdicts") prometen determinismo LLM que los proveedores no garantizan ni a temperatura 0.
**Resolución:** el veredicto se persiste en caché con clave `(hash_borrador, versión_directrices, versión_prompt, modelo_pin)`. Primera evaluación: LLM real. Evaluaciones siguientes: lectura de caché. El test 20/20 se ejecuta contra el sistema (1 miss + 19 hits = 20 idénticos, garantizado por construcción). Cambio de modelo o prompt = nueva versión de clave = re-evaluación consciente y documentada (evento `brand.directriz.actualizada` o equivalente de versión de prompt). El contrato de reproducibilidad cubre la **categoría** del veredicto; la redacción de las razones puede variar entre versiones.
**Afecta:** D00 §5.4 y PUERTA B6; D02 §3.2, §7.1, §13.2, §16.2.

### R-03 — Un solo nombre para el servicio de validación (D00, D01, D02, D06)
**Conflicto:** tres nombres para la misma capacidad; D06:215 declara obligatorio `brand.politicas`, que D02 §5.A no declara (D02 declara `brand.validar_borrador`, D02:200); D00:447 menciona `brand.politicas` como "futura".
**Resolución:** la única interfaz pública es la del sustrato: `verificacion.validar_borrador(tenant_id, tipo_contenido, contenido, paquetes_politicas=['brand'])` (D00 §5.4). El cubo Brand (D02) es el **proveedor del paquete `brand`** dentro de ese servicio: implementa directrices, versión y motor; no expone endpoint propio. Los nombres `brand.validar_borrador` y `brand.politicas` se eliminan del vocabulario de la serie. Los consumidores que necesiten invalidar caché se suscriben al evento `brand.directriz.actualizada`.
**Afecta:** D02 §5.A (retira su servicio; declara "proveedor del paquete brand"); D06 §5.B y línea 131; D01:260; D00:447.

### R-04 — Propiedad del estado del cliente y señal de CUSTOMER (D01, D03, D04)
**Conflicto:** dos máquinas de estados reclaman el estado del cliente (D01 pipeline hasta CUSTOMER; D03 §4.1 con PROSPECT→CUSTOMER→LOYAL/CHURNED). Además D04 §5.A declara que `finanzas.liquidacion.aprobada` es "consumida por Comercial para CUSTOMER", pero D01:259 solo declara consumir `finanzas.cobro.registrado`.
**Resolución:** (a) D01 es dueño del lead hasta la transición a CUSTOMER inclusive: la emite y archiva el lead (no re-transiciona después). (b) Desde ese evento, D03 es dueño del ciclo post-venta (CUSTOMER→LOYAL/CHURNED/INACTIVO). (c) El estado PROSPECT de D03 §4.1 **se elimina**: los prospectos son pipeline de D01; la máquina de D03 nace en CUSTOMER al consumir la transición. (d) La señal que dispara CUSTOMER es `finanzas.cobro.registrado` o confirmación manual del operador (como ya dice D01 paso 19); D04 §5.A corrige el consumidor declarado de `liquidacion.aprobada` (su consumidor real es el panel/registro del propio D04 y la vista del cliente).
**Afecta:** D03 §4.1 y §5.B; D04 §5.A.

### R-05 — P8 en dos niveles: fuente identificada, agregado disociado (todos, D07)
**Conflicto:** D03:269 emite P8 con `cliente_id`; D07 §7.1 y test §13.8 exigen P8 sin identificadores. Además, ningún Anexo A declara los asientos P8 como eventos versionados → D07 no es construible sin inventar esquemas (violaría DC-05).
**Resolución:** dos niveles. **P8-fuente**: evento `<cubo>.p8.asiento` v1, propiedad del cubo emisor, puede llevar `cliente_id` (es DATO_CLIENTE; sigue las reglas de PII de R-07), esquema a declarar en el Anexo A de cada dossier en v1.1. **P8-agregado**: lo produce el Agregador de D7.0; disociación = eliminación de identificadores + generalización a cohorte/segmento; es DATO_AGREGADO. Los tests de disociación de D07 auditan el agregado, no la fuente.
**Afecta:** Anexos A de D01, D03, D04, D05, D06 (añadir `p8.asiento`); D07 §3.1, §7.1, §13.8.

### R-06 — Lista de exclusión: de regla de D01 a invariante de sustrato I6 (D00, D03, D06)
**Conflicto:** D00:388 define la lista de exclusión por plataforma "consultada como gate determinista pre-envío/pre-llamada" y D01 la implementa (D01:307); pero D03 (propuestas de repetición, encuestas, resúmenes) y D06 (campañas, respuestas a reseñas) **también envían comunicaciones** y ninguno de los dos declara el gate en su §7.
**Resolución:** nueva invariante de sustrato **I6**: toda comunicación saliente de CUALQUIER cubo pasa por el gate de lista de exclusión antes de salir, sin excepción por cubo. Matiz necesario: el gate distingue clase **COMERCIAL** (bloqueada por exclusión: propuestas de repetición, campañas, prospección) de clase **TRANSACCIONAL** (no bloqueada: factura emitida, estado de un pedido en curso, resolución de una incidencia abierta) — negar a un cliente su factura porque hizo opt-out comercial sería el error inverso. D03 y D06 añaden la fila + test en sus §7 (`test_lista_exclusion_gate` heredado de D01).
**Afecta:** D00 §3 (I6 nueva); D03 §7; D06 §7.

### R-07 — PII, bitácora inmutable y derecho de supresión (D00, todos)
**Conflicto con la ley:** la bitácora hash-encadenada de D00 es inmutable y verificable; los payloads de D01 A.1 llevan nombre, email y teléfono de leads; el art. 17 RGPD (y la propia LIA) obligan a suprimir a petición. Borrar eventos rompe la cadena; no borrar incumple.
**Resolución:** (a) Regla de payload: los eventos NO llevan PII inline; llevan referencias (`*_ref`) a un almacén de sujetos borrable — el patrón ya existe en la serie (`borrador_ref`, `transcript_ref`, `dossier_ref`) y se eleva a norma. (b) Donde la PII inline sea inevitable (p. ej. `lead.descubierto`), el fragmento PII del payload se cifra con clave por-sujeto; la cadena hashea el ciphertext; la supresión GDPR = destrucción de la clave (**crypto-shredding**): la cadena queda íntegra y el dato queda ilegible para siempre. (c) Excepción legal explícita: los RFA y la bitácora SIF de D04 **no se suprimen nunca** (deber de conservación fiscal, art. 17.3.b RGPD: el deber legal prevalece); la frase de D00:156 "conservación exclusiva de lo exigido por ley" incluye formalmente la bitácora SIF completa y los registros de facturación, también tras la baja del tenant. (d) El validador de payloads del CI (R-16) incluye detección de PII inline no cifrada.
**Afecta:** D00 §3.4, §9.3, B2/B3; D01 Anexo A; D04 §8.1; todos los Anexos A.

### R-08 — Fail-safe de capacidad: pender, no rechazar (D05)
**Conflicto con el principio propio:** D05:375 fija "default = 0 (cierra todo)" si el operador no declara capacidad → rechazos automáticos, que son IRR-EXT (comunican un "no" al cliente), por un olvido de interfaz. Contradice el principio de fail-safe de toda la serie (ante duda, la acción externa NO sale).
**Resolución:** sin declaración de capacidad del día, los pedidos entrantes quedan en `PENDIENTE_CONFIRMACION` (modo manual degradado) + alerta persistente al operador ("capacidad no declarada; N pedidos esperando"). Lo único que se cierra automáticamente es la **confirmación automática**. El rechazo con propuesta de reschedule requiere o capacidad declarada y saturada de verdad, o decisión del operador.
**Afecta:** D05 §15 (fila "Operador no declara capacidad"), §6.

### R-09 — Reserva atómica de capacidad (D05)
**Gap:** dos pedidos concurrentes consultan "1 disponible", ambos confirman → sobreventa. D05 §13 solo prueba saturación secuencial; el patrón de claim atómico ya existe en D00 §4.3 (aprobaciones, batería 13.6) y no se replicó.
**Resolución:** la confirmación de pedido es un claim transaccional sobre la capacidad de la fecha (mismo patrón que aprobaciones). Nuevo test D05 §13.9: dos confirmaciones concurrentes sobre la última unidad → exactamente una gana; la otra recibe RESCHEDULE.
**Afecta:** D05 §3.2, §13.

### R-10 — Presupuesto de campañas: tres capas, no un gate (D06)
**Conflicto con la realidad:** D06 §13.4 promete "gasto rechazado" al superar presupuesto, pero el gasto lo ejecuta la plataforma externa (Google/LinkedIn) de forma asíncrona; el evento de gasto llega tarde. Un gate local determinista no puede garantizar el techo.
**Resolución:** control en tres capas: (1) **hard cap configurado en la plataforma** del canal (es la única garantía real); (2) reconciliación diaria del gasto reportado contra el mandato; (3) kill-switch automático de campaña al alcanzar el 90% del mandato según gasto reportado. El test §13.4 se redefine para verificar las tres capas, no un rechazo síncrono imposible.
**Afecta:** D06 §6, §7.2, §13.4.

### R-11 — Serialización de cadenas de hash (D00, D04)
**Gap:** hash encadenado + escrituras concurrentes = carrera o cadena rota. Ningún dossier fija el mecanismo.
**Resolución:** un solo escritor lógico por cadena: serialización por `tenant` en la bitácora de D00 y por `NIF-obligado` en la bitácora SIF de D04 (lock o cola de escritura de un solo consumidor). El orden de la cadena es el orden de escritura serializada; el ULID identifica, **no** ordena la cadena. Test heredable: N escrituras concurrentes → cadena íntegra y verificable.
**Afecta:** D00 §3.4; D04 §3.4.

### R-12 — Idempotencia declarada por consumo (D02, D03, D05, D06, D07, D08)
**Gap verificado:** el bus es al-menos-una-vez (D00), pero solo D01 y D04 declaran claves de idempotencia; los otros seis dossieres: cero menciones.
**Resolución:** tabla obligatoria en §5.B de cada v1.1. Claves por defecto que quedan fijadas ya: D02 → `(hash_borrador, versión_directrices)`; D03 → `pedido_id` (alta de ficha), `event_id` (resto); D05 → `pedido_id` (recepción/confirmación); D06 → `event_id`; D07 → `event_id` del asiento fuente; D08 → `obligacion_id`, `evidencia_id`.
**Afecta:** §5.B de los seis dossieres.

### R-13 — Qué pasa cuando una aprobación caduca (D00, consumidores)
**Gap:** D00 fija caducidad 72h con claim atómico (D00:521) pero no la política post-caducidad; D03/D05 esperan aprobaciones y no saben qué hacer con las caducadas.
**Resolución:** acción REVERSIBLE caducada → se reencola **una vez** con aviso; caducada por segunda vez → abortada con notificación. Acción IRR-EXT caducada → **abortada siempre** con notificación (nunca auto-reenvío: un borrador aprobado hace cinco días puede estar desactualizado respecto a la conversación real).
**Afecta:** D00 §4.3; consumidores.

### R-14 — Timestamps y zona horaria (todos)
**Gap verificado:** política de TZ ausente en los nueve documentos (una sola mención incidental de UTC en D00). España cambia de hora dos veces al año; las ventanas horarias LSSI de D01, las preferencias de D03 y la capacidad diaria de D05 dependen de hora local.
**Resolución:** persistencia y eventos siempre en **UTC ISO-8601 con offset explícito**; reglas de horario comercial y presentación en **Europe/Madrid**; test obligatorio de cambio horario (último domingo de marzo y de octubre) en todo cubo con ventanas horarias. El sello temporal legal de la remisión AEAT (D04) usa el que devuelve AEAT, no el local.
**Afecta:** D00 sobre canónico; D01, D03, D05, D08.

### R-15 — Atribución de campañas sin tocar `pedido.atribuido` (D01, D06)
**Conflicto:** D06 §5.B espera `comercial.pedido.atribuido` "con marca de segmento"; el payload A.10 de D01 no tiene ese campo.
**Resolución:** la atribución de marketing viaja por el lead, no por el pedido: `lead.descubierto.fuentes[]` (D01 A.1, ya existente) admite entradas `{tipo: CAMPANA, ref: campana_id}`; D06 sigue la cadena `campana_id → lead_id → pedido.atribuido` para el ROI. No se añade campo a A.10.
**Afecta:** D06 §5.B, §13.5; D01 A.1 (documentar el tipo CAMPANA en fuentes).

### R-16 — Anexos A → JSON Schema con CI (todos)
**Gap:** los Anexos A mezclan pseudo-código con anotaciones en prosa (comas colgantes, campos con comentario inline). Un constructor los interpretará con variación.
**Resolución:** antes de emitir el primer evento de un cubo, su Anexo A se transcribe a JSON Schema en el repo; el CI valida cada evento emitido contra su esquema (extiende el gate RUE de D00 B3). Regla de compatibilidad: los consumidores toleran campos desconocidos (forward-compat) y jamás rompen por campos extra; los productores jamás retiran campos sin bump de versión (ya en D00 §3.5).
**Afecta:** todos; primero D01 y D00 (B3).

### R-17 — Métrica de falsos positivos con n pequeño (D07)
**Errata E-17:** FP≤20% con ≥3 alertas no es medible.
**Resolución:** en VR-D07-01, el umbral bloqueante es **cero falsos de severidad CRITICA**; la tasa FP global pasa a métrica informativa hasta acumular n≥15 alertas, momento en que el 20% se activa como umbral.
**Afecta:** D07 §14, §16.

### R-18 — Transparencia IA por canal (D01, D03, D06) — ver también GL-01
**Estado verificado:** D01 cubre la voz IA con gates duros (disclosure primer turno + Robinson + prefijo + cuota + horario, D01:91/182/285) — correcto. Pero D03 en nivel MEDIA permite envío con "template pre-firmado" sin humano por-mensaje, y la regla de oro de D03 §2.2 ("jamás sin aprobar el operador primero") es ambigua sobre si la aprobación de plantilla cuenta como aprobación del mensaje.
**Resolución:** aprobación **por-plantilla** habilita envío automático solo si (a) la plantilla no admite generación libre de texto por mensaje (variables cerradas: nombre, producto, fecha) y (b) el pie identifica el carácter automatizado del envío cuando no hay humano en el bucle por-mensaje. Si el mensaje contiene texto generado por IA ad-hoc, la aprobación es por-mensaje. Esto deja el nivel MEDIA de D03 utilizable sin traicionar su regla de oro ni el art. 50 del AI Act.
**Afecta:** D03 §2.2, §6; D06 §6 (respuestas a reseñas con template pre-aprobado: misma regla).

### R-19 — Credenciales bancarias: prohibido custodiar (D04)
**Conflicto con la ley:** D04 §10.1 punto 3 dice "Integración bancaria: credenciales de acceso". La agregación de cuentas de terceros es actividad reservada a entidades AISP bajo PSD2; custodiar credenciales de banca online del cliente es riesgo legal y de seguridad inaceptable.
**Resolución:** vías permitidas únicamente: (a) import manual CSV/QIF por el cliente u operador (default de FA2, que ya lo contempla), o (b) agregador licenciado (GoCardless/Tink u otro AISP) vía OAuth donde el consentimiento y las credenciales viven en el agregador. Kaizen jamás almacena usuario/contraseña de banca.
**Afecta:** D04 §10.1, FA2.

### R-20 — Presencia digital: solo APIs oficiales autorizadas (D06)
**Riesgo:** D06 §3.4 dice "crawler o API". El scraping de Google Maps/Yelp viola sus ToS, se rompe con cada cambio de frontend y expone al tenant.
**Resolución:** solo APIs oficiales con autorización del tenant (Google Business Profile API y equivalentes). Donde no haya API, la auditoría de ese canal es manual-asistida (checklist para el operador), no crawler.
**Afecta:** D06 §3.4, D6.1.

---

## §4 — GAPS DE CONTRATO QUE BLOQUEAN CONSTRUCCIÓN

Lo que falta para que un agente construya sin inventar. Cada gap tiene su propuesta por defecto, adoptada salvo veto del operador.

| # | Gap | Bloquea | Propuesta por defecto (adoptada) |
|---|---|---|---|
| GAP-01 | Esquemas de eventos P8 inexistentes en Anexos A | D7.0 completo | R-05: `<cubo>.p8.asiento` v1 en cada v1.1; hasta entonces, D7 no arranca |
| GAP-02 | SLA de `PENDIENTE_CONFIRMACION` en D05 sin definir (¿cuánto espera un pedido la capacidad?) | D5.0 | 24h → alerta al operador; 72h → evento a D01 para que Comercial gestione expectativa con el lead |
| GAP-03 | No existe grafo integrado de dependencias entre bloques de los 9 documentos | Planificación del constructor | §8 de este documento ES ese grafo |
| GAP-04 | Convención de nombres de bloques inconsistente (D01: C0–C7; D04: FA0–FA4/FB0–FB4; resto: D2.x/D3.x/…) | Tooling de tracking | Se mantienen los nombres v1.0 con tabla de equivalencia (§8); norma futura para nuevos dossieres: `DXX.n` |
| GAP-05 | Política de retención/crecimiento de la bitácora de eventos sin definir (crece para siempre) | B3/B7 | Bitácora viva por tenant + archivado por periodo con snapshot de huella de cierre (la cadena continúa del snapshot); umbral de archivado lo fija la primera medición trimestral (mismo mecanismo que D00 §9 usa para el umbral de migración de almacén) |
| GAP-06 | Techo de coste (`LIMITE_COSTE_DIARIO_EUR`) no dice explícitamente si cubre llamadas internas cubo→sustrato (validaciones de D02 disparadas por D01) | B4, D2.1 | Sí las cubre: todo gasto LLM se imputa al tenant que origina la cadena de trabajo, incluidas validaciones; un bucle de reintentos Comercial↔Brand debe chocar con el techo, no esquivarlo |

---

## §5 — GUARDARRAÍLES DE PRODUCCIÓN (GR)

Mecanismos de fallo del mundo real que los dossieres subestiman. El constructor los trata como requisitos.

**GR-01 · Los LLM no son deterministas ni estables.** Temperatura 0 no garantiza identidad de salida; los proveedores actualizan modelos. Todo veredicto se cachea (R-02), toda versión de prompt se pina, todo cambio de modelo es un evento versionado. Ningún test de la suite depende de igualdad textual de salida LLM.

**GR-02 · Todo lo externo falla y se repite.** AEAT cae (R-01), el email rebota, la API de ads responde tarde, el webhook llega dos veces. Por eso: idempotencia declarada en cada consumo (R-12), reintento exponencial con jitter en cada salida, y outbox transaccional para todo evento marcado "outbox: sí" en los §5.A (el evento se persiste en la misma transacción que el cambio de estado; un relay lo publica).

**GR-03 · La concurrencia existe aunque hoy haya un solo operador.** Claim atómico para aprobaciones (D00, ya está), para capacidad (R-09) y para emisión de facturas (D04 §13.2, ya está). Escritor único serializado por cadena de hash (R-11). Los tests de carrera no son opcionales: son la diferencia entre "funciona en demo" y "funciona".

**GR-04 · El fail-safe de una acción IRR-EXT es NO ACTUAR.** Nunca "actuar negando" (R-08), nunca "reenviar lo caducado" (R-13), nunca "publicar sin validar porque el validador está caído" (los §5.B ya definen degradados: en ausencia de servicio, los borradores QUEDAN en preparado — eso se respeta a rajatabla).

**GR-05 · El tiempo es hostil.** UTC en persistencia, Europe/Madrid en reglas locales, tests de cambio horario (R-14). Además: nunca confiar en el reloj local para la cadena SIF (D04 §13.3 ya lo prueba; el sello de AEAT manda).

**GR-06 · La bitácora es para siempre: lo que entra no sale.** Ni PII sin cifrar (R-07), ni secretos, ni tokens, ni URLs firmadas. El validador de payloads en CI (R-16) rechaza el evento antes de que la cadena lo haga permanente. Un secreto filtrado a una bitácora hash-encadenada es una infiltración irreversible.

**GR-07 · Coste con techo o coste runaway.** El `LIMITE_COSTE_DIARIO_EUR` (D00 B4) cubre también el gasto interno (GAP-06). Todo bucle agente-LLM tiene contador de iteraciones con techo duro además del techo de euros. La escalera de degradación de D00 §6.3 se implementa antes del primer tenant de pago.

**GR-08 · Sandbox total en desarrollo.** Toda salida IRR-EXT en dev/test apunta a entorno de pruebas: email a sink local (Mailpit/Mailtrap), AEAT al entorno de pruebas del protocolo de la Orden, teléfonos a números propios, ads en modo draft. Un test que envía un email real a un lead real es un **incidente**, no un test. Variable de entorno única `KAIZEN_ENV` con default `dev`; el modo `prod` exige configuración explícita y visible.

**GR-09 · Los datos reales no viajan a fixtures.** Los 463 leads HORECA reales y los datos de Laboratorio no aparecen en tests, fixtures ni seeds. Los tests generan sintéticos (nombres, NIFs de prueba válidos por dígito de control, emails @example). Ver también DC-07.

**GR-10 · Backups verificados o no hay backups.** SQLite/JSON por tenant (D00 §9) implica: copia diaria automatizada + **test de restauración periódico** (una restauración jamás ensayada no es un backup, es una esperanza). El commit pendiente de 35+ días es la versión código de este mismo fallo: sin push, no hay respaldo. B0 físico es lo primero (§8).

**GR-11 · Migraciones de esquema con disciplina.** El almacén local-first evolucionará. Toda migración: script versionado + backup pre-migración + verificación post (conteos, checksums de cadenas). Nunca migración manual "rápida" sobre datos de tenant.

**GR-12 · Observabilidad mínima viable desde el día uno.** Cada cubo expone: contador de eventos emitidos/consumidos, edad del evento más antiguo sin procesar, últimos N errores. Sin esto, el primer fallo silencioso en producción (la especialidad de la Categoría B que OpenGravity midió en 29,5%) será invisible.

---

## §6 — GUARDARRAÍLES REGULATORIOS CON RELOJ (GL)

| # | Regla | Reloj | Estado en la serie | Acción |
|---|---|---|---|---|
| GL-01 | **AI Act art. 50** (transparencia de sistemas que interactúan con personas y de contenido sintético) | **2026-08-02 — a 24 días de la emisión de este documento** | Voz IA: cubierta por D01 (disclosure primer turno). Envíos automatizados sin humano por-mensaje: resuelto en R-18 | Toda plantilla de C1/D3.1/D6.0 que pueda operar sin humano por-mensaje incorpora la identificación desde su diseño. Los VR de D01 (30 días) que arranquen ya, cruzan la fecha: cumplir desde el primer envío |
| GL-02 | **Prefijo/numeración de llamadas comerciales** (obligación CNMC) | Vigente 2026 | Gate en D01 (numeración/prefijo + Robinson) ✓ | Mantener; verificar numeración contratada antes de activar Voz |
| GL-03 | **Verifactu/RRSIF** — obligados IS | **2027-01-01** (Sociedades; IRPF 2027-07-01) | D04 Pista B especificada; motor: cero líneas (D04 §11.2) | Ver reloj inverso §8: FB0 debe arrancar antes de ~octubre 2026 o el margen desaparece |
| GL-04 | **Conservación fiscal** (facturas y registros: mínimo 4 años LGT / 6 años Cco) | Permanente | Resuelto en R-07(c): la bitácora SIF sobrevive a la baja del tenant | El flujo de baja de D00 §9.3 lo implementa como excepción explícita con acta |
| GL-05 | **Calendario de obligaciones D08** | Permanente | Anexo B con errores verificados (E-12/13/14/15) | **PLACEHOLDER**: prohibido sembrarlo en producción sin validación línea a línea por la gestoría. El cubo D08 arranca con calendario validado o no arranca |
| GL-06 | **LSSI/RGPD prospección** | Permanente | D01 fuerte (bloques obligatorios, opt-out absorbente, 1+1, horario) ✓ | Extendido a D03/D06 vía I6 (R-06) |
| GL-07 | **PSD2 — agregación bancaria** | Permanente | D04 §10.1 lo violaba | Resuelto en R-19: CSV manual o AISP licenciado |
| GL-08 | **Supresión GDPR vs. inmutabilidad** | Permanente | Sin resolver en v1.0 | Resuelto en R-07: referencias + crypto-shredding; excepción fiscal explícita |

---

## §7 — DISCIPLINA DEL AGENTE CONSTRUCTOR (DC)

Contrato de conducta. Se asume Claude Code o equivalente con ejecución real; si el agente es de solo-generación (tipo Antigravity: lee código local y genera archivos, no ejecuta contra servidores), las reglas que exigen "ejecutar y pegar salida" las cumple el operador y el agente lo declara explícitamente en el acta — nunca simula haberlas ejecutado.

**DC-01 · Orden de lectura obligatorio.** D00 completo + D09 completo antes del primer bloque. El dossier del cubo, completo, antes de tocar su código. No se construye desde el resumen.

**DC-02 · Ambigüedad = parada, no interpretación.** Si el dossier no especifica algo necesario, el agente emite un bloque `DECISIÓN REQUERIDA` con: la ambigüedad, 2–3 opciones con consecuencias, y su recomendación. Prohibido resolver en silencio. Las contradicciones de §3 existen porque los documentos los escribió alguien que también se equivoca; las próximas las detectará quien construya, y su deber es señalarlas, no esquivarlas.

**DC-03 · Test rojo primero; puerta con evidencia pegada.** Ningún bloque cierra sin su batería ejecutada en verde y la **salida real de los tests pegada en el acta** (no descrita, no resumida: pegada). Heredado de B1 y del axioma de KAIZEN_CORRECCIONES_AGENTE_v1_0: *hecho = observado funcionando, nunca un resumen*.

**DC-04 · Prohibido el literal.** Ni tenant, ni NIF, ni fecha legal, ni ruta absoluta de máquina, hardcodeados. Gate CI anti-literales (D00 I1–I5) + lint. Las erratas E-01/E-02 de este mismo documento prueban que el error es sistémico incluso en documentación: en código es fatal.

**DC-05 · Prohibido inventar contrato.** Si un campo, evento o servicio no está en el Anexo A / RUE / §5 correspondiente, no existe. Añadirlo requiere DECISIÓN REQUERIDA y bump documentado. "Un campo extra que seguro ayuda" es deuda de contrato.

**DC-06 · Commit por bloque, push diario.** El mes huérfano (35 días sin commit) no se repite. Cada bloque = commit con mensaje `[DXX-Bn] descripción` + acta. Trabajo de más de un día = push diario aunque el bloque no cierre (rama de trabajo).

**DC-07 · Datos reales fuera del código.** Fixtures y seeds sintéticos siempre (GR-09). Los datos reales viven en los almacenes de tenant, jamás en el repo.

**DC-08 · Secretos: .env + gestor, escaneo en CI** (D00 B7, adelantado: el escaneo del árbol se activa desde B1, no se espera a B7).

**DC-09 · Sandbox por defecto** (GR-08). El agente verifica `KAIZEN_ENV != prod` antes de cualquier prueba con salidas.

**DC-10 · Los VR se ejecutan literales.** Pre-registro cumplido tal cual está escrito (tenant correcto — E-01/E-02 corregidas —, N mínimos, umbrales binarios). Un VR "casi cumplido" es un VR fallido; se documenta y se reintenta, no se redondea.

**DC-11 · Un bloque a la vez.** No se abre D2.1 con D2.0 sin puerta cruzada. La tentación de paralelizar dentro de un mismo cubo produce medias-construcciones; el paralelo legítimo es entre cubos independientes (§8).

**DC-12 · Nada de infraestructura especulativa.** Redis/Neo4j/LangGraph permanecen en quarantine EXPERIMENTAL (D00) hasta que la medición trimestral diga lo contrario. El agente no "aprovecha para modernizar".

**DC-13 · Toda desviación del dossier durante la construcción se registra** en el acta del bloque como DIVERGENCIA con motivo, y alimenta la v1.1 del dossier. El código nunca diverge en silencio del papel: o el papel estaba mal (se corrige el papel) o el código está mal (se corrige el código).

---

## §8 — GRAFO DE DEPENDENCIAS INTEGRADO Y RELOJ INVERSO

### §8.1 Equivalencia de nomenclatura de bloques (GAP-04)

| Dossier | Bloques v1.0 | Lectura |
|---|---|---|
| D00 | B0–B7 | Sustrato |
| D01 | C0–C7 | Comercial |
| D02 | D2.0–D2.2 | Brand |
| D03 | D3.0–D3.2 | Atención |
| D04 | FA0–FA4 / FB0–FB4 | Finanzas pista A / pista B |
| D05 | D5.0–D5.2 | Operaciones |
| D06 | D6.0–D6.2 | Marketing |
| D07 | D7.0–D7.2 | Inteligencia |
| D08 | D8.0–D8.2 | Cumplimiento |

### §8.2 Grafo topológico (niveles = pueden arrancar cuando su nivel anterior tenga las puertas citadas)

```
N0  B0-físico (git add/commit/push del mes huérfano)          ← BLOQUEANTE ABSOLUTO, pendiente
N1  B1 (cirugías BG-257, CLI-1365, python-multipart; tests rojos primero)
N2  B2 (tenancy+I1..I6)   B3 (RUE+bitácora+outbox+schemas R-16)   D8.0† (sin dependencia de cubos)
N3  B4 (coste+techos)     B5 (aprobaciones+claim+R-13)
N4  B6 (verificación como servicio, con caché R-02)           C0 (corpus, cero código) → C1
N5  D2.0→D2.1 (requiere B6)     C2→C3→C4 (requieren B3/B5)     FA0 (requiere C-pedido.atribuido)
N6  FA1 (bus+coste)       D5.0 (requiere B1+C)       D3.0 (requiere C)
N7  C5→C6                 FA2→FA3                    D5.1        D3.1        D6.0 (requiere D2.1 + R-15)
N8  FB0 (gates: FA1 ✓ + "Laboratorio emite facturas manualmente" + GL-03 reloj)   D6.1   D8.1
N9  FB1→FB2→FB3 (motor SIF)         D7.0 (requiere p8.asiento en producción de C y D5.x — GAP-01/R-05)
N10 FB4      D7.1→D7.2      D6.2 (↔D7)      D3.2      D5.2      D8.2
B7 (seguridad/pánico/restauración): transversal — DEBE estar cruzado antes del primer VR con salidas reales en producción.
C7 (Voz): condicional, no bloquea nada; gates GL-01/GL-02 duros.

† D8.0 es el único bloque de cubo sin dependencia de otros cubos: puede correr en paralelo desde N2
  y tiene reloj legal propio (GL-05: arranca con calendario validado por gestoría).
```

**Camino crítico de caja:** N0 → B1 → (B3,B5) → C0–C4 → VR-D01-01 (30 días) → FA0–FA1 (primera liquidación cobrable).

**Ciclos declarados y rotos:** D06↔D07 (segmentos): D6.2 y D7 se declararon mutuamente opcionales en sus dossieres — se construyen cuando ambos lados existen, ninguno bloquea v1.0 del otro. P8: los cubos emiten `p8.asiento` desde sus bloques tempranos aunque D07 no exista aún (el evento se acumula en la bitácora; degradación elegante en la dirección correcta).

### §8.3 Reloj inverso (fechas duras desde hoy, 2026-07-09)

| Fecha | Qué vence | Cuenta atrás | Implicación de construcción |
|---|---|---|---|
| **2026-08-02** | AI Act art. 50 | **24 días** | Plantillas de C1 con transparencia desde el diseño; cualquier VR de envíos que arranque ya, cruza la fecha cumpliendo |
| 2026-08 | Constitución S.L. | ~semanas | La S.L. será el primer obligado de Pista B (dogfooding D04) |
| ~2026-10 | Último arranque razonable de FB0 | ~90 días | FB0 (estudio+esquemas) + contratación de certificación externa (el tercero tarda semanas) + FB1–FB3 + auditoría + declaración responsable deben caber antes de GL-03. Más tarde de octubre = sin margen |
| **2027-01-01** | Verifactu obligados IS | 175 días | La primera factura de la S.L. bajo el régimen; el motor debe estar firmado (D04 §16.2) antes |
| 2027-07-01 | Verifactu obligados IRPF | 357 días | Segunda ola de mercado VeriGest |

---

## §9 — CHECKLIST PRE-CÓDIGO (BINARIA)

El agente responde a las diez antes de escribir la primera línea de un bloque. Un NO = no se escribe código; se resuelve el NO.

1. ¿He leído D00, D09 y el dossier del cubo COMPLETOS (no el resumen)?
2. ¿El bloque que voy a construir tiene todas sus dependencias del grafo §8.2 con puerta cruzada y acta?
3. ¿Existe el commit físico de N0 (repo respaldado en remoto)?
4. ¿Los eventos que este bloque emite/consume tienen esquema en el RUE/JSON Schema (R-16), incluida su clave de idempotencia (R-12)?
5. ¿Tengo claro el fail-safe de cada acción IRR-EXT de este bloque (GR-04) y su comportamiento post-caducidad (R-13)?
6. ¿Los tests que voy a escribir primero (en rojo) cubren la batería §13 del dossier MÁS los de carrera/concurrencia aplicables (GR-03)?
7. ¿`KAIZEN_ENV=dev` y todas las salidas externas apuntan a sandbox (GR-08)?
8. ¿Cero literales de tenant/NIF/fechas legales en lo que voy a escribir, y el lint anti-literal está activo (DC-04)?
9. ¿Cero PII/secretos en payloads de eventos que voy a emitir (GR-06, R-07)?
10. ¿Hay alguna ambigüedad no resuelta entre el dossier y D09 para este bloque? (Si sí → DECISIÓN REQUERIDA antes de codificar, DC-02.)

---

## §10 — MAPA DE CAMBIOS v1.1 POR DOCUMENTO

Al emitir cada v1.1, incorporar exactamente esto (además de las erratas menores de §2 que le apliquen):

| Documento | Cambios a incorporar |
|---|---|
| **D00** | I6 (lista de exclusión como invariante, R-06) · política PII/crypto-shredding en §3.4 y §9.3 con excepción fiscal (R-07) · caché de veredictos en §5.4 y PUERTA B6 (R-02) · serialización de escritor de cadena (R-11) · política post-caducidad en §4.3 (R-13) · TZ UTC/Madrid en sobre canónico (R-14) · retirar mención `brand.politicas` (R-03) · imputación de coste interno (GAP-06) · política de retención de bitácora (GAP-05) |
| **D01** | Documentar `fuentes[].tipo=CAMPANA` en A.1 (R-15) · añadir `comercial.p8.asiento` v1 a Anexo A (R-05) · nota de que su gate de exclusión pasa a ser I6 del sustrato |
| **D02** | Retirar `brand.validar_borrador` de §5.A; declararse proveedor del paquete `brand` del servicio del sustrato (R-03) · reproducibilidad por caché en §3.2/§7/§13.2/§16.2 (R-02) · idempotencia (R-12) · E-10 |
| **D03** | Eliminar PROSPECT de §4.1; máquina nace en CUSTOMER (R-04) · fila I6 + test en §7 (R-06) · precisión de aprobación por-plantilla vs por-mensaje en §2.2/§6 (R-18) · `cliente.p8.asiento` en Anexo A (R-05) · idempotencia (R-12) |
| **D04** | Reescribir D04:148 conforme R-01 · corregir consumidor de `liquidacion.aprobada` en §5.A (R-04) · §10.1 banca conforme R-19 · `finanzas.p8.asiento` (R-05) · E-03..E-09, E-19 |
| **D05** | Fail-safe de capacidad no declarada (R-08) en §6/§15 · claim atómico + test 13.9 (R-09) · SLA de PENDIENTE_CONFIRMACION (GAP-02) · E-01 · E-16 · `operacion.p8.asiento` (R-05) · idempotencia (R-12) |
| **D06** | §5.B: sustituir `brand.politicas` por servicio del sustrato + suscripción a `directriz.actualizada` (R-03, E-20) · atribución vía lead (R-15) en §5.B/§13.5 · presupuesto en tres capas (R-10) en §6/§7/§13.4 · fila I6 + test (R-06) · APIs oficiales, sin scraping (R-20) · `marketing.p8.asiento` (R-05) · idempotencia (R-12) |
| **D07** | Dos niveles de P8 en §3.1/§7.1/§13.8 (R-05) · métrica FP conforme R-17 en §14/§16 · idempotencia (R-12) |
| **D08** | E-02 · Anexo B completo = PLACEHOLDER hasta validación de gestoría; corregir E-12/E-13/E-14/E-15 con fuente primaria citada por fila (GL-05) · idempotencia (R-12) |

---

*Fin de KAIZEN-D09 v1.0. Emitido el 2026-07-09 tras auditoría verificada línea a línea de D00–D08. Veinte erratas, veinte resoluciones, seis gaps, doce guardarraíles de producción, ocho relojes regulatorios, trece reglas de disciplina, un grafo y una checklist. La serie D00–D08 define QUÉ construir; D09 define QUÉ ESTABA ROTO en esa definición y CÓMO construir sin que el constructor herede los errores del arquitecto. El hallazgo que gobierna todos los demás: la clase de error que motivó la cirugía B1 (el literal `laboratorio` mal escrito) reapareció dos veces en los propios dossieres — la disciplina no es desconfianza hacia el agente constructor; es la constatación de que ningún autor, humano o IA, se audita bien a sí mismo. Por eso este documento existe.*
