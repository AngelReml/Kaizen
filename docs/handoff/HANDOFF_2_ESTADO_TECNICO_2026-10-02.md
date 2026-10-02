# HANDOFF 2 · Datos técnicos: cambios realizados y estado actual

Fecha: 2026-10-02. Documento 2 de 3 (instrucciones: `HANDOFF_1_…`; concepto: `HANDOFF_3_…`).
Convención: **VERIFICADO** = comprobado en la sesión de origen · **REPORTADO** = lo contó otro agente · **POR VERIFICAR** = sin probar.
Sin nombres de clientes reales, claves ni nombre de usuario de Windows.

---

## 1. Repositorio (nube) — VERIFICADO
- Remoto: `AngelReml/Kaizen`. Rama de trabajo: `claude/clever-wozniak-p7mins` (alineada con su remota; `main` con la fusión del PR 1).
- **PR 1 fusionado** en `main`: `b7a000c`. Commits fusionados relevantes: `43b1fae` (pestaña Nichos, tanda robusta, revisión), `7bfe31e` (informe 10-01), `3698bfd` (cliente local), `3fa3f94` (3 lentes).
- Commits posteriores a la fusión, **ya subidos a la rama, sin PR**: `30d9171` (informe de estado 10-02 y referencia MCP), `2ed5e31` y `4a91b48` (mapa de alternativas, 2 pasadas), `ccca1f2` (informe Octask), `b9283a8` (candidatas de vídeo gratis). Este handoff será el siguiente commit.
- Última suite completa: **1798 pasadas, 8 omitidas, 0 fallos** (código de salida 0). Pruebas de navegador del Mundo: **21/21** (medido en `43b1fae`; las 3 lentes posteriores se probaron con la suite, no se repitió el navegador).

## 2. Qué se construyó (por fases, con ficheros)
### 2.1 Autonomía v0 (antes de esta etapa; resumen)
`core/autonomia.py`, `core/aprobaciones.py` (niveles bloqueados, cambio de nivel sellado, `EN_MANOS`/`HECHA`), `panel_mando/app.py` (`/cmd/ajustes/autonomia`, vigilancia con freno de 30 s), `panel_mando/colmena.py` y `mundo.py` (nivel efectivo por empresa y cubo). Niveles CERO/BAJA/MEDIA/ALTA; ALTA **bloqueada** esta temporada; bajan solos tras 3 tarjetas denegadas seguidas o sello roto; solo el operador sube (con motivo). Docs: `AUTONOMIA_v0.md`, `PLAN_IMPLEMENTACION_AUTONOMIA_v0.md`, `SUELO_Y_VOCABULARIO_v0.md`.

### 2.2 Apuestas y dosier (motor)
- `core/apuestas.py`: máquina de estados `BORRADOR→DOSIER→ELEGIDA→EN_PRUEBA→MEDIDA→CRECE|PODADA` (+`DESCARTADA` desde borrador/dosier/elegida); solo el operador decide; la regla solo propone; aprendizaje obligatorio al cerrar; `EN_PRUEBA` solo con coste_max 0 (N1). Dosier de 7 campos con etiquetas de evidencia `VERIFICADA/RECORDADA/SUPUESTO` (URL/fecha/extracto de las fuentes los copia el código, no el modelo). Vetos deterministas, control de novedad (Jaccard ≥ 0,5), cuotas, `Apuestas.resolver_id`.
- `core/exploracion.py`: lentes rotativas (**ahora 13**, 3 por ciclo, `LENTES_POR_CICLO=3`; las 3 nuevas: `negocio_con_fuga_digital`, `contenido_largo_sin_reciclar`, `proceso_manual_tapable_con_agente`), memoria, ciclo, tanda con frenos (PARAR TODO, tope de horas, nivel CERO, atasco de 2 ciclos vacíos, tope del proveedor), informe markdown.
- `core/exploracion_modelos.py`: `ClienteWebllm` (token solo en cabecera `Authorization`, solo loopback salvo `KAIZEN_WEBLLM_PERMITIR_REMOTO=1`, `trust_env=False`, rotación `zai/groq/nemotron`), `ClienteClaude` (de pago) y **`ClienteLocal`** (LM Studio u otro servidor con API tipo OpenAI: descubre el primer modelo cargado, descarta `<think>…</think>`, solo loopback, tiempo máximo 300 s).
- `core/exploracion_busqueda.py`: envoltorio de `ddgs`.
- `herramientas/apuestas.py` + `lanzadores/NICHOS.cmd`: consola (tanda, listar, ver, elegir, descartar, probar, medir, cerrar).
- Eventos `inteligencia.apuesta.*` y `inteligencia.exploracion.*` (owner D07) en `eventos.json`, frases en `panel_mando/nucleo.py`.

