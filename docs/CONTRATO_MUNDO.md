# Contrato del Mundo (vista isometrica)

Implementacion: `panel_mando/mundo.py` (registrado desde `panel_mando/app.py`).
Tests: `tests/test_mundo_api.py`. Mismo origen y mismas guardas que el resto del
panel: el juego es una PROYECCION del sustrato; no hay almacen propio y las dos
rutas de datos son de solo lectura.

## Que se reutiliza (no se duplica)

Para actuar y para lo que ya existe, el juego llama a los endpoints del panel:
`GET /api/csrf`, `POST /cmd/aprobar|denegar|deshacer|parar_todo|reanudar`,
`GET /api/tarjetas/{empresa}`, `GET /api/sello/{empresa}`,
`GET /api/dinero/{empresa}`, `GET /latido`. Los `POST` exigen CSRF como siempre.

## Endpoints nuevos

Todos con la auth del panel (cookie de sesion o cabecera `X-Token`). `empresa`
se valida como en el resto del panel (identificador ASCII; si no, **400**);
vacia = primera empresa conocida.

### `GET /mundo`
Devuelve `mundo/index.html` leido de disco en cada peticion (sin cache de
proceso), con `Cache-Control: no-store`. Sin sesion: redirect **303 a /login**.
Si el fichero no existe: **404** con mensaje. Es la unica respuesta HTML; `empresa`
se valida pero nunca se interpola.

### `GET /api/mundo/estado?empresa=X`
Foto completa, JSON, **sin efectos secundarios**: no da de alta directores (a
diferencia de `/api/colmena/agentes`) y no crea tablas `colmena_*`; si no
existen, todos los cubos salen `alta:false`. Campos:

- `empresa`, `empresas[]`, `ahora` (ISO8601 Z), `parado` (PARAR TODO activo).
- `tenant.estado`: `activo|pausado|baja|desconocido` (registro de tenants; si
  falla, `desconocido`).
- `cubos[]`: uno por manifest instalado, en el orden de `CUBOS_ORDEN` de
  Colmena y luego los no listados por nombre. Cada uno: `cubo`, `nombre`
  (nombre de Colmena), `mision`, `autonomia`, `irreversibles[]`, `nota_estado`,
  `alta`, `uid`/`role_id`/`ts_alta` (null si no hay alta), `salud`
  `{estado, detalle, eventos_24h}` (misma funcion que Colmena; si no se puede
  medir, `SIN DATOS`), `ultimo` `{texto, ts}` del chat individual o null.
- `dinero`: misma funcion que `/api/dinero/{empresa}` (`frase`, `gasto_eur`,
  `tope_eur`, `sin_atribuir_eur`, `modo_ahorro`).
- `tarjetas`: `pendientes` (numero; cola en PENDIENTE) y `mechas[]`: las
  mechas encendidas de esa empresa, cada una `{aprobacion, dispara (ISO8601 con
  zona, tal cual lo da Mechas.armar), accion, cubo}` (texto y cubo del nodo de
  la cola). El detalle de las pendientes se pide a `/api/tarjetas/{empresa}`.
- `sello`: `{integra, pasos, mensaje}` de la verificacion de la bitacora.
- `cursores`: `{rue, bus}` para empalmar con el rio (ver abajo).
- `recientes[]`: hasta 40 eventos unificados, ts ascendente.

### `GET /api/mundo/rio?empresa=X&desde_rue=N&desde_bus=M&ciclos=K`
SSE (`text/event-stream`) con el mismo esqueleto que `/rio/{empresa}`: cada
ciclo emite los eventos nuevos y una linea `: latido`; ademas el pulso quema las
mechas vencidas. `ciclos=0` = infinito; `K>0` solo para tests/curl.

Evento unificado (`data:` en una sola linea de JSON; `id:` es `canal:id`):

```
{"canal":"rue"|"bus","id":<int>,"tipo":"...","cubo":"..."|null,
 "frase":"...","ts":"...","aprobacion":"<id de tarjeta>"|null}
```

- **Canal `rue`**: bitacora de la empresa; `id` = numero `n` de la cadena;
  `frase` = el mismo render que `/rio`. `cubo` por prefijo del tipo
  (comercial, brand, finanzas, marketing, inteligencia; `operacion`->`ops`,
  `cumplimiento`->`legal`; `plataforma`->null); si el payload trae un `cubo`
  conocido, gana. `aprobacion` = `payload.aprobacion_ref` en los
  `plataforma.aprobacion.*`.
- **Canal `bus`**: tabla `bus_eventos` del sustrato; `id` = id de fila; `cubo`
  = segmento 2 del topic (`colmena` -> null); `frase` generica derivada del
  topic (`Marca: revision emitida`). Solo se emiten eventos cuyo payload no
  tenga `empresa` (globales) o coincida con la pedida; del payload no sale nada.

## Cursores
`desde_rue` y `desde_bus` son independientes; `-1` (defecto) = desde el
principio; se devuelven solo eventos con id **estrictamente mayor**. Tope de 200
eventos por ciclo y canal (el siguiente ciclo continua). Empalme sin huecos ni
repeticiones: leer `estado`, y abrir el rio con `desde_rue=cursores.rue` (la cadena RUE empieza en `n=0`; un tenant vacio devuelve `-1`) y
`desde_bus=cursores.bus`. El cursor del bus es global (ids de toda la tabla):
los eventos de otros tenants avanzan el cursor pero nunca se emiten.

## Que es real y que no
- Real: todo sale de primitivas existentes (bitacora, bus, cola de
  aprobaciones, ledger, altas de Colmena, manifests). Nada se simula ni se
  rellena: sin dato, `SIN DATOS` / `null` / `alta:false`.
- Las frases del bus son genericas (no hay renderers por topic) y sin tildes.
- Unico efecto en lectura: si faltan las tablas vacias de infraestructura del
  bus o del coste se instalan (para que la salud sea medible). Nunca datos.
- `eventos_24h` y `salud` son los de Colmena; el cubo `legal` cuenta tambien
  la bitacora (RUE) segun su manifest.

## Probarlo con curl
Sin token (local): quitar la cabecera. Con token, `-H "X-Token: $KAIZEN_TOKEN"`.

```
curl -s "http://127.0.0.1:8600/api/mundo/estado?empresa=laboratorio"
curl -sN "http://127.0.0.1:8600/api/mundo/rio?empresa=laboratorio&ciclos=1"
curl -si "http://127.0.0.1:8600/mundo"        # 200 + no-store (o 404 sin fichero)
```
