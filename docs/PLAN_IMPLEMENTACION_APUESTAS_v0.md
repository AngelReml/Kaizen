# Plan de implementación — Apuestas y dosier v0

Estado: **ejecutado A1–A7 el 2026-10-01** (ver §5 Resultado). Concepto: `docs/APUESTAS_Y_DOSIER_v0.md`.
Decisiones de Ángel: K1, L1, M1 (decide él), N1; P1 y Q1 asumidas por su orden de "ponerse a buscar nichos ya".
**Decisión R retirada** (tope de coste): no hay gasto que aprobar; el ciclo 0 usa modelos gratuitos y el freno es el tope diario del propio WebLLM.

## 0. Correcciones a lo que dije antes (honestidad)

1. **Kaizen SÍ tiene búsqueda web:** `ddgs` (DuckDuckGo) en `departments/prospeccion.py` y `agentes.py`. Dije que no había ninguna herramienta; mi comprobación buscó las librerías equivocadas. Consecuencia: el ciclo 0 puede traer fuentes reales sin esperar a WebLLM.
2. **Qué significa VERIFICADA con `ddgs`:** que la fuente **existe y dice ese extracto** (URL, fecha de consulta y extracto los copia el CÓDIGO del resultado de la búsqueda; el modelo nunca los escribe). Que el extracto sostenga la afirmación lo vincula el modelo; Ángel puede revisarlo. La etiqueta se rebaja a RECORDADA si el modelo cita una fuente inexistente.
3. **WebLLM no está conectado a Kaizen:** es un puente en el PC de Ángel (`127.0.0.1:20130`); desde la nube de desarrollo no se alcanza. Se probará con un servidor simulado.

## 1. Piezas

| Pieza | Fichero | Qué hace |
|---|---|---|
| Apuestas | `core/apuestas.py` | Almacén + máquina de estados K1 + validación del dosier + control de novedad + cuotas + sellado. |
| Modelos | `core/exploracion_modelos.py` | Cliente WebLLM (OpenAI-compatible, `/external/v1`), adaptador de `claude_client`, rotación de modelos, manejo de 403/429/404/5xx. |
| Búsqueda | `core/exploracion_busqueda.py` | Envoltorio de `ddgs`: devuelve título, URL http(s) y extracto. |
| Exploración | `core/exploracion.py` | Lentes, memoria, ciclo (proponer → filtrar → seleccionar por cuotas → buscar → redactar → validar), tanda con frenos, informe. |
| Panel | `panel_mando/app.py`, `mundo.py` | `GET /api/apuestas/{empresa}`, `POST /cmd/apuestas/transicion`, números por estado en la foto del Mundo. |
| Lanzador | `herramientas/apuestas.py`, `lanzadores/NICHOS.cmd` | Lanzar la tanda, listar, ver, elegir/descartar desde cmd. |
| Eventos | `eventos.json`, `nucleo.py`, mapa | Eventos `inteligencia.apuesta.*` y `inteligencia.exploracion.*`. |

## 2. Reglas de diseño (aprendidas en la capa anterior)

- **Sellar fuera del candado de datos** (el interbloqueo ABBA con la bitácora fue real): decidir y guardar bajo `k.transaccion()`, publicar después.
- **Código de salida comprobado** en cada ejecución (nada de `| tail` que lo oculte).
- Cada garantía con **prueba de mutación** (se rompe a propósito y el test debe fallar).
- **Contenido externo = datos, no órdenes:** los extractos de búsqueda y las respuestas de modelos se validan y escapan; el modelo no puede fijar URL ni fecha de una fuente.
- **El texto del dosier no va a la bitácora:** solo ids, estados, coordenadas y huella sha256.
- Todo con `llm` y `buscar` **inyectables**: los tests no usan red ni modelo.

## 3. Fases y pruebas

