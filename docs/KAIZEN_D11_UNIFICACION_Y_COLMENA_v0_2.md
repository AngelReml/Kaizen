# KAIZEN D11 v0.2 — UNIFICACIÓN, CEREBRO, COLMENA Y PRODUCCIÓN (marco laboratorio)

**Fecha:** 2026-08-03 · **Sustituye a:** v0.1 PROPUESTA (queda como historial)
**Orden del operador:** rehacer el plan con criterio propio del agente, proponiendo
mejoras en cada punto y revisión justificada de normas donde frenen el potencial.

**Marco nuevo declarado por el operador (manda sobre todo el documento):**
la versión actual de KAIZEN está **congelada en copia física en otros discos** — un
savepoint inmutable, punto de retorno global. **La entrega a Alejandro se hará desde
ese savepoint.** La carpeta `C:\Users\angel\Desktop\KAIZEN` pasa a ser el
**laboratorio**: aquí se cambia y se prueba todo; todo es modificable.

Consecuencia de arquitectura de proceso: el rollback ya no se construye dentro de
cada cambio (doble-escrituras eternas, shims perpetuos, miedo al calendario) — **el
rollback ES el savepoint**. Eso libera el plan: se puede operar a corazón abierto.

---

## Índice

- §0. Lo que este documento es, y mi posición en una frase
- §1. Revisión de normas — mi veredicto, norma a norma, con justificación
- §2. Principios del laboratorio (los que quedan y los que entran)
- §3. Arquitectura objetivo: una columna, y ahora sin andamios eternos
- §4. El Cerebro Comercial — la IA donde el experimento dijo que valía
- §5. La Colmena v2 — de "solo mirar" a autonomía graduada real
- §6. Simplificación agresiva: lo que se extirpa
- §7. Robustez y producción (lo que se mantiene del v0.1, afinado)
- §8. Plan por etapas — esfuerzo y puertas, no fechas dogma
- §9. Riesgos del marco nuevo
- §10. ADRs propuestas (008–015) y decisiones de Iván

---

## §0. Lo que este documento es, y mi posición en una frase

Mi posición, sin diplomacia: **las reglas de KAIZEN no son el problema; su
aplicación estática sí podía llegar a serlo.** El fail-closed, la aprobación humana
y las cadenas de hash son la razón por la que este sistema puede venderse a un
negocio serio — eso no es corsé, es el producto. Lo que sí estaba contaminando el
potencial era otra cosa: tratar TODO freno como eterno e igual de sagrado, mezclar
ley con costumbre, y proteger una entrega que ahora ya protege un disco externo.
Este v0.2 separa esas tres cosas y propone dónde soltar lastre de verdad.

---

## §1. Revisión de normas — mi veredicto, norma a norma

Clasifico cada norma por su ORIGEN, porque no pesa igual una ley europea que una
costumbre de proceso. Cuatro categorías: **LEY** (intocable), **ALMA** (diseño que
ES el producto — se mantiene y evoluciona), **PROCESO** (se adapta al laboratorio),
**REVISABLE** (propongo cambiarla, con argumento; la firma es de Iván).

### 1.1 LEY — no se tocan, y además son ventaja comercial

| Norma | Veredicto |
|---|---|
| AI Act art. 50 (transparencia de IA en cada mensaje saliente) | INTOCABLE. No es nuestra regla: es el entorno. Y "cumplimiento como código" es argumento de venta que ningún integrador de n8n puede enseñar. |
| Lista Robinson (`robinson_ok is True` o no se llama) y `DO_NOT_CALL` terminal | INTOCABLE. Además: multa. |
| Orden TDF/149/2025 (numeración fija de origen) | INTOCABLE. La voz sigue DE BAJA hasta tener número conforme; dejo escrito el checklist de reactivación para ese día. |
| RGPD (PII, retención, derecho de supresión) | INTOCABLE. El crypto-shredding (R-13) pasa de "deuda" a etapa del plan (§8-E4). |

### 1.2 ALMA — se mantienen, pero paso de freno estático a freno adaptativo

