# KAIZEN-D10 — CENTRO DE MANDO DEL OPERADOR
## Serie de dossieres KAIZEN · Documento transversal de superficie (G5 hecho producto)

**Autor:** agente constructor; aprobado por el operador.
**Version:** **0.2 — CANON.** Sustituye a v0.1-PROPUESTA tras la pasada de empatia:
las 9 modificaciones fueron aprobadas por el operador en sesion 2026-07-10 (literal:
"ahora si me ha entendido"). La construccion NO arranca hasta orden expresa (P0).
**Declara contra:** KAIZEN-D00 v1.0 (§7, §3, §4, §6, §8) y D09 (R-02/R-16, DC).
**Mision en una frase:** que CADA accion de Kaizen sea visible y gobernable por el
operador de un vistazo y con pocos clics — y que usarlo se sienta como una cocina
propia, no como una cabina de avion.

---

## §0 — TESIS: PROYECCION SIN SEGUNDO CEREBRO + EMPATIA COMO LEY

El backend ES el panel (leccion Shinobi): el panel no almacena nada y no decide nada;
proyecta primitivas testeadas (772/7) y todo comando vuelve por los mismos gates que
la CLI. Cuatro leyes — FIJADO:

- **L1 · Fuente unica.** Todo sale de: bitacora RUE (`core/rue`), cola del sustrato
  (`core/aprobaciones`), libro de coste (`core/techos`), verificacion
  (`core/verificacion`), panico/palancas (`core/panico`), registro de empresas
  (`core/tenants`) y el knowledge de cada cubo. Prohibido un almacen propio del panel.
- **L2 · Nada invisible, por construccion.** Tipo del RUE sin renderer o accion sin
  control mapeado = test de paridad en rojo (§7). Incluye la salud del PROPIO panel.
- **L3 · Mismo gate para el dedo que para el codigo.** Cada boton invoca la funcion ya
  testeada, con identidad, y deja evento. Ningun endpoint atajo.
- **L4 · Idioma humano en el primer nivel (nuevo, empatia).** Ninguna sigla del canon
  en la pantalla uno. La tecnica existe, pero vive un nivel mas abajo, a peticion.

## §1 — LO EXISTENTE: VEREDICTOS (sin cambios desde v0.1, ya aprobados)

| Superficie | Veredicto — FIJADO |
|---|---|
| `api/server.py` + `panel/director.*` | **ABSORBER como esqueleto** (auth `KAIZEN_TOKEN` y tests ya hechos; webhooks de voz quedan montados intactos, voz DE BAJA) |
| `centro_mando.py` (8600) | **ABSORBER**: su alta de empresa pasa a "Ajustes"; el nuevo Centro HEREDA el puerto 8600 y el lanzador de doble clic |
| `mesa_jefe.py` (8700, PIN) | **COEXISTIR, intocable** (audiencia cliente, R8) |

## §2 — LA PANTALLA UNO: "LA MAÑANA" (nuevo nucleo, empatia §E1)

El panel abre SIEMPRE en La Mañana — el patron Mesa del Jefe aplicado al operador:

1. **Saludo y resumen en cristiano** (3-5 frases generadas de las primitivas, sin LLM):
   "Buenos dias. Desde ayer: Kaizen preparo 4 emails para Laboratorio; Marca aprobo 3;
   hay 2 esperando tu SI. Gastados 12 centimos de 10 €. Un plazo cerca: variantes
   del reglamento de IA (quedan 23 dias)."
2. **Las tarjetas** (cola de aprobacion, §4): lo que espera tu SI/NO, con su mecha.
3. **Avisos que importan**: plazos ≤30 dias sin resolver (reutilizan las alertas
   30/7/1 de D08), alertas CRITICAS de Inteligencia, y el estado "modo ahorro" si
   el tope del dia mordio. Nada mas.
4. **Un solo boton** al fondo: "Sala de maquinas".

Cabecera minima: nombre de la empresa activa · boton **PARAR TODO** · **latido** del
panel (§8). Sin reloj permanente de plazos (ansiedad fuera: los plazos son tarjetas).

