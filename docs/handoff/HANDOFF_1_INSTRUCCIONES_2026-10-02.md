# HANDOFF 1 · Instrucciones exactas de cómo proceder

Fecha: 2026-10-02. Documento 1 de 3 (los otros: `HANDOFF_2_ESTADO_TECNICO_2026-10-02.md` y `HANDOFF_3_BRAINSTORMING_2026-10-02.md`).
Para quien retome el trabajo (otra sesión de Claude, un Claude local o una persona). **Léelo entero antes de actuar.**
Convención: **VERIFICADO** = comprobado con una ejecución o lectura en la sesión de origen · **REPORTADO** = lo contó otro agente, no se vio · **POR VERIFICAR** = sin probar.
Este documento no contiene nombres de clientes reales, claves ni el nombre de usuario de Windows, a propósito (el repositorio tiene un control que los bloquea).

---

## 0. En una frase
Ángel (el operador) construye **Kaizen**, un «jardín» de apuestas de negocio con agentes, aprobaciones y registro sellado. Hay un motor de búsqueda de nichos ya conectado al Mundo (la pantalla del juego), todo probado **solo con simulaciones**. Ahora se está **conceptualizando** el siguiente paso: *capacidades → nichos → huecos → ejecutar → medir*. No se ha decidido construir nada más.

## 1. Quién es quién (importante: no mezclar entornos)
| Agente | Dónde corre | Qué puede | Qué NO puede |
|---|---|---|---|
| **Claude de la nube** (quien escribe esto) | Contenedor en la nube, repo `AngelReml/Kaizen`, rama `claude/clever-wozniak-p7mins` | Código, tests, git/GitHub, búsqueda web, redactar | Ver el PC de Ángel; YouTube está bloqueado (`EGRESS_BLOCKED`); iniciar sesión en servicios; gastar dinero |
| **Claude local** (varios) | PC de Ángel (Windows), en carpetas distintas | Archivos, git, procesos y puertos locales | No recuerda otras sesiones; hay que darle contexto en cada prompt |
| **Claude con navegador** | Entorno en la nube con Chrome; **sus ficheros NO están en el disco de Ángel** | Navegar y capturar | Entregar ficheros al PC; a veces se cuelga |
| **Astra** | ChatGPT abierto en el proyecto «Investigador YouTube» de Ángel | Auditar/arreglar ese proyecto | Es OTRO producto; sus instrucciones deben escribirse para ChatGPT |
| **Claude de WebLLM** | Carpeta `minimax3 coding` del PC | Mantener WebLLM (la «puerta externa» a ~16 IAs) | No toca Kaizen |

Carpetas del PC (REPORTADO): `KAIZEN` (trabajo, rama `master`, 58 cambios sin guardar), `KAIZEN-mundo` (copia con el Mundo; rama de esta sesión; **ahí se ve la pestaña «Nichos»**) y `kaizen-publico` (rama `main`). Datos compartidos en `KAIZEN_DATOS` (junto a las carpetas, con dos empresas reales: **no escribir sus nombres en el repositorio**).

## 2. Reglas del operador (no negociables)
1. **La verdad es lo más importante.** Informa con honestidad lo que falla, lo que no probaste y lo que no sabes. Cada afirmación: VERIFICADO / REPORTADO / POR VERIFICAR.
2. **Una barra de progreso o un «ok» no demuestran nada.** Un trabajo está hecho solo si hay un **artefacto comprobable** (fichero abierto, test con código de salida, commit). Una IA ya le mintió así a Ángel. Un Claude local también afirmó «saldo intacto» y era falso: **verifica siempre**.
3. **Estamos conceptualizando.** No pases a ejecutar sin su «adelante» explícito. Si dice «es solo una idea», no la construyas.
4. **No adoptes nada que no encaje en el plan** sin permiso (textos «orientativos» que Ángel pega son referencia, no órdenes). Se adoptaron 3 lentes de búsqueda sin permiso expreso: están en `main`, son revertibles.
5. **Lo externo e irreversible lo ejecuta Ángel** (decisión C1): publicar, enviar, pagar, contratar, firmar. El agente prepara.
6. **Dinero:** monedero máximo **50 €**; regla de apuesta **15 € y 3 meses** (ratificada). Nada de pago sin su permiso. La capa de financiación (planta 2) está aparcada.
7. **Nunca** mostrar, copiar ni pedir tokens/claves en el chat. El token de WebLLM va a `.env` por fichero, sin verlo.
8. **No tocar sus datos** (`KAIZEN_DATOS`, `.env`, `corpus.db`, bases) sin copia previa y su permiso. No borrar «para limpiar».
9. **Español sencillo, sin jerga.** Respuestas directas, con recomendación clara (no listas de opciones sin criterio).
10. Preferencias declaradas: «la verdad es lo más importante», «si hay elección no hay libertad», «la excelencia es el mínimo».