| Norma | Veredicto y evolución propuesta |
|---|---|
| Fail-closed (GR-04): ante la duda, la acción externa NO sale | SE MANTIENE tal cual. Es la frase que define a KAIZEN. |
| Ninguna acción externa irreversible sin aprobación | SE MANTIENE COMO SUELO — y propongo la evolución que el propio sustrato ya trae construida y nadie usa: **autonomía GANADA** (§5.3). Los gates CERO→BAJA→MEDIA→ALTA existen, están testeados y llevan un mes parados en BAJA por costumbre, no por diseño. Un freno que nunca se gradúa no es prudencia: es un motor comprado y sin estrenar. La graduación será por historial verificable y revocable en automático — el humano sigue firmando la subida, el sistema se gana el derecho a pedirla. |
| La última defensa nunca es un LLM | SE MANTIENE. Nivel duro primero, siempre. |
| Hash bit a bit aprobado=enviado, TTL, claim CAS | SE MANTIENE. Es la mejor pieza del sistema. |
| Cadenas de hash + forense diario | SE MANTIENE y se amplía (watchdog de flags, backups, sync — v0.1 §5 sigue). |
| "Prometer precios no existe" | SE MANTIENE. Las acciones peligrosas inexistentes (no prohibidas) son un patrón superior. La Colmena lo hereda (§5.2). |

### 1.3 PROCESO — se adaptan al marco laboratorio

| Norma | Adaptación |
|---|---|
| R6 "la suite solo puede subir" | ADAPTADA: en la RAMA principal del laboratorio se mantiene (es oro: 916 tests son el mapa de lo que no se puede romper sin enterarse). En ramas de experimento, se puede romper; **el merge a principal solo en verde**. La línea base del laboratorio arranca en 916/1/7 y su primer objetivo es 917/0/7 (candado AIACT email resuelto). El savepoint conserva su propia base congelada. |
| R9 "nada está hecho hasta que Iván lo ejecuta" | ADAPTADA A DOS NIVELES: en laboratorio, mi verificación ejecutada en réplica (VM) basta para iterar — si cada paso espera a Iván, el cuello de botella soy... él, y me pidió lo contrario ("intenta no necesitarme"). R9 pleno se reserva para HITOS: cierre de etapa, promoción a producción, y todo lo que Alejandro vaya a tocar. |
| E1 (verificar cada escritura al montaje con sha256) | SE MANTIENE SIN CAMBIOS. No es burocracia: este montaje corrompió un `.git` y truncó ficheros. Cuesta un comando y ha salvado tres sesiones. |
| R8 "todo lo visible, para un panadero en 90 s" | SE MANTIENE PARA ALEJANDRO, y se declara la segunda audiencia: el operador tiene cockpit técnico (Colmena, panel). Dos interfaces, dos vocabularios. |
| MAPA_VIVO y actas | SE MANTIENE en principal; los experimentos de rama no lo ensucian. |
| "Unificación = decisión v1.1 de Iván" | CUMPLIDA: la orden "unifícalo todo" del 2026-08-03 ES esa decisión. El laboratorio la ejecuta. |

### 1.4 REVISABLES — propongo cambio, con el argumento delante

**R-REV-1 · DR-01 "git SOLO local, jamás remoto ni push" → separar CÓDIGO de DATOS
y dar remoto privado al código.**
El motivo real de DR-01 es sagrado: los datos de terceros no pueden salir (R1 y
RGPD). Pero el árbol actual mezcla código con `state/`, `data/`, `empresas/`,
`diario/` — y por eso TODO quedó condenado a local. La consecuencia práctica hoy:
**el único respaldo del trabajo de 3 meses es un disco físico en la misma casa.**
Un incendio, un robo o un ransomware se llevan proyecto y savepoint a la vez.
Propuesta: (a) mover los datos fuera del árbol de git (directorio hermano
`KAIZEN_DATOS/` cifrado, con su propio backup local + externo); (b) `.gitignore`
blindado + hook pre-commit que ESCANEA el staging en busca de PII/secretos y
bloquea (fail-closed, testeable); (c) remoto PRIVADO del código limpio (GitHub
privado o, más soberano, Gitea en el VPS Contabo que ya pagas). El código sin datos
no es "datos de terceros": es tu propiedad intelectual, y hoy está en un único
punto de fallo físico. **Riesgo actual > riesgo propuesto.** La firma es tuya.