### 2.3 Fase B: conectar el motor al Mundo (esta etapa)
- `core/exploracion_fondo.py` (nuevo): tanda **en segundo plano**, una por empresa. Reserva atómica en la colección `exploracion`, clave `en_curso` = `{activa, desde(sello), latido, hasta, ciclos, ciclos_hechos, pid}`. `_viva()` descarta reservas huérfanas (propia sin hilo activo en `_ACTIVAS`; de otro proceso con pid muerto; sin latido en `LATIDO_MAX_S=45 min`). `_latir/_liberar` solo con el sello propio. `lanzar()` valida (`CICLOS_MAX=20`, `HORAS_MAX=48`), rechaza si ya hay una, si Inteligencia está en CERO o si PARAR TODO está activo, y lanza un hilo. `estado()` → `{en_curso, ultima}` (solo datos).
- `panel_mando/herramientas/inteligencia.py`: `ver_nichos` y `leer_nicho` (LECTURA), `buscar_nichos` (IRREVERSIBLE-INTERNA: propone tarjeta; con SÍ lanza la tanda; arg `ciclos` 1–20, 0 se rechaza).
- `panel_mando/app.py`: `GET /api/apuestas/{empresa}` (+`en_curso`, `ultima`), `POST /cmd/apuestas/transicion`, **`POST /cmd/apuestas/buscar`** (409 con `mensaje` si falta configuración, hay otra en marcha, PARAR TODO o nivel CERO), `st.fabrica_exploracion` (inyección en pruebas), `_fabrica_exploracion` envuelve `parar` con `st.panico`. `cmd_aprobar` devuelve `mensaje` cuando una tarjeta queda `ANULADA`.
- `core/aprobaciones.py` y `panel_mando/colmena.py`: el **motivo** de una tarjeta `ANULADA` ya no se pierde (se muestra en la tarjeta y el toast).
- `mundo/index.html`: pestaña **«Nichos»** (lista por estado, dosier con evidencia etiquetada, «Buscar nichos» con estado en vivo, botones elegir/descartar/probar/medir/cerrar, texto de modelos siempre con `esc()`, sin repintar con formulario abierto, bloqueo de doble envío) y botón «Ver los nichos» en el perfil del director de Inteligencia.
- Pruebas: `tests/test_exploracion_fondo.py`, `tests/test_inteligencia_nichos.py`, `tests/test_exploracion_local.py` (14), `tests/test_herramientas_inteligencia.py` (ahora espera 2 irreversibles), `tests/test_exploracion.py` (13 lentes, 5 ciclos), e2e `tests/e2e/mundo.e2e.js` (escenario **7b** nichos: debe ir **antes** del 8, que rompe el sello a propósito y deja a Inteligencia en CERO) y `tests/e2e/servidor_e2e.py` (ruta `/_e2e/nichos_fabrica`).
- Mutaciones comprobadas: se rompe a propósito y el test debe fallar (nivel CERO, sello de liberación, latido, reserva huérfana, parar). Una comprobación NO demuestra lo que dice: que el GET de descubrir modelo ignore el proxy (en loopback el proxy se salta solo).

### 2.4 Revisión independiente de la fase B (hallazgos corregidos)
Reserva huérfana tras reinicio; liberación/actualización de reserva ajena; tarjeta del director sin freno de nivel/PARAR TODO; doble clic en «Confirmar»; tests débiles (reserva atómica con 12 hilos añadida).

