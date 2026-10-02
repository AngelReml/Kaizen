> **Documento de referencia, guardado para no perderlo.** Lo aportó Ángel el 2026-10-02 y lo generó otra IA sobre un proyecto local suyo («Investigador YouTube»).
> Se conserva tal cual, salvo que las rutas con el nombre de usuario de Windows se sustituyeron por `<ESCRITORIO>`.
> **Claude no ha verificado nada de lo que dice**: ni las cifras, ni el estado del sistema, ni las pruebas. Todo es afirmación del informe original.
> No es una orden ni una decisión de Kaizen. Contexto: ver `docs/INFORME_ESTADO_2026-10-02.md`.

---

# Informe técnico para crear el MCP de Investigador YouTube

**Fecha de la auditoría:** 2026-10-02 (Europe/Madrid)  
**Proyecto auditado:** `<ESCRITORIO>\investigador youtube`  
**Objetivo:** proporcionar a una IA implementadora la información necesaria para crear un servidor MCP local que pueda consultar, alimentar y operar el Investigador YouTube sin depender de la interfaz visual del panel.

## 1. Dictamen ejecutivo

El proyecto ya contiene casi toda la lógica de dominio que necesita el MCP. No conviene reescribir la descarga, la búsqueda, la selección de subtítulos ni la reanudación de canales. El MCP debe ser una capa fina y estructurada sobre los módulos Python existentes.

La arquitectura recomendada es:

```text
Cliente de IA
    │ MCP por stdio
    ▼
Servidor MCP local nuevo
    ├── adaptador de consulta ───────► SQLite FTS5 / embeddings / vault
    ├── adaptador de ingesta ────────► scripts/yt.py + scripts/nucleo.py
    ├── adaptador de captura TXT ────► scripts/captura_visual.py
    │                                  scripts/captura_canal_visual.py
    └── gestor persistente de tareas ► datos/mcp-tareas/
```

**Estado del MCP:** no implementado.  
**Estado del sistema base:** operativo para corpus, búsqueda y una captura individual real; la captura real consecutiva de varios vídeos todavía no supera el criterio de aceptación.

El fallo real pendiente es importante: en la prueba con Plan BTC el primer vídeo se guardó correctamente, pero el segundo falló dos veces porque YouTube abrió el panel de transcripción sin mostrar contenido. Por tanto, el MCP no puede declarar un canal completo solo porque la llamada técnica haya acabado sin excepción.

## 2. Estado comprobado

### 2.1 Verificado en ejecución

- Python: `3.10.11`.
- Intérprete usado por el proyecto: `C:\Program Files\Python310\python.exe`.
- Panel activo y escuchando exclusivamente en `127.0.0.1:8765`.
- Proceso que escuchaba durante esta auditoría: PID `19592`.
- API `GET /api/estado` respondió correctamente.
- Corpus actual:
  - 127 vídeos registrados.
  - 81 vídeos con estado `ok`.
  - 6.424 párrafos FTS.
  - 13 canales.
  - 6.424/6.424 párrafos con embedding.
  - 1 título marcado como defectuoso.
- Vault efectivo: `<ESCRITORIO>\investigador youtube\vault`.
- Pruebas automatizadas: **11/11 correctas**.
- Compilación sintáctica correcta de los módulos principales y del servidor del panel.
- El directorio del proyecto **no es un repositorio Git**; no existe `.git` en su raíz.

### 2.2 Dependencias observadas