**R-REV-2 · R2 "sin cifra explícita = 0 $" → presupuesto operativo mensual del
laboratorio, con el freno delante que ya existe.**
El 0-por-defecto fue correcto cuando el peligro era un agente gastando sin
contabilidad. Ese peligro ya no existe: hay ledger, techo, reserva atómica DELANTE
de cada llamada y escalera de degradación — construidos y testeados. Hoy el
0-por-defecto produce otra cosa: un sistema con el músculo atrofiado (el comité
real votó una vez en julio; la Colmena nacería muda; el cerebro comercial no puede
ni probarse). Propuesta: **cifra mensual fija para el laboratorio — 10 €/mes —**
gobernada por el ledger único, desglosada en el forense diario, y revisable cada
mes a la vista del gasto real (recuerda: tres meses de construcción han costado
0,02 $). Sin tu cifra, sigue siendo 0: la norma no la rompo, propongo sustituirla
por una mejor.

**R-REV-3 · "Demos con leads reales solo lectura + marcador [DEMO]" → añadir un
TENANT SINTÉTICO de pruebas.**
Mantengo la regla para leads reales, y propongo lo que falta: una empresa ficticia
(`empresas/laboratorio/` con 50 leads inventados, generados, marcados) donde el
pipeline COMPLETO —incluido envío real a buzones PROPIOS— pueda ejecutarse de
punta a punta sin tocar a un tercero jamás. Es la pieza que permite probar "bajo
carga real" sin riesgo real: hoy el último milímetro del sistema solo se ha
ensayado en seco. Un sistema cuyo camino completo nunca se ha recorrido no está
probado; está ensayado.

**R-REV-4 · Calendario dogma → puertas de calidad.**
El v0.1 vivía condicionado por el 30-ago. Con la entrega protegida por el
savepoint, las fechas del laboratorio pasan a ser estimaciones de esfuerzo con
puertas de calidad (suite, forense, réplica). Lo único con fecha real es lo legal
(AI Act ya en vigor) y lo que Iván quiera fijar.

**Qué NO propongo revisar, aunque el marco lo permitiría:** el envío real a
terceros sin orden expresa (R4). El sandbox cambia el código, no cambia que los
466 sean personas reales. Todo envío a tercero real sigue siendo: producción,
orden tuya, rampa, dominio autenticado. El tenant sintético (R-REV-3) existe
precisamente para no necesitar tocarlos.

---

## §2. Principios del laboratorio

1. **El savepoint es sagrado; el laboratorio es libre.** Aquí se opera a corazón
   abierto; el punto de retorno vive fuera y no se toca.
2. **Fail-closed para el mundo real; fail-fast para el laboratorio.** Hacia fuera,
   ante la duda no sale nada; hacia dentro, que los errores revienten pronto y
   ruidoso — es un laboratorio, no un escaparate.
3. **Merge solo en verde.** Ramas para romper; principal siempre ejecutable.
4. **Un solo camino al mundo real** (ejecutor único). Sin excepciones ni "atajos de
   prueba": para probar está el tenant sintético.
5. **La autonomía se gana con historial, se pierde con un fallo, y la firma la
   subida un humano.**
6. **Los insumos de cada decisión se persisten con la decisión** (lección I-1/2/3).
7. **Menos código: todo lo muerto se extirpa** (§6). La superficie de fallo también
   es deuda.
8. **Dos audiencias:** Alejandro = 90 segundos; operador = cockpit.

---

## §3. Arquitectura objetivo: una columna, sin andamios eternos

La arquitectura del v0.1 §3 sigue siendo la correcta — sustrato G3 como columna
única: un bus (hash-chain, publicar+transicionar en una transacción), una cola
(propuestas de la Mesa + hash/token/TTL/claim de la cola G1), un ledger (reserva
atómica delante + escalera de degradación), una máquina de estados (M2 canónica,
P9 proyección con el mapeo existente), un ejecutor (AIACT → comité → coste →
pánico → envío), RUE como catálogo de tipos y no como almacén, knowledge.json como
almacén de trabajo de Fase 0 sincronizado a diario.

**Lo que cambia con el marco nuevo — tres decisiones que antes no podía tomar:**