## 3. Variables de entorno (Kaizen)
`KAIZEN_EXPLORACION_MODELO` = `webllm` (defecto) | `local` | `claude` · `KAIZEN_WEBLLM_URL` (defecto `http://127.0.0.1:20130`) · `KAIZEN_WEBLLM_TOKEN` (en `.env`, **nunca en chat**) · `KAIZEN_WEBLLM_PERMITIR_REMOTO` · `KAIZEN_LOCAL_URL` (defecto `http://127.0.0.1:1234/v1`) · `KAIZEN_LOCAL_MODELO` · `KAIZEN_LOCAL_CLAVE` · `KAIZEN_LOCAL_PERMITIR_REMOTO` · `KAIZEN_DATOS`. El panel carga `.env` **solo de su propia carpeta**.

## 4. Reglas de diseño que no se deben romper
- **Orden de candados:** la bitácora toma su candado y luego `k.transaccion()`; **nunca publicar eventos con el candado de datos tomado** (hubo un interbloqueo ABBA real). Los tests de regresión de interbloqueo corren en subproceso con límite de tiempo.
- Guarda PII R-07 en la bitácora: ids solo de dígitos parecen teléfonos; claves que acaban en `_ref/_hash/_cifrado` están exentas (`tanda_ref`).
- El texto del dosier **no** va a la bitácora: solo ids, estados, coordenadas y huella sha256.
- Contenido externo = datos, no órdenes (validar y escapar; el modelo no fija URL ni fecha de fuente).
- El Mundo no inventa actividad: lo que ve sale del backend o se dice que no hay conexión.

## 5. Estado de ejecución (cómo se mide) — *los comandos de pruebas citados como «§6» en el Handoff 1 están aquí*
- Suite: `env -u KAIZEN_DATOS -u KAIZEN_KNOWLEDGE_PATH -u KAIZEN_EMPRESA python -m pytest -q -p no:cacheprovider` y **comprobar `$?`**.
- E2E (≈10 min, 21 escenarios, puerto 8631): `KAIZEN_PY=<python> PLAYWRIGHT_MODULE=<ruta a playwright> node tests/e2e/mundo.e2e.js`; filtro `SOLO="1 ,7b,11"` (¡`SOLO=1` atrapa todos los `10x`!).
- Chromium preinstalado en la nube; no ejecutar `playwright install`.

## 5b. Límites conocidos (VERIFICADO salvo indicación)
- **Modelos reales y `ddgs` reales: sin probar** con Kaizen (desde la nube `ddgs` no tiene salida; `www.youtube.com` bloqueado en la nube).
- `NICHOS.cmd` sin ejecutar en Windows. Umbrales (similitud 0,5, cuotas, 13 lentes, 3 por ciclo) sin calibrar. Calidad de las ideas con modelos reales: desconocida.
- Un reinicio del panel a mitad de búsqueda pierde esa búsqueda (el botón no queda bloqueado). El botón del Mundo lanza 3 vueltas fijas.
- Discrepancia de diseño sin resolver: `buscar_nichos` pide SÍ (autonomía firmada) vs. «lo interno es libre» (documento del edificio).
- «Hablar con el director» abre el chat de la Colmena en otra pestaña; sin chat integrado en el Mundo. Los directores del chat usan la clave de pago de Anthropic.