| Componente | Versión / ubicación | Estado |
|---|---|---|
| Python | 3.10.11 | Verificado |
| `yt-dlp` | 2026.8.19, user site | Verificado en el entorno real |
| `youtube-transcript-api` | 1.2.4, user site | Verificado en el entorno real |
| `mcp` | 1.23.3, user site | Ficheros y metadatos presentes |
| `playwright` usado por captura | 1.63.0 en `libs\` | Verificado |
| `curl-cffi` usado por proyecto | 0.16.0 en `libs\` | Verificado |
| Chrome | rutas estándar de Program Files | Detectado por el código |

El entorno aislado de algunas herramientas puede ocultar el *user site* de Python. El servidor MCP no debe confiar en una instalación global implícita. Debe usar un entorno virtual propio o un lanzador que garantice que `mcp`, `yt-dlp` y `youtube-transcript-api` son importables por el mismo intérprete.

La versión instalada expone `mcp.server.fastmcp.FastMCP` y admite `run(transport='stdio')`. No se debe actualizar el SDK a ciegas durante la implementación.

### 2.3 Prueba real de captura de canal

Canal probado:

```text
Nombre: Plan BTC
Channel ID: UCYP50Ia1diVVE9fwVnqEyqQ
Total público listado: 883
Orden: más reciente → más antiguo
```

Los tres primeros elementos observados fueron:

1. `DURHMgUUvTM` — 2026-10-01.
2. `byqw1A12tso` — 2026-09-29.
3. `6qv3cE7mAiU` — 2026-09-24.

Resultado persistido:

```json
{
  "channel_id": "UCYP50Ia1diVVE9fwVnqEyqQ",
  "total_listado": 883,
  "terminado": false,
  "resumen": {
    "guardados": 1,
    "omitidos": 0,
    "fallos_temporales": 1,
    "total": 883
  }
}
```

Primer vídeo:

- Guardado correctamente.
- 216 líneas de transcripción.
- 34.462 bytes.
- Idioma `es`.
- Ruta:
  `<ESCRITORIO>\investigador youtube\capturas navegador\Plan BTC [UCYP50Ia1diVVE9fwVnqEyqQ]\OCTUBRE El mes que BITCOIN inicia una caída del 15% (será compra) [DURHMgUUvTM].txt`

Segundo vídeo:

```json
{
  "video_id": "byqw1A12tso",
  "estado": "fallo_temporal",
  "intentos": 2,
  "motivo": "YouTube ha abierto la transcripcion, pero no ha mostrado su contenido."
}
```

También se verificó que una parada solicitada espera a que finalice el vídeo actual, conserva el TXT y que, al reanudar, no repite el vídeo ya guardado.

## 3. Componentes y responsabilidades actuales

### 3.1 Núcleo y almacenamiento

Archivo: `scripts\nucleo.py`

Responsabilidades principales:

- raíz del proyecto y rutas de datos;
- lectura robusta de `canales.yaml`;
- resolución de canal desde `UC...`, URL o `@handle`;
- listado de vídeos;
- creación y acceso a SQLite;
- búsqueda FTS5;
- generación de enlaces de YouTube con segundo exacto;
- escritura protegida del vault.

Constantes relevantes:

```python
RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
TRANSCRIPCIONES = RAIZ / "transcripciones"
BD = DATOS / "corpus.db"
```

Funciones públicas que el adaptador MCP puede reutilizar:

```python
cargar_config() -> dict
conectar() -> sqlite3.Connection
crear_esquema(con) -> None
resolver_canal(entrada: str) -> tuple[str | None, str | None]
videos_historico_ordenado(channel_id: str, limite=None) -> list[dict]
listar_videos(con, limite=50) -> list[dict]
buscar(con, consulta, limite=30, canal=None) -> list[dict]
afinar_segundo(con, video_id, idioma, inicio_parrafo, termino) -> float
hhmmss(segundos) -> str
enlace_minuto(video_id, segundos) -> str
ruta_vault(conf) -> Path
```

`videos_historico_ordenado()` transforma el channel ID `UC...` en la playlist automática de subidas `UU...`. Esta playlist reúne vídeos, shorts y directos en una única secuencia global. Si no está disponible, usa como alternativa el listado histórico por pestañas.

### 3.2 Ingesta del corpus

Archivo: `scripts\yt.py`

Punto de entrada principal para un vídeo:

```python
anadir_video(
    bruto: str,
    conf: dict,
    forzar: bool = False,
    titulo: str | None = None,
) -> dict
```

Contrato observado en éxito:

```json
{
  "ok": true,
  "video_id": "...",
  "titulo": "...",
  "canal": "...",
  "parrafos": 123,
  "idiomas": ["es"],
  "caracteres": 45678,
  "temas": [],
  "nota": "ruta del markdown",
  "log": [],
  "embeddings": {}
}
```

Contrato de error:

```json
{
  "ok": false,
  "motivo": "explicación",
  "log": [],
  "video_id": "opcional"
}
```

Esta ingesta descarga las pistas de subtítulos permitidas, actualiza transcripciones fuente, SQLite/FTS, vault y, cuando es posible, embeddings. Es diferente de la captura visual TXT.

### 3.3 Búsqueda exacta

`nucleo.buscar()` devuelve:

```json
{
  "video_id": "...",
  "idioma": "es",
  "inicio": 125.4,
  "cita": "texto con **coincidencias**",
  "titulo": "...",
  "publicado": "YYYY-MM-DD",
  "canal": "..."
}
```

La función no añade por sí sola el enlace final. El adaptador MCP debe completar cada resultado así:

```python
segundo = N.afinar_segundo(
    con,
    fila["video_id"],
    fila["idioma"],
    fila["inicio"],
    consulta,
)
fila["segundo"] = segundo
fila["minuto"] = N.hhmmss(segundo)
fila["enlace"] = N.enlace_minuto(fila["video_id"], segundo)
```

Esto es obligatorio para que una IA pueda citar una afirmación y abrir la fuente en el segundo exacto.

### 3.4 Búsqueda semántica

Archivo: `scripts\embeber.py`

```python
buscar_semantico(con, conf, consulta, top=10) -> dict
```

Respuesta de éxito:

```json
{
  "ok": true,
  "modelo": "...",
  "resultados": [
    {
      "video_id": "...",
      "idioma": "es",
      "titulo": "...",
      "canal": "...",
      "inicio": 125.4,
      "minuto": "2:05",
      "enlace": "https://youtu.be/...?t=125",
      "cita": "...",
      "similitud": 0.8123
    }
  ]
}
```

Depende de LM Studio y de un modelo de embeddings local. Si no está disponible, devuelve `ok: false`, `motivo` y una lista vacía. El MCP debe propagar este fallo como capacidad no disponible, no inventar resultados ni convertirlo en una búsqueda exacta silenciosa.

### 3.5 Captura visual de un vídeo

Archivo: `scripts\captura_visual.py`

Funciones reutilizables:

```python
extraer_video_id(valor: str) -> str
capturar_lista(videos, destino, perfil=None, headless=False,
               progreso_cb=None, resultado_cb=None, detener_cb=None) -> dict