1. **Corte directo, no convivencia larga.** En v0.1, cada fusión llevaba semanas de
   doble-escritura y shims por miedo a la entrega. Ahora: migración directa con
   verificación (script de corte + suite + forense + comparación de contadores en
   réplica), y el savepoint como red. Los shims que se creen son **temporales con
   fecha de derribo escrita**, no arquitectura.
2. **La unificación va PRIMERO, la Colmena después.** En v0.1 la Colmena se
   adelantaba porque la unificación no cabía antes de la entrega. En el orden
   correcto de ingeniería, las personas del chat nacen ya sobre la columna única
   (una cola, un ledger) y no aprenden vicios de la era de los tres árboles.
3. **`data/kaizen.db` absorbe también los almacenes menores:** `eventos.json` (RUE)
   entra como tabla-catálogo versionada; `.kaizen_cost.json` se importa al ledger y
   se retira; `state/voz/quota/` queda congelado con la voz. Un proceso, un
   fichero de verdad, N vistas.

El diagrama del v0.1 §3 sigue válido con una corrección de rótulo: donde decía
"adaptadores (shims G1/G2)" ahora dice "adaptadores CON FECHA DE DERRIBO".

---

## §4. El Cerebro Comercial — la IA donde el experimento dijo que valía

El experimento del 2026-08-03 dejó un mapa medido: la misión es determinista y sin
IA; la IA rinde en los bordes. En v0.1 esto era "propuesta futura". En el
laboratorio es OBRA, con presupuesto del R-REV-2 y métricas por pieza:

| Pieza | Qué hace | Coste estimado | Métrica de éxito |
|---|---|---|---|
| **C1 · Decisor+email** | LLM barato lee la web del lead (la URL ya está en 465/466) y extrae persona de contacto + email directo + forma de tratamiento. Por lotes, solo top de cola. | ~0,002 €/lead (modelo cheap del router) | % de leads del top-60 con email directo verificado (hoy: dato no medido — primera medición fija la base) |
| **C2 · Rescate de ambiguos** | Tras persistir descartes (I-2): LLM a temperatura 0 revisa SOLO los descartados-sin-señal y propone re-cualificación → a revisión humana, no auto-alta. | lote único ~0,50 € | falsos negativos recuperados / 100 descartes |
| **C3 · Contexto comercial** | 2 líneas por lead (web+reseñas) que alimentan al redactor: personalización real en vez de plantilla con nombre. | ~0,003 €/lead, solo cola de contacto | tasa de respuesta por variante (medible vía P8 cuando haya envíos) |
| **C0 · Prerrequisito** | I-1/I-2/I-3: persistir place_types, descartes con razón, peso del match. Sin esto, C2 no tiene materia prima y nada es re-auditable. | 0 € (código) | re-derivabilidad del corpus: 20% → ~100% en leads nuevos |

Dónde NO va IA (ratificado por el experimento, lo defiendo aunque el marco sea
libre): priorizador (P8 aprende de resultados reales, no de opiniones) e ICP con
señal completa (las reglas son gratis, auditables y reproducibles — el LLM entra
solo donde la señal se acaba). La libertad nueva es para quitar fricción, no para
meter moda.

---

## §5. La Colmena v2 — de "solo mirar" a autonomía graduada real

La base del v0.1 §4 se mantiene: Buzz self-hosted (relay localhost → VPS), jamás el
hosting de Block (sin E2EE — R1/RGPD), allowlist estricta, personas con Persona
Packs (keypair + NIP-OA + personalidad + skills), `kaizen-mcp` como única frontera,
condición de parada N=3, presupuesto por turno reservado DELANTE en el ledger.

**Lo que sube de ambición — la corrección al v0.1 que el marco permite:**

### 5.1 Las personas usan los NIVELES del gate, no un "solo lectura" plano

El v0.1, contaminado de prudencia de entrega, dejaba a las personas en
lectura+proponer. Eso infrautiliza la matriz de gates que el sustrato YA tiene.
Propuesta: las personas operan con el MISMO sistema de autonomía que los cubos:

