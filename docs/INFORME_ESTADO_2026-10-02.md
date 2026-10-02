# Informe de estado — 2026-10-02

Sustituye a `INFORME_ESTADO_2026-10-01.md` como foto del **punto exacto** en el que estamos.
Convención: **VERIFICADO** = lo comprobé yo con una ejecución o una lectura en esta sesión · **REPORTADO** = lo contó un Claude local de tu PC, no lo he visto yo · **POR VERIFICAR** = sin probar.
Este informe no contiene nombres de clientes reales ni datos personales a propósito (el repositorio tiene un control que los bloquea).

## 1. Resumen en cinco líneas
1. El motor de nichos, la pestaña «Nichos» del Mundo y las herramientas del director de Inteligencia están **fusionados en `main`** (PR 1).
2. Con modelos y búsqueda **reales** todavía no ha salido ni una vuelta completa: el primer intento falló en WebLLM (`empty_prompt`), ya arreglado por el Claude local, **sin reprobar**.
3. Tu carpeta de trabajo local tiene **58 cambios sin guardar en git**; el commit lo bloquea el control de nombres reales. Nada se ha perdido ni se ha subido.
4. La dirección estratégica se está replanteando: primero **qué puede hacer Claude (y las otras IAs)**, luego nichos, luego ejecutar. Nada de eso está decidido ni construido.
5. El disco ya no está en rojo (17,8 GB libres), con una limpieza grande pendiente de tu decisión (19,5 GB).

## 2. Repositorio (nube) — VERIFICADO
- `main` en `b7a000c` (fusión del PR 1). Todo lo hecho en esta etapa está commiteado y subido.
- Última suite completa: **1798 pasadas, 8 omitidas, 0 fallos**; pruebas de navegador del Mundo **21 de 21** (en el commit anterior a las tres lentes nuevas; las lentes se probaron con la suite, no se repitió el navegador).
- Contenido: pestaña «Nichos» (buscar, leer dosier, elegir, descartar, probar, medir, cerrar) · herramientas `ver_nichos`, `leer_nicho`, `buscar_nichos` (esta última pide tu SÍ) · búsqueda en segundo plano con una sola a la vez · cliente de modelo local (LM Studio, API tipo OpenAI) · 13 lentes de búsqueda (3 añadidas por tu sugerencia, revertibles).
- Revisiones independientes: dos rondas, hallazgos verificados y corregidos con pruebas de mutación.

## 3. Tu PC — REPORTADO (no lo he visto)
- Hay tres copias del repositorio: la carpeta de trabajo (`KAIZEN`, rama `master`), `KAIZEN-mundo` (copia con el Mundo; ahí se vio la pestaña «Nichos» tras un `git pull`) y `kaizen-publico`.
- `KAIZEN-mundo` y la carpeta de trabajo comparten la misma carpeta de datos (con dos empresas reales). La búsqueda de nichos escribiría en la empresa que muestre el panel. **Decisión pendiente (ver §5).**
- **WebLLM:** arreglado `empty_prompt` (montaje del prompt desde `messages`); proveedor nuevo `lmstudio` detrás de la puerta externa con 26 tests propios; commit hecho en una rama aparte, sin push. Un **segundo fallo** probable en la ruta de `zai`/`groq`/`nemotron` (`outcome.get`) pendiente de reproducir con test. La puerta externa se apaga al reiniciar WebLLM **a propósito** (decisión de diseño suya).
- **Carpeta de trabajo `KAIZEN`:** 58 cambios sin guardar (56 modificados, 2 nuevos). Se creó una rama aparte y se preparó todo; el commit **bloqueado** por el control (24 violaciones, 17 ficheros con nombres de clientes reales). `master` intacta. Plan acordado: copia de seguridad privada de esos 17 ficheros fuera del repositorio y commit solo de los 41 limpios, **sin saltar el control y sin push**. Resultado de ese plan: **no recibido**.
- **Disco `C:`:** 17,8 GB libres. 19,5 GB corresponden a `vm_bundles` de Claude Desktop (máquina virtual de Cowork). Según fuentes de usuarios es seguro borrarlo con la app cerrada y se regenera; **no lo has borrado todavía**. Otros: cachés regenerables (npm, uv, Temp, Playwright).
- **SSD de 512 GB** del portátil viejo con posible protección contra escritura: **sin diagnosticar** (riesgo: algunos SSD se ponen en solo lectura al fallar).
- **LM Studio:** instalado; servidor sin encender; modelos pequeños descargados (≈1,4 GB). **Prueba real de una vuelta de nichos: pendiente.**