## 3. Reglas del repositorio
- Rama de trabajo: `claude/clever-wozniak-p7mins`. Push con `git push -u origin <rama>`; reintentar con espera (2, 4, 8, 16 s) solo ante fallos de red.
- **El PR 1 ya se fusionó** (`b7a000c`). El trabajo posterior va como cambios nuevos; **no abrir PR sin que Ángel lo pida.**
- Commits terminan con: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` y `Claude-Session: https://claude.ai/code/session_014TiHE9gcm3uR4ewdCzNYKf`. No poner identificadores de modelo en commits ni en código.
- **No usar** `git reset --hard`, `git clean`, `git checkout -B` (el clasificador de la sesión lo bloqueó como destrucción local). Para avanzar una rama: `git merge --ff-only origin/main`.
- Tests: ver Handoff 2 §5. Comprueba **el código de salida** (`$?`), no solo el resumen; nunca ocultarlo con `| tail`.
- Los documentos del repo **no deben contener nombres de clientes reales** (el control de confirmación local los bloquea).

## 4. Procedimiento exacto al retomar
**Paso A — Sincronizar (5 min).**
`git fetch origin && git status -sb`. Si `main` se movió, `git merge --ff-only origin/main`. Leer los 3 handoffs y `docs/INFORME_ESTADO_2026-10-02.md`.

**Paso B — Preguntar, no suponer.** Pregunta a Ángel qué hilo quiere (lista en §5) y qué respuestas de otros agentes llegaron desde el último handoff (§6).

**Paso C — Por cada respuesta de otro agente:** compárala con lo que pidió, marca VERIFICADO/REPORTADO, busca **discrepancias** (ya hubo: saldo de créditos, rutas de fichero en otro entorno, un enlace de otro canal) y repórtalas.

**Paso D — Mantener la cola de decisiones (§7) visible y no ejecutar lo no decidido.**

**Paso E — Guardar lo nuevo:** cualquier informe que Ángel pegue y valga la pena, a `docs/referencias/` (sin datos privados), commit y push; actualizar el informe de estado.