| Nivel | Qué puede hacer una persona en ese nivel | Ejemplos |
|---|---|---|
| CERO | leer y contar | estado, forense, pipeline, ranking P8 |
| BAJA | escribir INTERNO reversible | `proponer_tarjeta`, crear compromiso interno, anotar un lead, lanzar `registro sync`, regenerar el panel |
| MEDIA | orquestar trabajo interno | lanzar el ritual de la mañana (gasta según ledger), encolar lotes C1/C3 del cerebro, preparar informes |
| ALTA + comité | acciones externas irreversibles | NO DISPONIBLE para personas. Punto. El chat propone; la Mesa dispone. La "ALTA conversacional" no existe (patrón AcciónInexistente). |

Arranque: Director y Forense en BAJA; Comercial en BAJA con subida a MEDIA a la
primera semana limpia. Todo por el gate real del sustrato — la Colmena no lleva su
propio sistema de permisos: usa EL de KAIZEN.

### 5.2 Autonomía GANADA (la evolución del alma, §1.2)

Regla propuesta, cableada en `gates.py` + `decisiones_operador`:

- Cada tipo de acción acumula historial: propuesta → decisión humana.
- **N aprobaciones consecutivas sin corrección (N=20 por defecto) en un tipo de
  acción → el sistema PIDE la subida de nivel para ese tipo**, con su evidencia.
  El humano firma (un toque en la Mesa). La subida queda sellada.
- **Primer fallo o corrección → bajada AUTOMÁTICA al nivel anterior** (endurecer es
  programático; relajar es humano — la asimetría original, ahora con bucle de
  aprendizaje).
- Techo duro: las acciones externas irreversibles NUNCA superan "ALTA + comité +
  Mesa" — la graduación opera por debajo de ese techo, no lo mueve.

Esto convierte el freno estático en un freno que aprende, sin ceder la última
palabra. Es, en mi criterio, la mejora de mayor potencial de todo el dossier: es
la diferencia entre "un sistema vigilado" y "una empresa sintética que se gana la
confianza como se la ganaría un empleado".

### 5.3 Órdenes de verdad, memoria de verdad

- "Comercial, prepara 5 tarjetas de cafeterías del anillo 0 con el argumento que
  mejor rinda" → la persona consulta P8, encola C3 para esos 5, redacta vía el
  composer real (con Brand Guardian), crea 5 propuestas → Mesa. Una orden, un
  circuito entero, cero saltos de barrera.
- Memoria por persona (engrams cifrados de Buzz o tabla propia en el sustrato — a
  decidir en obra por simplicidad): lo que Iván corrige queda recordado; el estilo
  de cada persona se afina con uso.
- El P8 alimenta a las personas: el argumentario que aprende deja de ser una tabla
  que nadie mira y pasa a ser lo que el Comercial te cuenta por chat.

---

## §6. Simplificación agresiva: lo que se extirpa

Antes no cabía por el riesgo de entrega; ahora es obligatorio. Menos código, menos
superficie de fallo, menos contexto que cargar. Todo va a `_archivo/` (nada se
borra: se destierra), con la suite verde tras cada extirpación:

1. **La CLI de voz neutralizada** (R-02): de candada a EXTIRPADA. La voz está DE
   BAJA; su reactivación futura entrará por el ejecutor único o no entrará.
2. **`core/bus.py` backend Redis** (no consume el stream — auditado): fuera, con
   docker-compose.yml si ya no lo usa nadie.
3. **Uno de los dos paneles**: `panel_mando/` (D10, con auth de sesión, CSRF,
   PARAR TODO persistente) ABSORBE al panel viejo (`api/server.py` + `panel/`);
   los webhooks de voz que viven en api/server quedan congelados con la voz.
4. **Uno de los dos comités**: el 3×3 decide en el camino de ejecución; OpenGravity
   queda como QA forense a posteriori o se destierra si en 30 días nadie lee sus
   veredictos — que lo decida el uso, no la nostalgia.
5. **`demos/demo_tesis.py`, digests CONTEXTO_TOTAL de >200K tokens, docs
   pre-canónicos de mayo**: a `_archivo/`. La wiki queda con lo vigente.
6. **`departments/desarrollo` y `rrhh`** (cascarones pospuestos): fuera del árbol
   activo hasta que existan de verdad.

Estimación honesta del efecto: −15–25% de líneas activas, cero pérdida de función
viva, y una suite que por fin describe solo lo que existe.

---