## 4. Dirección estratégica (en discusión, nada decidido)
- **Dosier como formato de informe de nicho** y «Añadir nicho» a mano (recibir informes de fuera) antes que la búsqueda autónoma: propuesto, **sin tu «sí»**, no construido.
- **Capacidades primero:** el catálogo no es «qué hace Kaizen hoy» sino **qué puede hacer Claude y las otras IAs que orquestas** (con herramientas y conexiones) → de ahí salen los nichos → cada nicho trae su lista de huecos. Propuesto, **no construido**.
- **Web3:** lo harás tú por tu cuenta; yo investigo fuentes públicas en solo lectura. Kaizen no guarda claves. Los textos orientativos que has pasado **no se adoptan** salvo lo indicado en §2.
- **Impuestos (España), según resúmenes de despachos y prensa, sin verificar con gestor:** airdrop = ganancia patrimonial; staking = rendimiento del capital mobiliario; cambiar una cripto por otra tributa aunque no pases por euros. «No vender = no hay impuestos» **no es correcto**.
- **Reglas firmadas que siguen vigentes:** lo externo e irreversible lo ejecuta el operador; tope de 50 €; capa de financiación (planta 2) aparcada; planta 3 = Web3.

## 5. Decisiones que esperan por ti
1. ¿Buscar nichos guarda apuestas en una empresa real existente o en una **nueva y limpia**? (recomendado: nueva).
2. `buscar_nichos`: ¿sigue pidiendo tu SÍ (documento de autonomía firmado) o pasa a libre (documento del edificio, §5)? Hay una discrepancia entre ambos.
3. Los 17 ficheros con nombres reales: copia privada y renombrado a medias; ¿terminas el renombrado? ¿qué nombre en cada sitio?
4. ¿Adelante con «Añadir nicho» y/o con el catálogo de capacidades?
5. ¿Borras `vm_bundles` (19,5 GB) y las cachés?

## 6. Investigación inicial: vídeo con IA gratis (fuentes web, **sin probar nada**)
- **Kling AI:** [66 créditos diarios, hasta 720p](https://dreamina.capcut.com/ai-video/free-ai-video-generators-recurring-credits-vs-trials-2026), según esa comparativa.
- **PixVerse:** créditos iniciales más 60 diarios (misma fuente).
- **Pika:** 80 créditos al mes, 480p, sin marca de agua y con uso comercial según [esta guía](https://upsampler.com/blog/best-free-ai-video-generator-2026); mensual, no diario.
- **Wan 2.2 / LTX 2** gratis en la web de [Upsampler](https://upsampler.com/blog/best-free-ai-video-generator-2026), hasta 1080p, calidad por debajo de los modelos punteros.
- **Qwen:** fuentes dispares: una dice [«ilimitado y sin marca de agua»](https://www.seedance.tv/blog/qwen-ai-video-generator-free), otra «cuota limitada según cuenta y región». **Contradictorio: hay que probarlo.**
- **Meta Vibes:** [gratis con intentos ilimitados](https://metricool.com/meta-vibes/), pero Meta prevé pasar a suscripción para funciones extra.
- **Sora** [dejó de existir en abril de 2026](https://upsampler.com/blog/best-free-ai-video-generator-2026), según esa fuente.
- Las comparativas advierten de topes diarios, marcas de agua y uso comercial vetado en muchos planes gratuitos.
- **Publicación automática:** TikTok y YouTube dejan en privado lo subido por API sin una auditoría de la plataforma; Instagram tiene tope diario de publicaciones por API. Sin conector de publicación visible en esta sesión.
- **Siguiente prueba propuesta:** 1 a 2 vídeos cortos reales en dos o tres de estas herramientas, midiendo calidad, tiempo, marca de agua y límite diario.

## 7. Referencias guardadas
- `docs/referencias/INFORME_MCP_INVESTIGADOR_YOUTUBE_2026-10-02.md`: informe de otra IA para crear un MCP del «Investigador YouTube» (proyecto local tuyo). **No verificado por mí.**
- Idea planteada (no construida): vigilar una lista de canales, resumir cada vídeo nuevo y guardar los resúmenes en una carpeta de `.md` consultable por Claude. Según ese informe, el proyecto ya tiene corpus, búsqueda y vault; falta la vigilancia periódica, el resumen y la interfaz para Claude. Dudas abiertas: dónde corre (tu PC) y que la captura por navegador falló con el segundo vídeo en su prueba real.

## 8. Límites que siguen abiertos
Modelos reales y `ddgs` reales sin probar con Kaizen · `NICHOS.cmd` sin ejecutar en Windows · umbrales de la búsqueda sin calibrar · calidad de las ideas con modelos reales desconocida · todo lo de §3 es de oídas.