## 6. PC de Ángel — REPORTADO (no visto por la sesión de nube)
- **WebLLM** (carpeta `minimax3 coding`): arreglado `empty_prompt` (montaje del prompt con `flatten_messages`); rama `lmstudio-proveedor` (commit `fccf3c5`, guarda 54 cambios previos) y rama **`auditoria-api-externa`** con `b0b5d54` (proveedor LM Studio), `c47883f` (tests rojos), `11f7b9a` (arreglo: `_do()` trataba `Outcome` como diccionario → 500 en `zai/groq/nemotron`; en modo stream un `UnboundLocalError`), `d18958e` (comparación de token en tiempo constante). Tests: 46 pasadas en los dos ficheros nuevos (26 de LM Studio); suite completa sin `tests/extension` con código 0 (548 pasadas, 11 omitidas) salvo 2 fallos conocidos de `test_workshop_windows.py` por poco disco. **Sin push; sin probar con proveedores reales ni LM Studio real; temperatura y `max_tokens` no se reenvían a `zai/groq/nemotron`.** `pytest-asyncio` no está instalado (los tests asíncronos antiguos no se ejecutaban). Puerta externa apagada tras reiniciar **a propósito**; el token está en un fichero local.
- **LM Studio:** instalado; servidor local sin encender; modelos pequeños (~1,4 GB). **OmniRoute** (API tipo OpenAI en el puerto 20128) apagado; no conectado.
- **Carpeta `KAIZEN`:** rama `master` en `9c8675f` con 22 commits locales sin subir; **58 cambios sin guardar** (56 modificados, 2 nuevos: `AUDITORIA_E2E_2026-09-12.md`, `BRAINSTORM_EDIFICIO_KAIZEN.md`). Contienen arreglos de código con test (enrutado de órdenes de redactar, el libro de gastos de pruebas no suma el contador global, aviso de error 401 del proveedor) y un renombrado parcial de nombres reales a «Laboratorio». Rama `trabajo-local-auditoria-e2e` creada y `git add -A` hecho; **commit bloqueado** por el control de nombres reales (24 violaciones, 17 ficheros). Plan de copia privada + commit de los 41 limpios: **sin resultado recibido**. Posible riesgo: la ruta `diario/laboratorio/` en `runner_llm.py` frente a la carpeta real del disco (sin comprobar).
- `KAIZEN-mundo` (en `7bfe31e` tras `git pull`; **pestaña «Nichos» visible, vacía**) y el panel en el puerto 8600 se relanzaron; usan los datos compartidos de `KAIZEN_DATOS`; tiene `.env` con una sola línea (token de WebLLM) ignorado por git. El primer intento de una vuelta real falló en WebLLM (`empty_prompt`), ya arreglado en WebLLM, **sin reprobar**.
- **Disco `C:`:** 17,8 GB libres (llegó a 8,88). 19,5 GB en `vm_bundles` de Claude Desktop (máquina virtual de Cowork). SSD de 512 GB del portátil viejo con posible protección contra escritura: **sin diagnosticar**. Un `uv cache clean` anunció 3,1 GiB y solo liberó ~1 GB (hipótesis: enlaces duros con los `.venv`).

## 7. Investigador YouTube (Astra) — REPORTADO
- Proyecto local de Ángel (no es un repo; Astra hizo `git init`, commit `5269372`, rama `main`, 22 ficheros, datos privados en `.gitignore`). Copia completa previa verificada: 7.328 ficheros, ZIP 99.252.593 bytes, SHA-256 `960AD4199FB39C73C748FB36B98EE12459F669BF74E23CC2BE9B06B69881B45E`.
- **Fase 0 (solo lectura): 16 caminos** donde algo avanza/«ok» sin fichero válido. Los principales: listado de canal puede omitir vídeos sin avisar (1); salta por `estado='ok'` sin comprobar el `.md` (2); fallos temporales desaparecen del recuento (3); la barra usa el índice del bucle (4); `nuevos` sube antes de escribir (5); el error al escribir la nota se traga (6); SQLite se confirma antes que el fichero (7, 8); `reindexar` y reconstrucción con `continue` silenciosos (9, 10); el panel fuerza `estado=hecho, ok=True` (11); indicadores y `MAPA.md` cuentan SQLite, no el disco (12); la captura reanudable cuenta `OMITIDO` y fallos como avance (13, 14) y devuelve `ok:true` con `terminado:false` (15); la validación del TXT no demuestra contenido ni pertenencia (16).
- Estado del disco: 127 registros, **81 `ok` (los 81 con `.md` mínimo válido)**, 46 no-ok antiguos (no son omisiones confirmadas), **82 IDs con notas duplicadas (87 ficheros de más)**. Captura de Plan BTC: 1 guardado, 1 fallo temporal, 881 sin intentar, `terminado:false`. Las notas aún **no tienen resumen ni puntos clave**.
- **Fase 1A autorizada** con el alcance del Handoff 1 §5. Informe de la 1A: **pendiente**.
- Informe técnico del MCP (otra IA): `docs/referencias/INFORME_MCP_INVESTIGADOR_YOUTUBE_2026-10-02.md` (el MCP **no existe**; servirá a clientes locales, no a la sesión de nube).
- Vídeos de Alejavi Rivera localizados (REPORTADO): `IWA9LCvNW8g` (2026-09-27) y `mRn9flyjzVk` (2026-08-23); en ambos YouTube mostraba «Subtítulos no disponibles».