**Estados vacios — FIJADO:** cada bloque tiene su frase diseñada ("Nada que aprobar.
Kaizen sigue trabajando; te avisare."). Una zona en blanco parece rota; aqui no hay
zonas en blanco. **Primera vez:** tour de 3 burbujas maximo (que es una tarjeta, que
es PARAR TODO, donde esta la Sala), y no vuelve a aparecer.

## §3 — NIVEL 2: "SALA DE MAQUINAS" (la cabina, por eleccion)

Cuatro pestañas: **Historias · Cubos · Dinero · Ajustes**.

- **Historias (empatia §E2, sustituye al rio como vista principal):** los eventos
  agrupados por hilo (`correlacion_id`) y narrados como frases: "Bar Sintetico:
  prepare un email → Marca lo aprobo → espera tu SI → enviado → contesto". Filtro
  por empresa/cubo/dias. Dentro de cada historia, "ver detalle tecnico" despliega
  los eventos crudos con hash y el sello de tinta. **El rio crudo completo** (con el
  renderer generico "visible aunque feo" del test de paridad) vive aqui como cajon
  tecnico — jamas en La Mañana.
- **Cubos:** 8 tarjetas de salud → drill-down con los controles DIRIGIR (§5).
- **Dinero:** "Hoy: 12 centimos de 10 €" + barra; historial simple; export CSV; el
  libro con decimales completos, en el detalle. **Dinero humano — FIJADO (empatia
  §E7):** primer nivel siempre en centimos/euros redondeados; "modo ahorro" se explica
  solo: "Se alcanzo el tope del dia; lo urgente ya aprobado se completara".
- **Ajustes:** empresas (alta absorbida del 8600 como asistente de 3 pasos con resumen
  final), mandato, palancas, umbrales. **Guardas (empatia §E9):** esta pestaña asume
  que NO es para niños, y por eso: valores acotados (sin texto libre para numeros),
  consecuencia en cristiano antes de aplicar, y boton "volver al valor recomendado"
  en cada ajuste. Cambiar algo aqui SIEMPRE deja evento con identidad.

## §4 — LAS TARJETAS Y LA MECHA (empatia §E4 — el corazon del gobierno)

Anatomia FIJADA de toda tarjeta de aprobacion:

1. **Que es**, en una frase: "Email inicial para Bar Sintetico (Laboratorio)".
2. **La consecuencia del SI**, obligatoria: "Si dices SI: se enviara 1 email real".
3. **Que pasa si no haces nada**: "Caduca en 71 h; se aborta y te avisare".
4. El contenido completo + veredicto de Marca (escudo) + sello de tinta en hover.
5. Nombre de la EMPRESA repetido en la tarjeta (no solo en cabecera).

Controles con **friccion asimetrica**: NO = un toque; SI de accion que sale al mundo =
**mantener pulsado**. Y al soltar, **la mecha**: "Se envia en 60 segundos — DESHACER".
La mecha usa mecanica ya construida y testeada (APROBADA → revocar gana antes del
claim): el clic irreversible se convierte en un minuto reversible. Duracion de mecha
por clase en config (60 s por defecto; 0 = sin mecha para acciones internas).

## §5 — MAPA ACCION → VISIBILIDAD → CONTROL (conservado; columna "se ve" re-situada)

| Origen | Se ve | Se gobierna (→ funcion real) |
|---|---|---|
| Sustrato·Aprobaciones | Mañana: tarjetas con consecuencia y mecha | Aprobar/Denegar/Deshacer-mecha → `ColaSustrato.*` (claim atomico) |
| Sustrato·Coste | Mañana: frase de gasto; Sala·Dinero: detalle | Cambiar tope (mandato, con guarda) → `tenants`; export → `LibroCoste.export_csv` |
| Sustrato·Panico/Palancas | Cabecera: PARAR TODO + estado | Mantener 2 s → `Panico.activar`; reanudar solo-operador → `desactivar` |
| Sustrato·Verificacion | Escudo en cada contenido (veredicto+razones; hash en hover) | Re-validar → `validar_borrador` (cache R-02) |
| Sustrato·Bitacora/RUE | Sala·Historias (narradas) + cajon tecnico (crudo) | "Comprobar el sello" 1 clic → `Bitacora.verificar` (ruptura señalada en cristiano) |
| Comercial (D01) | Historia por lead; pipeline por estados en Cubos; atribuciones con cadena legible | Transicionar (V1-V6) → `PipelineCanonico`; validar pedido externo (humano); preparar borradores → cola |
| Brand (D02) | Directrices activas con version; tasa de rechazo | Alta/editar/suspender → `CuboBrand` (versionado sin rotura) |
| Operaciones (D05) | Capacidad de hoy + pedidos PENDIENTES si no se declaro (R-08) | Declarar capacidad (input de 10 s) → `declarar_capacidad`; confirmar/reschedule |
| Finanzas (D04) | Liquidacion del mes (hash), aging; SIF con banda ambar permanente "aun no certificado" | Calcular → `Liquidador`; conciliar (humano); anular (humano siempre) |
| Marketing (D06) | Campañas con gasto/presupuesto y kill-switch | Aprobar/pausar; publicar real NO existe en v1 (dry) |
| Inteligencia (D07) | Alertas clasificadas en Mañana si CRITICAS; resto en Cubos | Reconocer/Descartar (alimenta FP); umbral versionado |
| Cumplimiento (D08) | Plazos como tarjetas en Mañana (≤30 d); expedientes en Cubos | Registrar obligacion; aportar evidencia; compilar defensa |

Regla de cierre intacta: tipo nuevo del RUE sin fila → paridad lo caza y el renderer
generico lo pinta en el cajon tecnico — visible aunque feo, jamas oculto.

## §6 — IDIOMA DE PANTALLA (nuevo — empatia §E3) — FIJADO

Diccionario obligatorio (canon → pantalla): tenant → **empresa** · IRREVERSIBLE-EXTERNA
→ **"sale al mundo"** · bitacora/RUE → **"historial sellado"** · escalera de degradacion
→ **"modo ahorro"** · panico → **"PARAR TODO"** · hash/seq/event_id → ocultos tras
**"ver detalle tecnico"** · claim/outbox/SSE → nunca aparecen · CADUCADA → "caduco sin
respuesta" · PENDIENTE_VALIDACION → "esperando tu confirmacion".

**Errores como escudo (empatia §E8) — FIJADO:** todo gate que bloquea se muestra como
proteccion, con escudo bambu y tres partes: que NO paso, por que en cristiano, que
puedes hacer. Ejemplo canonico: "No se envio: este contacto ya recibio sus 2 mensajes
permitidos (la ley marca el limite). No hay nada que hacer: Kaizen te protegio."
Prohibido mostrar una traza o el nombre de una excepcion en el primer nivel.

## §7 — CONEXIONES BACKEND (conservado integro de v0.1)

- **SSE con cursor `seq` y replay** desde la bitacora: pestaña cerrada dos horas =
  rio reproducido, nada perdido. Hub en proceso via hooks de `Bitacora.publicar`
  (acoplamiento cero; sin panel, nada cambia — P1).
- **Comandos**: `click → POST /cmd (identidad + empresa) → gates (palanca/panico,
  hard stop si gasta) → funcion testeada → evento (origen plataforma.panel) → el rio
  devuelve el resultado`. IRR-EXT solicita en cola, jamas ejecuta directo.
- **Test de paridad**: RUE↔renderers + catalogo de acciones↔controles + (nuevo) salud
  del panel. Falta = suite roja.
- El panel NUNCA llama a un LLM; lecturas locales, 0 €.

## §8 — EL LATIDO (nuevo — empatia §E9b) — FIJADO

El panel se auto-vigila y lo muestra: punto discreto "al dia" / "datos de hace 3 min —
reconectando" / "sin conexion con Kaizen". Un panel congelado enseñando un "todo bien"
viejo es la peor invisibilidad; por eso el latido entra en el mapa de paridad y tiene
test propio (cortar el stream en test debe cambiar el estado visible).

## §9 — CAPA VISUAL (conservada + matiz)

Marca KAIZEN del manual (51 pags): bambu `#7A8B5A` unico acento; modos **Hiru** (dia)
/ **Yoru** (noche); Cormorant Garamond (titulos y cifras protagonistas), Inter (UI),
JetBrains Mono (solo en detalle tecnico); fuentes locales, cero CDN. El **sello de
tinta** (hanko bambu) vive en el hover del detalle: emociona sin estorbar. Estados en
tinta sobria (exito bambu, aviso ambar apagado, bloqueo tinta roja seca). Paletas de
tenant solo en vistas de CLIENTE. Animacion ≤150 ms; la mecha es la unica animacion
larga permitida (60 s, barra que se consume).

## §10 — TECNOLOGIA (conservada): opcion A — FastAPI + HTML/CSS/JS artesanal + SSE,
sin build chain, Jinja, un `panel.css` de marca escrito a mano. React y TUI descartados
(trade-offs en v0.1 §5, sin cambios).

## §11 — DECISIONES ADOPTADAS POR DEFECTO (faciles de cambiar — ABIERTO suave)

1. **Modo por defecto: Hiru (dia).** Una constante de config (`TEMA_DEFECTO`); Yoru a
   un clic en Ajustes. Cambiarlo no toca arquitectura.
2. **Mini-vista movil: NO por ahora.** Localhost + token hasta que exista hosting
   persistente (S5/E2). La Mañana ya nace estrecha (una columna): si un dia se expone
   con tunel+PIN como la Mesa, el diseño no cambia. Revisar en S5.

## §12 — RIESGOS (v0.1 §6 integro) + los nuevos de la empatia

Se conservan los 8 de v0.1 (paridad, segunda verdad, perdida de eventos, comando sin
rastro, auth, sobrecarga, voz, drift). Nuevos:

| Riesgo | Mitigacion |
|---|---|
| La mecha molesta en acciones internas | Duracion por clase; 0 s para lo interno; SOLO "sale al mundo" lleva 60 s |
| El resumen de La Mañana miente por simplificar | Se genera SOLO de las primitivas con plantillas deterministas (sin LLM); cada frase es clicable hacia su fuente |
| Cambio de empresa a mitad de cola | Cambio de empresa limpia seleccion + cinta de color + nombre en cada tarjeta |
| Historias ilegibles con hilos largos | Historia colapsada a "ultimo paso + cuantos anteriores"; expandir a peticion |

## §13 — PLAN POR FASES (reordenado por la empatia; puertas binarias, commit por fase)

- **P0 · Esqueleto**: app unica en 8600 (absorbe auth), SSE cursor+replay, renderer
  generico, cajon tecnico. *Puerta:* todo evento de la suite visible; paridad verde;
  reconexion sin perdida; latido cambia de estado al cortar el stream (test).
- **P1 · Gobierno**: tarjetas con consecuencia + mecha 60 s (deshacer real via
  revocacion pre-claim) + PARAR TODO (mantener 2 s, pantalla de estado, reanudar) +
  friccion asimetrica. *Puerta:* carrera de doble clic = exactamente-una-vez; deshacer
  dentro de la mecha aborta de verdad (test); PARAR TODO retiene y reanuda sin perdida.
- **P2 · La Mañana**: resumen determinista en cristiano + tarjetas + avisos (plazos
  ≤30 d, CRITICAS) + estados vacios + tour primera vez. *Puerta:* diccionario §6
  aplicado (test: ninguna palabra prohibida del canon en el HTML del primer nivel);
  cada frase del resumen clicable a su fuente.
- **P3 · Sala — Historias y Dinero**: agrupacion por `correlacion_id` narrada; dinero
  humano + export. *Puerta:* una historia real de lead completa legible de punta a
  punta; "comprobar el sello" funciona con ruptura señalada en cristiano.
- **P4 · Sala — Cubos y Ajustes**: 8 tarjetas + drill-down §5; alta de empresa como
  asistente (absorcion 8600 completada; `centro_mando.py` retirado del lanzador);
  guardas de Ajustes. *Puerta:* mapa accion→control completo (paridad de acciones
  verde); alta E2E de empresa sintetica desde el panel.
- **P5 · Delicia y 90 segundos**: Hiru/Yoru completo, sello-hash, microinteracciones,
  revision contra el manual pagina a pagina. *Puerta doble:* **test de los 90 s**
  (el operador, sin ayuda: ¿cuanto he gastado hoy?, ¿que pasa si digo SI a esta
  tarjeta?, ¿hay algo urgente? — cronometrado, <90 s) **y R9**: Ivan lo usa en SU
  maquina y lo declara delicia. Criterio humano, innegociable.

Coste de construccion: 0 € en LLM (todo determinista); el gasto es tiempo de sesiones.

---

*Fin de KAIZEN-D10 v0.2 — CANON aprobado por el operador tras la pasada de empatia
(9 modificaciones integradas; v0.1-PROPUESTA queda superada como historico). Nada
construido aun: la construccion arranca en P0 SOLO con orden expresa del operador.*

Relacionados: [[SERIE_D]] · [[KAIZEN_D00_SUSTRATO_Y_CONTRATOS_v1_0]] · [[KAIZEN_D10_CENTRO_DE_MANDO_v0_1_PROPUESTA]] · [[CENTRO_DE_MANDO]] · [[MESA_DEL_JEFE]] · [[DECISIONES_REQUERIDAS_SERIE_D]]