## §7. Robustez y producción (se mantiene del v0.1, afinado)

El v0.1 §5–§6 sigue vigente íntegro — dimensionado honesto (SQLite con dos órdenes
de magnitud de margen; ADR-012), los cinco pilares (backups CON simulacro mensual,
forense-watchdog, systemd en el VPS Contabo ya pagado, rituales de doble clic,
runbooks de una página), degradación elegante, entregabilidad F4 (dig SPF/DKIM/
DMARC, rampa ≤10/día, dominio frío = PARAR), y el mecanismo AI Act para email
(fichero de variantes aprobado SOLO por el operador + check en composición + candado
en envío).

Afinados con el marco nuevo:

- **El savepoint entra en el plan de copias:** verificación trimestral de que el
  disco externo LEE y el bundle restaura (un savepoint que no se ha probado a
  restaurar es una esperanza, no un punto de retorno).
- **Promoción laboratorio → producción como ACTO:** cuando una versión del
  laboratorio esté lista para sustituir al savepoint como base de Alejandro, se
  hace con liturgia: suite en clon limpio + forense verde 7 días + R9 pleno de
  Iván + NUEVO savepoint físico. La entrega del 30-ago no depende de esto: sale
  del savepoint actual tal cual está.
- **El tenant sintético (R-REV-3) es parte de producción,** no un juguete: es el
  entorno de ensayo permanente del camino completo, incluido SMTP real a buzones
  propios. La primera vez que el sistema recorra su último milímetro será contra
  nosotros mismos, no contra un tercero.

---

## §8. Plan por etapas — esfuerzo y puertas, no fechas dogma

Estimo esfuerzo en sesiones de trabajo del agente (S). Las puertas son de calidad,
no de calendario. Orden pensado para que cada etapa deje el sistema MEJOR aunque la
siguiente nunca llegue.

**E0 · Fundación del laboratorio (1 S)**
Rama principal limpia + `KAIZEN_DATOS/` si apruebas R-REV-1 + tenant sintético
`empresas/laboratorio/` con 50 leads ficticios + baseline: suite 916/1/7 registrada
como base del laboratorio.
*Puerta:* suite reproducida en réplica; savepoint verificado legible.

**E1 · Cimientos y verde total (1–2 S)**
I-1/I-2/I-3 (persistencia de insumos) · texto AI Act email (tu texto, mi cableado:
fichero de variantes + composer + Brand check + candado) · `registro sync` en
REVISIÓN DIARIA · watchdog de flags en el forense · commit R6.
*Puerta:* **917+/0/7** — cero rojos por primera vez desde el 02-ago; forense con
checks nuevos verde.

**E2 · Unificación de columna (3–5 S)**
Ledger único (importa `.kaizen_cost.json`, retira contadores) → cola única
(propuestas+hash/token/TTL/claim) → bus único (shim core/bus con fecha de derribo,
RUE a catálogo) → máquina única (M2 canónica, P9 proyección) → ejecutor único como
única puerta. Cada fusión: corte directo + verificación en réplica + suite.
*Puerta:* un lead sintético recorre TODO el circuito (Fase 0 → tarjeta → SÍ →
ejecutor → SMTP al buzón propio del tenant laboratorio) dejando UNA sola traza
coherente; contadores viejos retirados; suite sube.

**E3 · Extirpaciones (1–2 S)**
Las seis de §6, una a una, con suite verde tras cada una.
*Puerta:* −15% líneas activas; py_compile limpio; suite ≥ base.

**E4 · Cerebro Comercial (2–3 S + presupuesto R-REV-2)**
C1 decisor+email sobre el top-60 · C2 rescate de ambiguos (ya hay descartes
persistidos) · C3 contexto comercial. Primero contra el tenant sintético, luego
contra el corpus real (leyendo webs públicas: es prospección, no contacto).
*Puerta:* métricas de la tabla §4 medidas y escritas; coste real vs estimado.

**E5 · La Colmena (3–4 S + presupuesto)**
Relay compose local pineado + `kaizen-mcp` + 3 personas (Director/Forense en BAJA,
Comercial BAJA→MEDIA) + parada N=3 + coste por turno en canal + forense publicando
la mañana.
*Puerta:* una orden por chat termina como tarjetas en la Mesa con coste visible;
dos personas colaboran y se detienen solas; una semana de uso real tuyo.