capturar(video, destino=None, perfil=None, headless=False,
         progreso_cb=None) -> dict
```

Comportamiento:

- acepta ID de 11 caracteres y URLs `watch`, `youtu.be`, `shorts`, `embed` y `live`;
- usa una sesión persistente de Chrome en `datos\perfil-navegador`;
- abre el vídeo y valida que el reproductor corresponde al ID pedido;
- prefiere subtítulos españoles directos;
- si no existen, usa la traducción de YouTube a español cuando esté disponible;
- abre el panel de transcripción y extrae los segmentos con tiempo;
- reutiliza una sola ventana de Chrome durante un lote;
- serializa el acceso mediante `_BLOQUEO_NAVEGADOR`.

Solo debe existir un trabajo de captura visual activo. El MCP debe devolver un error estructurado `BUSY` ante una segunda solicitud, en vez de dejar otra llamada bloqueada indefinidamente esperando el `Lock`.

### 3.6 Captura reanudable de canal

Archivo: `scripts\captura_canal_visual.py`

```python
capturar_canal(
    entrada: str,
    limite: int | None = None,
    destino_raiz=None,
    estados_dir=None,
    perfil=None,
    headless: bool = False,
    progreso_cb=None,
    detener_cb=None,
    resolver=None,
    listar=None,
    capturador=None,
) -> dict
```

Propiedades:

- recorre el canal de más reciente a más antiguo;
- guarda cada resultado inmediatamente;
- escribe el estado de manera atómica usando `.json.tmp` y `os.replace()`;
- al reiniciar, valida registros previos;
- si el equipo se apagó después de escribir el TXT pero antes del JSON, recupera el avance leyendo la cabecera del TXT;
- trata `guardado` y `omitido` como estados terminales;
- trata `fallo_temporal` como reintentable;
- comprueba la parada entre vídeos, nunca a mitad de un fichero.

Estado persistente:

```text
datos\capturas-canales\<channel_id>.json
```

Salida por canal:

```text
capturas navegador\<nombre seguro> [<channel_id>]\*.txt
```

Resultado actual:

```json
{
  "ok": true,
  "channel_id": "UC...",
  "canal": "...",
  "carpeta": "...",
  "estado_ruta": "...json",
  "total": 883,
  "guardados": 1,
  "omitidos": 0,
  "fallos_temporales": 1,
  "detenido": false,
  "terminado": false
}
```

`ok: true` aquí significa que el recorrido terminó de forma controlada, **no** que el canal esté completo. El MCP debe normalizar esta ambigüedad.

### 3.7 Validación y formato del TXT

Archivo: `scripts\guardar_exportacion_navegador.py`

Formato canónico:

```text
YouTube transcript
Video ID: DURHMgUUvTM
Language: es
Captions: auto-generated

