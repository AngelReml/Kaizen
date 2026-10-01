# Apuestas y dosier — v0

Estado: **decidido por Ángel e implementado el 2026-10-01** (ver §12); la firma formal de la tabla del §11 no consta. Plan: `docs/PLAN_IMPLEMENTACION_APUESTAS_v0.md`.
Decisiones de Ángel: **K1, L1, M1 (con la corrección "lo decido yo sobre todo"), N1**, y el requisito nuevo de
**diversidad y no repetición con una prueba nocturna**. Marco firmado: `docs/SUELO_Y_VOCABULARIO_v0.md`;
autonomía: `docs/AUTONOMIA_v0.md`.

Lo que está marcado **(propuesta)** es un valor por defecto mío que Ángel puede cambiar; no es decisión suya todavía.

---

## 1. Qué es una apuesta

Una **apuesta** (la "semilla" del Suelo) es una hipótesis de nicho o vía de ingreso, con su dosier, su prueba barata y
lo que se aprendió de ella. En el código se llamará `apuesta`; el texto que Ángel lee es el **dosier**.
(En el repo "dossier" ya designa los documentos de diseño D00–D11: por eso el objeto no se llama dossier.)

## 2. Estados (K1)

```text
BORRADOR → DOSIER → ELEGIDA → EN_PRUEBA → MEDIDA → CRECE
    ↓         ↓         ↓                         ↘ PODADA
    └─────────┴─────────┴──────────→ DESCARTADA
```

| Estado | Lo mueve | Entrada: condición comprobada por código |
|---|---|---|
| BORRADOR | Inteligencia | Tiene nicho, problema y público; pasa el control de novedad (§6). |
| DOSIER | Inteligencia | Los 7 campos del §3 completos y válidos, con sus coordenadas (§6) y el chequeo de vetos. |
| ELEGIDA | **Ángel** | Decisión suya. |
| EN_PRUEBA | **Ángel** | Criterio de muerte completo (señal, umbral, plazo con fecha, fuente del dato, coste máximo). Mientras no exista el flujo de financiación, coste máximo = 0 € (N1). |
| MEDIDA | **Ángel** | Resultado numérico real anotado con su referencia (como D1). |
| CRECE / PODADA | **Ángel** | Ver §5. Exigen un **aprendizaje** escrito. |
| DESCARTADA | **Ángel** | Desde BORRADOR, DOSIER o ELEGIDA, con razón obligatoria y aprendizaje. |

- PODADA y DESCARTADA son terminales. CRECE puede abrir una nueva ronda de EN_PRUEBA (numerada) con su propia petición.
- Cada transición se sella en la bitácora (id de apuesta, estado, huella sha256 del dosier; **nunca el texto**).
- El **aprendizaje** es obligatorio al cerrar (PODADA, DESCARTADA o paso a CRECE): qué se esperaba, qué pasó, qué se haría distinto.
  Es el "abono" del jardín y entra en la memoria que se le pasa a Inteligencia en cada vuelta (§6).

## 3. El dosier (7 campos)

1. **Nicho y por qué**: problema, público, por qué ahora.
2. **Evidencia** (ver §4).
3. **Coste de probarlo** y su **alternativa gratuita**.
4. **Señal esperada y criterio de muerte**: qué se mide, umbral, plazo con fecha, **de dónde sale el dato**.
5. **Capacidades necesarias**, cuáles tiene Kaizen y cuáles no (explorar fuera de lo que sabe hacer hoy está permitido).
6. **Qué necesita de Ángel** (pasos que ejecuta él, decisión C1).
7. **Cómo se obtiene señal de personas reales** (clics, respuestas, preventas...). Sin él el dosier no es válido.

Más: **riesgo legal** (bajo/medio/alto y por qué) y **vetos** (nada de mentiras, spam, reseñas falsas ni dinero político):
el código rechaza lo que caiga en una lista de categorías vetadas; el resto lo ve Ángel.

## 4. Evidencia honesta (L1)

Kaizen busca en la web con `ddgs` (DuckDuckGo, ya usado en la prospección). Por eso cada afirmación del dosier lleva una etiqueta:

| Etiqueta | Significa | Requisito |
|---|---|---|
| VERIFICADA | El modelo cita una fuente **real recuperada por la búsqueda** | URL, fecha de **consulta** y extracto, copiados por el CÓDIGO del resultado (el modelo nunca los escribe); una cita a una fuente inexistente se rebaja a RECORDADA |
| RECORDADA | Lo dice el modelo; sin fuente | — |
| SUPUESTO | Hipótesis sin base comprobada | — |

**Límite de VERIFICADA:** el código comprueba que la fuente existe y copia su extracto; que ese extracto **sostenga** la afirmación lo
juzga el modelo. Por eso el informe muestra el extracto y lo dice: el operador lo lee. Las búsquedas de WebLLM (Perplexity, Felo...) NO se usan.
Si la búsqueda falla, el dosier se hace igual con todo RECORDADA/SUPUESTO y el informe lo cuenta.