| Fase | Contenido | Prueba que la cierra |
|---|---|---|
| A1 | `core/apuestas.py` | FSM completa (transiciones válidas/ inválidas, solo operador decide), validación de dosier, vetos, novedad, cuotas, concurrencia sin interbloqueo. |
| A2 | Eventos y frases | Paridad RUE↔renderers; mapa regenerado. |
| A3 | Modelos y búsqueda | Servidor HTTP simulado: 200/401/403/404/429/5xx, rotación, token nunca en logs ni errores. |
| A4 | Exploración | Modelo simulado **deliberadamente repetitivo**: se rechaza, la rotación de lentes impide repetir lentes entre vueltas, las cuotas se cumplen, los frenos paran (cap, horas, PARAR TODO, sello roto, 2 ciclos vacíos). |
| A5 | Panel | Auth/CSRF, solo operador, entradas hostiles → 409, privacidad de la foto del Mundo (solo números). |
| A6 | CLI | Ejecución de extremo a extremo con modelo y búsqueda simulados; informe legible. |
| A7 | Cierre | Suite completa, e2e 20/20, revisión independiente, línea base, push. |

## 4. Lo que NO entra ahora (y por qué)

- Búsqueda con chats de WebLLM (Perplexity, Felo...): otra puerta, consume cuentas de Ángel, pide su permiso.
- Petición de financiación / monedero: capa siguiente. EN_PRUEBA solo con coste 0.
- Pantalla web de apuestas: por ahora CLI + informe en fichero.
- Aviso automático al vencer un plazo: hoy es un número en la foto del Mundo, no un evento.
- Prueba con modelo real: la hace Ángel en su PC; aquí no hay clave ni acceso a su WebLLM.

## 5. Resultado

| Fase | Resultado | Desviación |
|---|---|---|
| A1 apuestas | hecha | — |
| A2 eventos y frases | hecha | — |
| A3 modelos y búsqueda | hecha | — |
| A4 exploración | hecha | Los frenos de PARAR TODO/horas/autonomía se miran **antes de cada pregunta** (el plan decía entre ciclos; lo corrigió la revisión). |
| A5 panel | hecha | — |
| A6 lanzador | hecha | Falta la **herramienta `redactar_dosier` en el chat** de Inteligencia (N1): la tanda lo hace por código. `NICHOS.cmd` no se pudo ejecutar en Windows. |
| A7 cierre | suite 1724 pasadas / 8 omitidas, e2e 20/20, revisión independiente, línea base | — |

### Qué se encontró por el camino (honesto)
- **Bug grave mío, cazado por las pruebas:** normalizaba `es_ES` a minúsculas y el vocabulario cerrado dice `es_ES`: rechazaba **todos** los candidatos legítimos.
- **Fallo latente:** un `tanda_id` hexadecimal puede ser todo dígitos (~1 %) y la bitácora lo toma por un teléfono (R-07). Ahora empieza por letra y va en una clave `_ref`.
- **Bug de rotación:** tras un 404 el cliente saltaba un modelo (índice sobre lista que encoge). Ahora usa cola circular.
- **Error de método mío:** una mutación con `git checkout` descartó cambios sin commitear de `mundo.py` (los rehice), y dos `pkill -f` se mataron a sí mismos.
- **Revisión independiente (1 alto, 4 medios, varios bajos), todo verificado y corregido:** una respuesta hostil del modelo abortaba la tanda; el proxy del
  entorno desviaba la petición y con ella el token; los frenos solo se miraban entre ciclos; el aprendizaje de una ronda se pisaba al abrir la siguiente;
  VERIFICADA sobreafirmaba y el doc decía que Inteligencia no podía buscar; novedad ciega a otros alfabetos y a sectores cortos; vetos esquivables con caracteres
  invisibles; informe que interpretaba html y enlaces del modelo.
- Cada garantía tiene **prueba de mutación** (se rompe a propósito y el test falla).

### Límites que siguen abiertos
1. La búsqueda `ddgs` no se probó en vivo; WebLLM y los modelos reales tampoco; `NICHOS.cmd` no se ejecutó en Windows.
2. Umbrales (similitud 0,5, cuotas, 10 lentes, 3 lentes por ciclo) **sin calibrar**: la primera tanda real los afinará.
3. Un ciclo sigue siendo largo; el sello roto solo se comprueba entre ciclos.
4. Si WebLLM cambia su API o el cap diario, la tanda para (429) y lo cuenta; no reintenta al día siguiente sola.
5. Sin pantalla web de apuestas ni aviso en el feed al vencer un plazo.