[0:00] Primera línea...
[0:09] Segunda línea...
[1:02:05] Línea en un vídeo largo...
```

La validación exige:

- UTF-8 o UTF-8 con BOM;
- cabecera `Video ID` igual al vídeo solicitado;
- `Language: es` o un código `es-*`;
- al menos una línea con marca de tiempo.

Si ya existe un fichero con los mismos bytes, devuelve `ya_existia: true`. Si existe un fichero diferente con el mismo nombre, crea `(2)`, `(3)`, etc.; no sobrescribe una captura distinta.

### 3.8 Separación que no se debe romper

Hay dos almacenes con finalidades diferentes:

| Subsistema | Salida | Consultable en FTS/embeddings |
|---|---|---|
| Ingesta de corpus | `transcripciones\`, `datos\corpus.db`, `vault\` | Sí |
| Captura visual | `capturas navegador\*.txt` | No |

Capturar un TXT desde Chrome **no añade automáticamente** ese contenido al corpus SQLite ni al vault. El MCP debe decir qué operación realizó y no mezclar ambas.

## 4. Modelo de datos

### 4.1 SQLite principal

Base: `datos\corpus.db`

Tablas relevantes:

```sql
CREATE TABLE canales (
    id TEXT PRIMARY KEY,
    nombre TEXT,
    idioma TEXT,
    url TEXT
);

CREATE TABLE videos (
    id TEXT PRIMARY KEY,
    canal_id TEXT,
    titulo TEXT,
    publicado TEXT,
    duracion INTEGER,
    estado TEXT,
    motivo TEXT,
    n_fragmentos INTEGER,
    caracteres INTEGER,
    idiomas TEXT,
    temas TEXT,
    enriquecido INTEGER DEFAULT 0,
    visto TEXT
);