El ciclo 0 puede salir con poca evidencia verificada, y **se declara abiertamente**. Un dosier sirve como lista ordenada de
hipótesis, no como prueba. Su primer paso es una **verificación gratuita** que ejecuta Ángel. Nunca se presenta una
afirmación RECORDADA como si fuera un hecho.

## 5. Quién decide la poda y el crecimiento (M1 corregida)

**Ángel decide siempre.** La regla solo **propone**: compara el número medido con el umbral y dice "esto no llegó al umbral →
propongo PODADA" o "superó el umbral → propongo CRECE". Nada se poda ni crece solo.
Al vencer el plazo de una apuesta EN_PRUEBA el sistema **avisa** ("pide medición") y no cambia su estado.
CRECE exige además una petición de financiación (capa siguiente).

## 6. Diversidad y no repetición

Problema planteado por Ángel: que no se vuelva repetitivo a la segunda vuelta. Un modelo, dicho "no te repitas", no basta:
es una promesa, no una garantía. Por eso hay **mecanismos en código** (todo (propuesta), ajustable en un fichero de datos):

1. **Coordenadas.** Cada dosier declara: modelo de ingreso (servicio por encargo, producto digital, micro-suscripción,
   contenido/audiencia, afiliación, intermediación, automatización como servicio, datos/informes, otro), cliente
   (particular, autónomo, pyme, empresa grande, comunidad de aficionados), canal de captación, idioma/mercado, coste inicial
   (0 / ≤15 / ≤50 / >50 €) y tiempo hasta la primera señal (≤7 / ≤30 / >30 días), más el sector en texto.
2. **Control de novedad determinista.** Cada borrador se compara con **todas** las apuestas existentes, incluidas las
   PODADA y DESCARTADA: similitud de palabras (título + problema + público, sin palabras vacías) por encima de 0,5, o
   mismas coordenadas y sector → se **rechaza** diciendo a qué apuesta se parece, y se reintenta (máx. 3 por dosier).
3. **Cuotas por ciclo de 5 dosieres.** Al menos 3 modelos de ingreso distintos; como mucho 2 con el mismo cliente y 2 con el
   mismo canal; al menos 1 con coste 0 y señal en ≤7 días; al menos 1 **fuera de las capacidades actuales**.
4. **Lentes rotativos.** Una lista de unas 10 formas de mirar (p. ej. tareas repetitivas que una pyme paga por quitarse;
   cambios regulatorios con fecha; servicios manuales automatizables con IA; aficiones con poca oferta en español;
   información dispersa que alguien pagaría por ver ordenada; intermediación; estacionalidad; lo que Kaizen ya sabe hacer;
   quejas recurrentes sobre servicios existentes; errores caros y evitables). El ciclo *n* usa 3 lentes elegidos por
   rotación fija, así que la vuelta 2 **no puede** usar los mismos que la 1. Ángel edita la lista.
5. **Memoria.** En cada vuelta Inteligencia recibe lo ya hecho: título, coordenadas, estado y aprendizaje de cada apuesta.
6. **Exploración y explotación.** Los 3 primeros ciclos solo exploran. Después, si alguna apuesta mostró señal, al menos 1 de
   cada 5 dosieres es una variación de ella.

Límite honesto: estos mecanismos **garantizan que lo repetido se rechaza y que la cobertura se mide**, pero no que el modelo
tenga ideas buenas. La calidad de las ideas solo se ve con un modelo real.

## 7. La tanda nocturna (prueba "déjalo encendido")

H1 sigue siendo "lo lanza Ángel". Una **tanda** es una orden suya, acotada y única; **no** deja nada programado:

- **Parámetros:** por defecto 3 ciclos de 5 dosieres y 8 horas como máximo (`--ciclos`, `--horas`).
- **Frenos automáticos:** tope diario del proveedor (429), **PARAR TODO, tope de horas y autonomía de Inteligencia en CERO: se miran antes de cada pregunta
  al modelo** (un ciclo puede durar horas); el **sello roto** solo entre ciclos (recorre toda la cadena); y **2 ciclos seguidos con menos de 2 dosieres**
  (atasco o repetición).
- **Informe de la noche** al terminar: ciclos hechos, dosieres válidos y rechazados **con su motivo**, tasa de repetición
  (rechazos por similitud / intentos), cobertura por coordenadas, coste real, errores. Los dosieres se listan con su coste y
  su tiempo hasta la señal, **sin ranking subjetivo**: una puntuación hecha por el propio modelo sería opinión.
- **Dónde corre:** en el PC de Ángel, con `lanzadores\NICHOS.cmd`. Modelos: los tres gratuitos de WebLLM por `/external/v1` (zai, groq, nemotron), rotados
  entre preguntas; tope de 100 preguntas al día del propio WebLLM, que es el freno natural. **Coste: 0 €.** En la nube de desarrollo no hay clave ni acceso a
  WebLLM, así que allí solo se probó con un modelo y un servidor simulados.
- La decisión R (tope de coste de la primera tanda) **se retiró**: no hay gasto que aprobar.

## 8. Eventos y almacén

- Colección `apuesta` por empresa; las transiciones se sellan con eventos RUE nuevos (creada, dosier completado, elegida, en
  prueba, medida, crece, podada, descartada, rechazada por repetición). Payloads: ids, estados, coordenadas y huellas.