**E6 · Autonomía ganada (2 S)**
El bucle historial→petición de subida→firma humana→bajada automática al primer
fallo, cableado en gates + Mesa.
*Puerta:* primera subida de nivel REAL firmada por ti con su evidencia sellada.

**E7 · Producción (2–3 S + dominio DR-10)**
VPS: systemd + TLS + Mesa/panel/relay + backups con drill nº1 con acta + R-13
retención/crypto-shredding.
*Puerta:* la Mesa abre desde tu móvil con tu PC apagado; drill de restauración OK.

Total estimado: **15–22 sesiones de agente.** Sin fechas dogma: con las puertas,
cada etapa se promociona cuando está verde, no cuando el calendario lo diga. La
única cita externa real es la entrega del 30-ago — y esa sale del savepoint, no de
aquí.

---

## §9. Riesgos del marco nuevo

Los del v0.1 §8 siguen (Buzz beta, bucles, PII al chat, SQLite, bus factor,
inyección vía leads). El marco laboratorio añade tres nuevos, con su contramedida:

| # | Riesgo nuevo | Contramedida |
|---|---|---|
| R-D11-11 | **Deriva de laboratorio**: tanto experimento que el árbol quede peor que el savepoint y nada se promocione nunca | Puertas por etapa + "cada etapa deja el sistema mejor aunque la siguiente no llegue" + forense diario también en laboratorio |
| R-D11-12 | **Confusión de entornos**: creer que el laboratorio es producción y enviar algo real desde aquí | El tenant real mantiene envío deshabilitado en laboratorio; el tenant sintético es el único con SMTP vivo; el forense canta si eso cambia |
| R-D11-13 | **El savepoint se pudre** (discos que no leen, bundle que no restaura) | Verificación trimestral de restauración del savepoint, con acta (§7) |

---

## §10. ADRs propuestas (008–015) y decisiones de Iván

- **ADR-008** · Sustrato G3 = columna única; knowledge = almacén de trabajo
  sincronizado. *(sin cambios desde v0.1)*
- **ADR-009** · El chat propone, la Mesa dispone — las herramientas de ejecución
  externa NO EXISTEN en la Colmena. *(sin cambios)*
- **ADR-010** · Colmena = cockpit del operador; Alejandro ve la Mesa. *(sin cambios)*
- **ADR-011** · Dependencias beta clavadas; upgrade con acta. *(sin cambios)*
- **ADR-012** · SQLite hasta que los números manden otra cosa (umbral: >100k leads
  o >50 escrituras/s sostenidas). *(sin cambios)*
- **ADR-013 · NUEVA** · Savepoint inmutable + laboratorio libre; promoción entre
  ambos como acto con liturgia (suite en clon + forense 7 días + R9 + nuevo
  savepoint).
- **ADR-014 · NUEVA** · Autonomía ganada: subida por historial con firma humana,
  bajada automática al primer fallo, techo inamovible en las acciones externas.
- **ADR-015 · NUEVA** · Separación código/datos: los datos de terceros viven fuera
  del árbol de git; el código limpio puede tener remoto privado. *(condicionada a
  tu firma de R-REV-1)*

**Decisiones que quedan en tu mesa (6, en orden):**

1. **Aprobar este v0.2** como plan vigente del laboratorio (o corregirlo — v0.3).
2. **R-REV-1**: separación código/datos + remoto privado. (La que más protege tu
   trabajo; la única que toca una decisión tuya "permanente", por eso va firmada
   por ti o no va.)
3. **R-REV-2**: cifra mensual del laboratorio (propongo 10 €/mes).
4. **Texto AI Act para email** (sigue siendo el desbloqueo del canal y del rojo).
5. **Dominio (DR-10)** — desbloquea E7 y el envío real de producción.
6. Los datos de **buzz** que dijiste que me pasarías, si siguen pendientes.

---

*D11 v0.2 — reescrito con criterio propio por orden del operador. Donde propongo
revisar una norma, la firma es suya; donde la norma es ley o es el alma del
producto, lo digo sin rodeos y la defiendo. Si algo aquí contradice al código
testeado, gana el código.*