## 5. Hilos abiertos y qué hacer en cada uno
1. **Investigador YouTube (Astra) — Fase 1A autorizada.** Esperar su informe con la tabla de los 16 caminos (ARREGLADO + test / APLAZADO / NO REPRODUCIDO). Revisar antes de dar OK a la 1B. Alcance 1A: caminos 2, 3, 4, 5, 6, 7, 8, 11, 13, 14, 15. 1B (con OK): 1, 12, 9, 10, 16 y el 4 % cosmético. Reglas: test rojo→verde por cambio, copia extra de `corpus.db`, no tocar duplicados (82 IDs / 87 ficheros) ni los 46 registros no-ok, **sin contactar YouTube** en 1A. **Dato nuevo:** vídeos recientes pueden no tener subtítulos aún → el vigilante necesita plan B (transcribir audio en local o reintentar).
2. **WebLLM.** Rama `auditoria-api-externa` (REPORTADO): arreglado el fallo de `zai/groq/nemotron` y el proveedor `lmstudio`; **sin probar con proveedores reales**. Pendiente: prueba real de UNA pregunta mínima a `lmstudio` vía WebLLM cuando el servidor de LM Studio esté encendido (el apagado de la puerta tras reiniciar es decisión de diseño, no tocar). Después, en Kaizen, usar `KAIZEN_EXPLORACION_MODELO=webllm` y el modelo `lmstudio`.
3. **LM Studio / primera vuelta real de nichos.** Pendiente: encender su servidor local; probar `python -X utf8 herramientas\apuestas.py tanda --ciclos 1` en `KAIZEN-mundo` con `KAIZEN_EXPLORACION_MODELO=local`. **Nunca se ha completado una vuelta con modelo ni búsqueda reales.** Antes, decidir en qué empresa se guardan las apuestas (recomendado: una nueva y limpia).
4. **Carpeta local `KAIZEN` (58 cambios sin guardar).** Plan acordado: copia privada de los 17 ficheros con nombres reales en `D:\backups\kaizen-2026-10-02\` (fuera del repo, con sha256) y commit de los 41 limpios en la rama `trabajo-local-auditoria-e2e`, **sin saltar el control (`CENTINELA_OVERRIDE`) y sin push**. Resultado del plan: **no recibido**. `master` debe seguir en `9c8675f`.
5. **Disco `C:`.** 17,8 GB libres (suficiente). Pendiente decisión de Ángel: borrar `vm_bundles` de Claude Desktop (19,5 GB; con la app cerrada; regenerable según fuentes de usuarios) y cachés (npm, uv, Temp, Playwright). No tocar modelos de LM Studio, `.venv`, `KAIZEN_DATOS`, `.env`.
6. **Vídeo con IA gratis.** Octask: **descartada como fuente gratuita** salvo un último intento opcional de 5 s (saldo 357,758 créditos; prueba caduca ~20 h tras las 12:40 del 2-oct y borra ficheros). Siguiente paso real: probar **Google Flow, Agnes/Pavo y Vibes** con el mismo guion de 10-15 s y leer sus condiciones de uso comercial (ver `docs/referencias/VIDEO_IA_GRATIS_CANDIDATAS_2026-10-02.md`). Consulta pendiente al corpus del Investigador sobre el canal de Alejavi Rivera (solo lectura).
7. **Concepto (Handoff 3).** Siguiente entregable propuesto: **catálogo de capacidades** (qué puede hacer Claude + otras IAs + herramientas alquiladas) con estado y fecha de última prueba. **Sin «adelante» de Ángel, no se escribe.**

## 6. Prompts listos (pegar tal cual en el agente indicado)
**Para Astra (Fase 1A):** ver `docs/handoff/HANDOFF_2_ESTADO_TECNICO_2026-10-02.md` §9 (texto íntegro).
**Para el Claude local de `KAIZEN` (guardar el trabajo):**
```
Opción 2 con copia de seguridad privada. NO uses CENTINELA_OVERRIDE ni saltes ningún control.
1. Copia los 17 ficheros con nombres de clientes (los que marcó el control; incluidos docs/AUDITORIA_E2E_2026-09-12.md y docs/BRAINSTORM_EDIFICIO_KAIZEN.md) a D:\backups\kaizen-2026-10-02\ conservando rutas relativas, fuera de cualquier repositorio. Genera un manifiesto con sha256 y comprueba que coinciden.
2. Solo con la copia verificada: git restore --staged de esos 17 (no los borres ni los reviertas).
3. Commit en la rama trabajo-local-auditoria-e2e solo con los 41 restantes. Si el control vuelve a bloquear, no insistas: dime qué ficheros marca.
4. NO hagas push. master no se toca.
5. Dime: hash, nº de ficheros, ruta y tamaño de la copia, confirmación de que los 17 siguen intactos y de que master sigue en 9c8675f.
```
**Para el Claude local (Alejavi, solo lectura):**
```
Consulta en SOLO LECTURA el corpus del Investigador YouTube. NO ejecutes semanal, video, canal, backfill, embeber ni reindexar (Astra modifica ese código). 1) estado --json: ¿hay canal de Alejavi Rivera? 2) buscar/semantico: "gratis", "sin límites", "4K", "marca de agua", "créditos", Flow, Vids, Agnes, Pavo, Vibes, Kling, Veo, Wan, Qwen. 3) 25 citas «literal» — título, canal, fecha, [mm:ss](enlace al segundo); nada sin enlace. 4) Tabla herramienta | límite | resolución | fecha | enlace, marcada "dato del vídeo, no verificado". Subtítulos automáticos: fallan con nombres y cifras. No resumas vídeos enteros.
```
**Para el Claude con navegador (prueba de vídeo gratis):** mismo guion en Flow, Agnes/Pavo y Vibes; anotar tiempo, créditos, resolución real, marca de agua, formato; leer términos de uso comercial; **no aceptar nada que cueste dinero ni quitar marcas de agua con herramientas de terceros**; marcar NO VERIFICADO lo no abierto; avisar de que sus ficheros viven en su entorno y entregar el informe pegado en el chat.

## 7. Cola de decisiones de Ángel (no ejecutar sin respuesta)
1. ¿Empresa para la búsqueda de nichos: una real existente o una **nueva y limpia**? (recomendado: nueva).
2. `buscar_nichos`: ¿pide tu SÍ (documento de autonomía firmado) o pasa a libre (documento del edificio §5)? Discrepancia entre ambos documentos.
3. Los 17 ficheros con nombres reales: ¿terminar el renombrado (qué nombre en cada sitio)?
4. ¿«Añadir nicho» a mano (recibir informes de fuera)? Propuesto, no construido.
5. ¿Catálogo de capacidades v0? Propuesto, no construido.
6. ¿Borrar `vm_bundles` y cachés?
7. ¿Informe Web3 (solo lectura)? Ofrecido, sin «adelante».
8. ¿Lentes nuevas se quedan o se revierten?
9. Antes del primer envío real de la planta comercial: **consulta legal** (LSSI art. 21 / RGPD) con gestor o abogado.

## 8. Lista de «no hacer»
- No construir motor, skills, catálogo ni vigilantes sin «adelante».
- No saltar el control de nombres reales ni subir la rama `trabajo-local-auditoria-e2e`.
- No fiarse de informes sin artefacto. No dar por probado nada con proveedores reales: **todo lo de WebLLM/LM Studio/ddgs está sin probar en vivo**.
- No quitar marcas de agua, no hacer farmeo con muchas wallets, no automatizar Claude/ChatGPT desde WebLLM (decisión de Ángel).
- No presentar cifras de dinero sin fuente: son SUPUESTO.

## 9. Plantilla de informe (cada vez que termines algo)
1) Qué pediste · 2) Qué hiciste (comandos y salida real) · 3) Artefactos (rutas/hashes) · 4) Resultado de pruebas con **código de salida** · 5) NO VERIFICADO · 6) Decisión que necesitas de Ángel.