CREATE VIRTUAL TABLE fts USING fts5(
    video_id UNINDEXED,
    idioma UNINDEXED,
    inicio UNINDEXED,
    texto,
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TABLE parrafos (
    video_id TEXT,
    idioma TEXT,
    inicio REAL,
    texto TEXT,
    mapa TEXT,
    PRIMARY KEY (video_id, idioma, inicio)
);

CREATE TABLE embeddings (
    video_id TEXT,
    idioma TEXT,
    inicio REAL,
    texto TEXT,
    vector BLOB,
    dims INTEGER,
    modelo TEXT,
    creado TEXT,
    PRIMARY KEY (video_id, idioma, inicio)
);
```

El vault es la fuente legible y SQLite es un índice regenerable. El MCP debe usar las funciones del dominio en lugar de ejecutar SQL de escritura ad hoc.

### 4.2 Transcripciones fuente

Ruta:

```text
transcripciones\<primer carácter del video_id>\<video_id>.json
```

Estructura observada:

```json
{
  "video_id": "...",
  "pistas": {
    "es": [
      {"inicio": 0.36, "texto": "..."}
    ]
  },
  "obtenido": "ISO-8601",
  "titulo": "...",
  "canal_id": "UC...",
  "canal_nombre": "...",
  "publicado": "YYYY-MM-DD",
  "duracion": 978
}
```

## 5. API HTTP existente

El panel usa `ThreadingHTTPServer` de la biblioteca estándar. No usa Flask ni FastAPI. Está enlazado a `127.0.0.1` y no tiene autenticación. Añade `Access-Control-Allow-Origin: *` a las respuestas JSON.

### GET

| Ruta | Función |
|---|---|
| `/` | panel HTML |
| `/api/estado` | recuentos del corpus |
| `/api/lmstudio` | disponibilidad del embedding local |
| `/api/buscar?q=...` | búsqueda exacta, pero sin enlace enriquecido |
| `/api/semantico?q=...` | búsqueda semántica |
| `/api/videos` | últimos 50 vídeos |
| `/api/tarea/<id>` | estado de tarea en memoria |
| `/capturas-canal/<carpeta>` | listado HTML de TXT |
| `/capturas/<ruta.txt>` | lectura del TXT |
| `/api/memoria/estado` | estado de la memoria externa opcional |
| `/api/memoria/buscar?q=...` | búsqueda en memoria externa opcional |

### POST JSON

| Ruta | Cuerpo | Función |
|---|---|---|
| `/api/tarea/video` | `{texto, forzar?, titulo?}` | ingesta de un vídeo al corpus |
| `/api/tarea/canal` | `{texto, limite?}` | ingesta de canal al corpus |
| `/api/tarea/captura-browser` | `{texto}` | autodetecta vídeo o canal y captura TXT |
| `/api/tarea/<id>/detener` | `{}` | parada segura |
| `/api/video` | `{texto, forzar?, titulo?}` | compatibilidad síncrona |
| `/api/embeber` | `{limite?}` | calcula embeddings |
| `/api/tarea/reparar_titulos` | `{}` | repara títulos |
| `/api/video/borrar` | `{video_id}` | borrado de DB/FTS/embeddings |
| `/api/memoria/actualizar` | `{limite?}` | actualiza memoria externa |

El gestor de tareas HTTP actual es un diccionario en memoria:

```json
{
  "id": "12 caracteres",
  "tipo": "...",
  "estado": "en_curso|hecho",
  "mensaje": "...",
  "hechos": 0,
  "total": 0,
  "ok": null,
  "resultado": null,
  "creado": 0.0,
  "latido": 0.0,
  "detener_solicitado": false
}
```

Limitaciones del API como base directa de un MCP:

1. Las tareas desaparecen al reiniciar el panel.
2. Las tareas finalizadas se purgan después de una hora.
3. `estado: hecho` no distingue éxito completo, parcial, pausa o fallo.
4. `ok: true` en captura de canal no implica `terminado: true`.
5. La búsqueda exacta HTTP no añade el enlace al segundo refinado.
6. La captura y el corpus son operaciones diferentes bajo nombres parecidos.
7. No hay autenticación; solo es aceptable porque escucha en localhost.

El MCP definitivo debe importar la lógica Python directamente o extraer los servicios compartidos. Envolver únicamente este HTTP conservaría sus ambigüedades y su estado efímero.

## 6. Diseño requerido del MCP

### 6.1 Transporte y proceso

- Transporte preferido: `stdio`.
- Un proceso MCP local por cliente.
- Nombre recomendado: `investigador-youtube`.
- Carpeta nueva, aislada y eliminable: `mcp-investigador\`.
- No mover ni renombrar los módulos actuales en la primera versión.
- Añadir `scripts\` al `sys.path` de manera explícita y validada.
- Resolver siempre la raíz desde la ubicación del servidor, no desde el directorio de trabajo del cliente.

Esqueleto compatible con el SDK presente:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "investigador-youtube",
    instructions="Consulta y opera el corpus local de YouTube con citas verificables.",
)

@mcp.tool()
def investigador_estado() -> dict:
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

No imprimir logs normales por `stdout`, porque corromperían el protocolo MCP. Los logs deben ir a `stderr` o a un fichero.

### 6.2 Gestor de tareas nuevo

Las operaciones largas no deben bloquear una llamada MCP durante horas. Deben devolver un `task_id` inmediatamente.

Persistencia recomendada:

```text
datos\mcp-tareas\<task_id>.json
```

Escritura atómica obligatoria: fichero temporal en la misma carpeta y `os.replace()`.

Contrato recomendado:

```json
{
  "schema_version": 1,
  "task_id": "uuid",
  "kind": "capture_channel_txt",
  "status": "queued|running|cancel_requested|succeeded|partial|cancelled|failed",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC",
  "heartbeat_at": "ISO-8601 UTC",
  "input": {},
  "progress": {
    "completed": 1,
    "total": 883,
    "saved": 1,
    "skipped": 0,
    "retryable_failures": 1
  },
  "transport_ok": true,
  "task_ok": true,
  "complete": false,
  "partial": true,
  "message": "...",
  "result": {},
  "error": null
}
```

Reglas:

```text
complete = terminado == true AND fallos_temporales == 0
partial  = hay algún resultado útil AND complete == false
failed   = no hay resultado útil y la operación no puede continuar
cancelled = parada segura confirmada entre vídeos
```

Al arrancar, una tarea con `status=running` y sin proceso vivo debe convertirse en `partial` o `failed` con código `INTERRUPTED`. Para captura de canal, el detalle recuperable sigue estando en `datos\capturas-canales\<channel_id>.json` y los TXT.

### 6.3 Herramientas MCP mínimas

#### `investigador_estado`

Entrada: ninguna.

Salida:

```json
{
  "ok": true,
  "corpus": {
    "videos": 127,
    "transcritos": 81,
    "parrafos": 6424,
    "canales": 13,
    "embebidos": 6424,
    "total_parrafos_para_embeber": 6424,
    "titulos_rotos": 1
  },
  "paths": {
    "root": "...",
    "vault": "...",
    "captures": "..."
  },
  "capabilities": {
    "exact_search": true,
    "semantic_search": true,
    "visual_capture": true
  }
}
```

#### `buscar_corpus`

Entrada:

```json
{
  "consulta": "bitcoin corrección",
  "limite": 15,
  "canal": null
}
```

Validación: `consulta` no vacía, `limite` entre 1 y 50.

Cada resultado debe incluir `video_id`, `idioma`, `titulo`, `canal`, `publicado`, `segundo`, `minuto`, `enlace` y `cita`. Nunca devolver una cita sin su enlace verificable.

#### `buscar_semantico`

Entrada: `consulta`, `limite` de 1 a 30.

Debe propagar `modelo`, `similitud` y el enlace exacto. Si LM Studio está apagado, usar un error de capacidad `SEMANTIC_BACKEND_UNAVAILABLE`; no fingir éxito.

#### `listar_videos`

Entrada: `limite` de 1 a 200.

Salida por elemento: `id`, `titulo`, `publicado`, `estado`, `n_fragmentos`, `idiomas`, `canal`.

#### `iniciar_ingesta_video`

Entrada:

```json
{
  "url_o_id": "https://youtu.be/...",
  "forzar": false,
  "titulo": null
}
```

Salida inmediata: `task_id`, `status: queued`.

#### `iniciar_ingesta_canal`

Entrada: `canal`, `limite` opcional. Esta operación alimenta corpus/vault; no crea los TXT visuales.

#### `iniciar_captura_video_txt`

Entrada: `url_o_id`.

Salida inmediata: tarea. Al finalizar debe incluir `video_id`, `idioma`, `lineas_transcripcion`, `bytes`, `ruta`, `ya_existia` y un URI de lectura MCP si se implementa.

#### `iniciar_captura_canal_txt`

Entrada:

```json
{
  "canal": "https://www.youtube.com/@planbtc",
  "limite": null
}
```

Debe recorrer de nuevo a antiguo, reanudar automáticamente y no repetir estados terminales válidos.

#### `consultar_tarea`

Entrada: `task_id`.

Devuelve el registro persistente completo, sin incluir transcripciones enteras.

#### `detener_tarea`

Entrada: `task_id`.

Solo solicita parada. Debe responder `cancel_requested`. La confirmación final llega al consultar la tarea después de que el vídeo actual quede validado y guardado.

#### `estado_captura_canal`

Entrada: `channel_id`, URL o `@handle`.

Debe leer y normalizar `datos\capturas-canales\<channel_id>.json`, contar pendientes y devolver una muestra acotada de fallos temporales.

#### `listar_capturas`

Entrada: canal opcional, `limite`, cursor opcional.

Devuelve solo metadatos: `video_id`, título, idioma, líneas, bytes, ruta relativa, fecha y estado. No devolver el texto completo.

#### `leer_captura`

Entrada:

```json
{
  "video_id": "DURHMgUUvTM",
  "desde_linea": 0,
  "max_lineas": 200
}
```

Salida paginada:

```json
{
  "video_id": "DURHMgUUvTM",
  "desde_linea": 0,
  "lineas_devueltas": 200,
  "siguiente_linea": 200,
  "fin": false,
  "texto": "..."
}
```

Límite obligatorio para no inundar el contexto de la IA. Como alternativa, exponer una plantilla de recurso `investigador://capturas/{video_id}` y mantener la lectura por fragmentos como herramienta.

### 6.4 Operaciones que no deben exponerse inicialmente

No exponer `borrar_video` en la primera versión. La función actual borra DB, FTS y embeddings, pero no borra la transcripción fuente ni la nota del vault. Si se añade más adelante, debe exigir una confirmación explícita y describir exactamente este alcance parcial.

Tampoco exponer:

- ejecución arbitraria de comandos;
- rutas arbitrarias del disco;
- lectura de cookies o exportación del perfil de Chrome;
- modificación directa de SQLite;
- edición libre de `canales.yaml`.

## 7. Contrato de errores

Todas las herramientas deben devolver errores estructurados con un código estable:

```json
{
  "ok": false,
  "error": {
    "code": "TRANSCRIPT_PANEL_EMPTY",
    "message": "YouTube abrió la transcripción, pero no mostró contenido.",
    "retryable": true,
    "details": {
      "video_id": "byqw1A12tso"
    }
  }
}
```

Códigos mínimos:

| Código | Reintentable | Significado |
|---|---:|---|
| `INVALID_INPUT` | No | URL, ID o parámetros inválidos |
| `CHANNEL_NOT_FOUND` | No/quizá | no se pudo resolver el canal |
| `VIDEO_NOT_FOUND` | No/quizá | vídeo inexistente o inaccesible |
| `NO_TRANSCRIPT` | No | YouTube no ofrece transcripción |
| `NO_SPANISH_TRACK` | No | no hay pista ni traducción al español |
| `TRANSCRIPT_PANEL_EMPTY` | Sí | panel abierto sin segmentos |
| `RATE_LIMITED` | Sí | limitación temporal de YouTube |
| `BROWSER_PROFILE_BUSY` | Sí | perfil usado por otro Chrome |
| `CAPTURE_BUSY` | Sí | ya hay una captura visual activa |
| `SEMANTIC_BACKEND_UNAVAILABLE` | Sí | LM Studio/modelo no disponible |
| `TASK_NOT_FOUND` | No | tarea desconocida o eliminada |
| `INTERRUPTED` | Sí | proceso terminado antes de completar |
| `INVALID_EXPORT` | Depende | TXT no demuestra ID/idioma/contenido |
| `INTERNAL_ERROR` | Depende | error no clasificado |

No usar excepciones como contrato público. Capturarlas, registrarlas sin secretos y convertirlas a esta forma.

## 8. Concurrencia, idempotencia y reanudación

1. Permitir varias búsquedas simultáneas con conexiones SQLite independientes y cortas.
2. No compartir una conexión SQLite entre hilos.
3. Serializar todas las capturas visuales con un semáforo no bloqueante de capacidad 1.
4. Permitir una sola ingesta de escritura al corpus a la vez, o implementar una cola explícita.
5. Un `task_id` debe identificar un intento concreto; la reanudación de canal se basa en su `channel_id` y en su estado persistente.
6. No repetir un TXT validado.
7. No convertir `fallo_temporal` en `omitido` por número de reintentos sin una política explícita.
8. Guardar avance después de cada vídeo.
9. En una parada, terminar y validar el vídeo actual antes de marcar `cancelled`.
10. Si el proceso muere, reconstruir el estado desde JSON y TXT en el siguiente arranque.

## 9. Seguridad

- Preferir MCP por `stdio`: no abre ningún puerto.
- Si se ofrece `streamable-http`, enlazar solo a `127.0.0.1` y exigir un token aleatorio.
- No reutilizar el CORS `*` del panel para el MCP.
- Resolver rutas y comprobar contención antes de leer ficheros.
- Permitir lectura solo bajo:
  - `capturas navegador\`;
  - `vault\` si se crea una herramienta específica;
  - `datos\capturas-canales\`;
  - `datos\mcp-tareas\`.
- Rechazar `..`, rutas UNC y rutas absolutas suministradas por el cliente.
- No devolver cookies, tokens, cabeceras sensibles ni contenido del perfil del navegador.
- No aceptar comandos de shell ni nombres de módulo arbitrarios.
- Limitar tamaño de entrada, número de resultados y tamaño de salida.
- Registrar operación, duración, código final y task ID; no registrar la transcripción completa por defecto.

## 10. Pruebas exigidas al MCP

### 10.1 Unitarias

- validación de todos los esquemas de entrada;
- enriquecimiento de búsqueda exacta con segundo, minuto y enlace;
- límite de resultados y lectura paginada;
- contención segura de rutas;
- conversión de excepciones a códigos estables;
- estados de tarea y transiciones válidas;
- persistencia atómica;
- recuperación de una tarea interrumpida;
- exclusión mutua de captura visual;
- `complete` falso cuando existe un fallo temporal;
- parada segura;
- corrupción o ausencia del JSON de progreso;
- recuperación desde un TXT válido;
- rechazo de un TXT con otro ID o idioma no español.

### 10.2 Integración con dobles de prueba

- canal de tres vídeos: guardar primero, fallar temporalmente segundo, guardar tercero;
- reanudar: omitir primero y tercero, reintentar solo segundo;
- parada después del primer vídeo;
- reinicio del servidor entre primer y segundo vídeo;
- LM Studio disponible/no disponible;
- YouTube devuelve 429;
- perfil de Chrome ocupado.

### 10.3 Aceptación real obligatoria

Antes de afirmar que el MCP está terminado:

1. Capturar dos vídeos reales consecutivos en una misma sesión.
2. Capturar un lote real limitado a tres vídeos.
3. Detener después del primer vídeo y verificar el TXT en disco.
4. Reiniciar el MCP.
5. Reanudar y comprobar que empieza en el segundo pendiente.
6. Verificar un vídeo con pista española directa.
7. Verificar otro vídeo que necesite traducción a español.
8. Probar un vídeo sin subtítulos.
9. Probar un vídeo privado, eliminado o restringido.
10. Comprobar que ningún resultado parcial se presenta como completo.
11. Consultar el corpus y abrir al menos un enlace en el segundo exacto.
12. Ejecutar las 11 pruebas actuales más las pruebas nuevas del MCP.

El sistema actual no supera todavía el punto 1 debido al fallo real del segundo vídeo de Plan BTC.

## 11. Plan de implementación recomendado

### Fase A — adaptador de solo lectura

- Crear carpeta `mcp-investigador\`.
- Crear entorno reproducible.
- Implementar `investigador_estado`, `buscar_corpus`, `buscar_semantico` y `listar_videos`.
- Añadir pruebas de contratos, enlaces exactos y límites.

### Fase B — lectura segura de capturas

- Implementar `listar_capturas`, `leer_captura` y `estado_captura_canal`.
- Añadir paginación y contención de rutas.

### Fase C — tareas persistentes

- Extraer o crear un gestor compartido de tareas persistentes.
- Implementar `consultar_tarea` y `detener_tarea`.
- Recuperar tareas interrumpidas al arrancar.

### Fase D — escritura

- Implementar ingesta de vídeo/canal.
- Implementar captura TXT de vídeo/canal.
- Añadir exclusión mutua no bloqueante y estados normalizados.

### Fase E — aceptación y documentación

- Resolver el fallo de navegación entre vídeos.
- Ejecutar la matriz real de aceptación.
- Actualizar `LEEME.md`.
- Actualizar `skill\SKILL.md` y `skill\references\captura-navegador.md`.
- Sincronizar la copia instalada del skill.
- Documentar la configuración del cliente MCP y el procedimiento de desinstalación.

## 12. Definición de terminado

El MCP solo puede declararse terminado si:

- arranca por `stdio` sin contaminar stdout;
- el cliente de IA descubre todas las herramientas previstas;
- la búsqueda exacta siempre devuelve cita y enlace con segundo;
- las salidas grandes están paginadas;
- una captura larga devuelve task ID inmediatamente;
- el estado de tarea sobrevive a un reinicio;
- la parada segura conserva el vídeo actual;
- reanudar no repite TXT válidos;
- dos vídeos reales consecutivos se capturan correctamente;
- un fallo temporal nunca produce `complete: true`;
- no existe acceso a rutas arbitrarias ni ejecución de comandos;
- todas las pruebas automatizadas son correctas;
- la documentación describe el comportamiento realmente comprobado.

## 13. Pendientes y elementos no verificados

- **No verificado:** canal completo de principio a fin.
- **No verificado:** dos capturas reales consecutivas sin intervención.
- **No verificado:** recuperación del gestor MCP tras reinicio, porque el MCP aún no existe.
- **No verificado:** compatibilidad con un cliente MCP concreto.
- **No verificado:** vídeos con autenticación, restricción de edad o región.
- **No verificado:** traducción a español en una aceptación real de lote.
- **No verificado:** comportamiento prolongado ante 429 o cambios del DOM de YouTube.
- **Pendiente:** documentación principal y skill todavía describen principalmente la captura individual.
- **Pendiente:** convertir las tareas efímeras del panel en un servicio compartido o crear un gestor persistente separado.
- **Pendiente:** resolver el panel de transcripción vacío al navegar al segundo vídeo.

## 14. Instrucción lista para la IA implementadora

```text
Implementa un servidor MCP local para el proyecto
<ESCRITORIO>\investigador youtube usando este informe como contrato.

No reescribas la lógica de dominio existente. Reutiliza los módulos de scripts,
mantén separadas la ingesta del corpus y la captura visual TXT, y crea el MCP en
una carpeta nueva y eliminable llamada mcp-investigador.

Empieza por herramientas de solo lectura. Después añade un gestor persistente de
tareas para las operaciones largas. Usa stdio como transporte, no escribas logs
en stdout, no expongas comandos ni rutas arbitrarias y no incluyas borrado en la
primera versión.

Cada resultado de búsqueda debe contener cita literal, vídeo, minuto y enlace al
segundo exacto. Cada captura de canal debe distinguir transport_ok, task_ok,
complete y partial. Nunca interpretes ok=true como canal terminado si
terminado=false o existen fallos_temporales.

Antes de declarar terminado el trabajo, ejecuta las 11 pruebas actuales, añade
las pruebas MCP descritas en este informe y supera la aceptación real de dos
vídeos consecutivos, parada segura y reanudación tras reinicio. Si una prueba no
se puede ejecutar, déjala marcada como NO VERIFICADA; no la des por buena.
```