## 8. Documentos del repositorio relevantes
`docs/INFORME_ESTADO_2026-10-01.md` y `…-10-02.md` · `docs/MAPA_ALTERNATIVAS_2026-10-02.md` (alternativas con precios de terceros y la ley del correo en frío en España) · `docs/referencias/` (informe del MCP, prueba de Octask, candidatas de vídeo gratis) · `docs/APUESTAS_Y_DOSIER_v0.md` (+ §12–13 y secciones de fase B, ClienteLocal y lentes) · `docs/PLAN_IMPLEMENTACION_APUESTAS_v0.md` §6 · `docs/CONTRATO_MUNDO.md` · `docs/LINEA_BASE.md` · `docs/AUTONOMIA_v0.md` · `docs/SUELO_Y_VOCABULARIO_v0.md`.

## 9. Orden íntegra para Astra (Fase 1A) — enviada
```
OK, Astra. Adelante con la Fase 1, con este alcance y orden.
FASE 1A (ahora): contrato y contadores. Cubre tus caminos 2, 3, 4, 5, 6, 7, 8, 11, 13, 14 y 15.
- El orden correcto para guardar un vídeo: 1) escribir el .md en un fichero temporal en la misma carpeta; 2) validarlo releyéndolo; 3) renombrarlo de forma atómica; 4) SOLO ENTONCES confirmar en SQLite. Si cualquier paso falla, el vídeo queda como FALLO, nunca como ok.
- Cada vídeo termina en GUARDADO, OMITIDO (motivo explícito) o FALLO (motivo y si es reintentable). Un fallo temporal tras agotar reintentos se guarda como FALLO y cuenta en el resumen.
- El progreso y el "hecho" se calculan contando resultados reales en disco, no con el índice del bucle. Un canal solo es "hecho" si terminado=true y no hay fallos pendientes. Nunca ok=true engañoso: separa transporte_ok, tarea_ok, completo y parcial.
- Al arrancar: reconcilia los registros "ok" sin fichero válido marcándolos "inconsistente" (no los borres).
FASE 1B (después, con mi OK): listado de canal incompleto (camino 1), indicadores y MAPA.md desde el disco (12), reindexar y reconstrucción de notas (9, 10), validación más fuerte del TXT (16). El 4 % mínimo de la barra: al final.
REGLAS: por cada camino un test que FALLE antes y PASE después; commits pequeños; copia adicional de corpus.db con la copia en caliente de SQLite; solo migraciones aditivas; NO toques las notas duplicadas ni trates los 46 no-ok antiguos como omisiones confirmadas; NO contactes con YouTube en esta fase (pruebas con simulaciones); ejecuta las 11 pruebas actuales más las nuevas con código de salida; tabla final de los 16 caminos (ARREGLADO con test / APLAZADO / NO REPRODUCIDO); lo no probado, NO VERIFICADO; para y espera mi OK antes de la 1B.
```

## 10. Notas de entorno de la sesión de nube (para no repetir tropiezos)
- Salida de red por proxy; `www.youtube.com` bloqueado (curl y WebFetch). `WebSearch` funciona. `ddgs` no se pudo probar en vivo.
- El clasificador de la sesión bloqueó `git checkout -B … origin/main`; se resolvió con `git merge --ff-only origin/main`.
- Un `pkill -f` se mató a sí mismo antes: terminar procesos por PID.
- Los resúmenes de búsqueda de terceros (comparativas, blogs) tienen interés comercial: tratarlos como POR VERIFICAR hasta ver la web oficial.