- El Mundo muestra **solo números por estado** (como el resto de salas). El texto del dosier se lee aparte (O1).

## 9. Lo que NO incluye (siguiente capa)

Petición de financiación y monedero (EN_PRUEBA con gasto), el Consejo que ensambla el informe, y los estatutos de cada cubo.
EN_PRUEBA solo admite coste 0 hasta entonces.

## 10. Decisiones abiertas

- **P** mecanismo de diversidad: propuesta = §6 completo.
- **Q** forma de la tanda: propuesta = §7.
- ~~R~~ retirada (sin gasto en el ciclo 0).
- Los umbrales (0,5 de similitud, cuotas, 10 lentes, 4 ciclos) son **propuestas** que se afinan con la primera tanda real.

## 11. Firma

| Campo | Valor |
|---|---|
| Aprobado por | |
| Fecha | |
| Cambios pedidos | |


## 12. Qué está implementado (2026-10-01)

| Pieza | Estado |
|---|---|
| Estados K1, dosier (7 campos), evidencia L1, vetos, novedad, cuotas | Implementado (`core/apuestas.py`). |
| M1: decide el operador; la regla solo propone | Implementado. Aviso de plazo vencido: un **número** en la foto del Mundo (no un evento). |
| Diversidad §6 (coordenadas, novedad, cuotas, lentes rotativos, memoria, variación) | Implementado (`core/exploracion.py`). Umbrales y lentes son propuestas **sin calibrar con un modelo real**. |
| Tanda con frenos e informe | Implementado; lanzador `herramientas/apuestas.py` y `lanzadores/NICHOS.cmd`. |
| N1 `redactar_dosier` como herramienta de Inteligencia en el chat | **No implementado: desviación.** Los dosieres los escribe la tanda por código; el director de Inteligencia en el chat NO puede escribirlos. Sí puede **verlos y lanzarlos** (siguiente fila). |
| El director de Inteligencia y los nichos (B2) | Implementado: `ver_nichos` y `leer_nicho` (LECTURA: datos reales, nunca de memoria) y `buscar_nichos` (IRREVERSIBLE-INTERNA: propone una tarjeta y **solo con tu SÍ** lanza una tanda acotada, 1–20 vueltas, en segundo plano). Si falta el token o la API externa está apagada, la tarjeta queda ANULADA y **te dice qué hacer**. |
| Pestaña «Nichos» en el Mundo (B3/B4) | Implementado: lista por estado (brote, elegida, en prueba, medida, crece), dosier legible con la evidencia etiquetada, botón «Buscar nichos» con estado en vivo y botones para elegir, descartar, probar, medir y cerrar. Texto de los modelos siempre escapado. PARAR TODO detiene la búsqueda antes de la siguiente pregunta. Una sola búsqueda a la vez por empresa. |
| Pantalla web de apuestas | Sí, dentro del Mundo (fila anterior). La API sigue en `/api/apuestas/{empresa}` y el lanzar en `POST /cmd/apuestas/buscar`. |
| Búsqueda `ddgs` en vivo | Código listo; **no se pudo probar en vivo desde la nube** (sin salida a DuckDuckGo). |
| `NICHOS.cmd` | **No ejecutado en Windows** (se razonó la semántica de cmd). |
| Calidad de las ideas con modelos reales | **Desconocida**: es lo que dirá la primera tanda real. |

## 13. Cómo lanzarlo en el PC (cmd)

1. WebLLM encendido y su puerta externa activada (una vez): en su carpeta, `python -m scripts.external_api_admin enable` (imprime el token UNA vez).
2. En el `.env` de Kaizen añade `KAIZEN_WEBLLM_TOKEN=<el token>` (no lo pegues en ningún chat). Opcional: `KAIZEN_WEBLLM_URL` si no es `http://127.0.0.1:20130`.
3. Doble clic en `lanzadores\NICHOS.cmd` → opción 1. Al acabar deja un informe `.md` y los dosieres quedan en estado DOSIER.
4. Leer: opción 2 y 3; decidir: opciones 4 (elegir) y 5 (descartar). Probar, medir y cerrar: `python -X utf8 herramientas\apuestas.py probar|medir|cerrar ID ...`.
Para dejarlo encendido toda la noche: `python -X utf8 herramientas\apuestas.py tanda --ciclos 6 --horas 8` (el PC no debe suspenderse). Con 100 preguntas/día de WebLLM caben unos 6–8 ciclos; al agotarse, para solo y lo dice.

### Límites de la conexión con el Mundo (honesto)
- Probado con un modelo y una búsqueda **simulados** (pytest y un navegador real contra el backend real). Con **modelos reales y `ddgs` reales no está probado**.
- Si el proceso del panel se reinicia durante una búsqueda, la tanda se pierde; el candado de «en marcha» caduca solo (horas + 1).
- La búsqueda del botón son 3 vueltas fijas; el director puede pedir otro número (1–20).
- «Hablar con el director» sigue abriendo el chat de la Colmena en otra pestaña: dentro del Mundo aún no hay chat integrado.
