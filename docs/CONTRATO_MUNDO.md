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
  `rendimiento` (ver «Rendimiento y grados»). Solo el cubo `comercial` trae ademas `pipeline`: `{leads:{COLD, CONTACTADO, CONVERSACION, COMPROMETIDO, PEDIDO, CUSTOMER, DORMIDO, DESCARTADO, EXCLUIDO}, pedidos:{atribuidos, pendientes_validacion}}`. Solo numeros: ningun dato de personas. Solo el cubo `marketing` trae `marketing`: `{campanas:{BORRADOR..CANCELADA}, contenidos:{GENERADO, VALIDADO_POR_BRAND, RECHAZADO, APROBADO, LANZADO, ARCHIVADO}, gasto:[{estado, pct}] (activas y pausadas, hasta 8; pct = gasto reportado / presupuesto), kill_switch_pct}`: sin nombres de campana ni textos.
- `dinero`: misma funcion que `/api/dinero/{empresa}` (`frase`, `gasto_eur`,
  `tope_eur`, `sin_atribuir_eur`, `modo_ahorro`).
- `tarjetas`: `pendientes` (numero; cola en PENDIENTE) y `mechas[]`: las
  mechas encendidas de esa empresa, cada una `{aprobacion, dispara (ISO8601 con
  zona, tal cual lo da Mechas.armar), accion, cubo}` (texto y cubo del nodo de
  la cola). El detalle de las pendientes se pide a `/api/tarjetas/{empresa}`.
- `sello`: `{integra, pasos, mensaje}` de la verificacion de la bitacora. La verificacion es completa
  en cada foto: un sello roto se ve al momento.
- `rrhh`: `{mapa, propuestas[]}`. Sale de las funciones puras del cubo RRHH
  (`mapa_desde` y `propuestas_desde` en `panel_mando/herramientas/rrhh.py`) sobre estos mismos
  cubos: `mapa` = `{catalogo, presentes, faltantes, fuera_de_catalogo, cobertura}`. El juego no
  reimplementa nada: cuenta lo mismo que RRHH.
- `cursores`: `{rue, bus, chat}` para empalmar con el rio (ver abajo).
- `recientes[]`: hasta 40 eventos unificados, ts ascendente.

### `GET /api/mundo/rio?empresa=X&desde_rue=N&desde_bus=M&desde_chat=C&ciclos=K`
SSE (`text/event-stream`) con el mismo esqueleto que `/rio/{empresa}`: cada
ciclo emite los eventos nuevos y una linea `: latido`; ademas el pulso quema las
mechas vencidas. `ciclos=0` = infinito; `K>0` solo para tests/curl.

Evento unificado (`data:` en una sola linea de JSON; `id:` es `canal:id`):

```
{"canal":"rue"|"bus"|"chat","id":<int>,"tipo":"...","cubo":"..."|null,
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

- **Canal `chat`**: mensajes de la Colmena (`colmena_mensajes`): solo los de directores y del
  operador; las notas de sistema no salen. `id` = id del mensaje. El `tipo` dice quien y donde:
  `colmena.sala.director`, `colmena.individual.director`, `colmena.sala.operador`,
  `colmena.individual.operador`. `cubo` solo se rellena para un director (el que habla); la frase
  de un mensaje del operador empieza por `Tú: `. Sin las tablas de Colmena: canal vacio, nada
  se crea.

## Cursores
`desde_rue`, `desde_bus` y `desde_chat` son independientes; `-1` (defecto) = desde el
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

## Lo que el juego hace con cada cosa (y lo que NO hace)

| Llega | El juego |
|---|---|
| `estado.cubos[].alta` pasa a true | abre la sala (o levanta el pabellon) y el director llega andando |
| `estado.cubos[].salud` (OK, DEGRADADO, ERROR, SIN DATOS) | sala cuidada, con polvo, con polvo y goteras, o rotulada «sin datos» |
| evento `rue` o `bus` con `cubo` | el director dice la frase y una gota de tinta viaja al Registro, que la sella |
| evento sin cubo | solo gota y feed |
| `plataforma.aprobacion.*` | refresca la ventanilla |
| `chat` de un director | lo dice en su mesa; si es de la sala, camina a la Sala de Reunion |
| `finanzas.cobro.registrado`, `comercial.pedido.atribuido` | fuegos artificiales (hanabi) |
| `estado.dinero.modo_ahorro` | el gasto se marca y los directores dicen «en modo ahorro» |
| `estado.parado` | el mundo se congela y dice TODO PARADO |
| cubo nuevo en el catalogo | se le reserva el primer solar libre; al darlo de alta, se construye |

Sin conexion el mundo lo dice y **no inventa actividad**: conserva lo ultimo que supo.

Escritura: el juego solo usa `POST /cmd/aprobar|denegar|deshacer|parar_todo|reanudar`, con el
mismo CSRF y los mismos gestos de mantener pulsado que el panel (SI 0,8 s; PARAR TODO 2 s), y el
`GET /api/colmena/agentes` cuando el operador pulsa «Dar de alta a los directores» (es lo que ya
hacia abrir el chat: da de alta a los que faltan).

## Adorno y rincones (lo que reacciona al clic y NO es dato)

El mundo tiene mucho que tocar: arboles (lluvia de petalos u hojas), el torii, el puente y el
arroyo (un farolillo baja por la corriente), las islas flotantes, el sol, la montana, las nubes, el
bambu (oleadas), los furin del alero (suenan), los faroles, el cesped (brota una flor) y, ademas, los
directores y las salas (un destello, un salto, un pulso de luz; y se abre su ficha como siempre).

**Nada de eso es estado de la empresa.** No escribe en el backend, no crea eventos, no mueve dinero
ni aprobaciones, y no dice nada de ningun cubo. Las flores y los farolillos no se guardan. Lo unico
que se recuerda es cuales de los rincones has descubierto (`localStorage`, clave `kaizen-rincones`,
solo en ese navegador) y si el sonido esta activo (`kaizen-snd`). El sonido (campanillas en escala
pentatonica) solo suena como respuesta a un clic tuyo y se apaga con el boton «Sonido».

Lo que SI es real y se ve en el aspecto de un director: el **aura de chakra** (un halo con su color
y chispas que suben) aparece solo mientras acaba de hacer algo de verdad (un evento o un mensaje
suyo); un clic tuyo no la enciende. El color del pelo, de los ojos y de la cinta de la frente es
solo identidad del cubo, no salud ni estado.

La prueba `10e` de `tests/e2e/mundo.e2e.js` comprueba las dos cosas: que cada clic hace algo y que
el estado de la empresa (eventos, dinero, aprobaciones, parada) queda exactamente igual.

## Rendimiento y grados (`cubos[].rendimiento`)

Calculado por `panel_mando/rendimiento.py` (funciones puras, con tests) sobre datos reales: la tabla
`costes` (por cubo), los pedidos atribuidos y la cola de aprobaciones. Ventana de 30 dias. Forma:
`{rango, metrica, puntuacion, coste_eur, valor_eur, roi, decisiones:{firmes,rechazadas}, tasa_acierto, motivo}`.

| Regla | Valor (constantes del modulo) |
|---|---|
| Opta a grado | alta de 30 dias o mas |
| Comercial y Marketing (los dos con dinero medible) | ROI = valor de pedidos ATRIBUIDOS con importe / coste; experto con ROI >= 2. Comercial cuenta todos los pedidos; Marketing solo los de leads con fuente CAMPANA (cadena R-15) y su coste suma el del cubo y el gasto de canal de las metricas de sus campanas |
| Resto de cubos | acierto = firmes / (firmes + rechazadas); experto con >= 90 % y >= 5 decisiones |
| Mejor del mes | el experto de mayor puntuacion; un empate no premia a nadie |
| Sin muestra | `rango: null` y el `motivo` lo dice; nunca un grado inventado |

Firmes = APROBADA, EJECUTANDO, EJECUTADA. Rechazadas = DENEGADA, REVOCADA. Pendientes, anuladas y
caducadas no cuentan. Los pedidos pendientes de validacion externa no cuentan como valor.

**Limites honestos:** (1) ROI y acierto no son la misma unidad: la puntuacion es metrica / umbral, una
convencion para comparar, no una medida universal. (2) La tabla `costes` no tiene columna de empresa:
con varias empresas en la misma base el coste por cubo se mezcla. (3) El valor de Marketing es un SUBCONJUNTO
del de Comercial: el mismo pedido suma en los dos cubos («lo trajo una campana» y «lo cerro Comercial»). (4) Los cubos sin ingresos
atribuibles se miden por decisiones. Los umbrales los decide el
operador; cambiarlos es editar las constantes y este cuadro.

El juego lo dibuja en las bocamangas (veterano = 30 dias de alta; experto y mejor del mes solo si este
campo lo dice) y en la ficha del director. Ademas, en cada sala hay un orbe luminoso por evento de las
ultimas 24 h del cubo (hasta 8) y un halo que crece con esa cuenta: es `salud.eventos_24h`, dato real.

## Tesorería (sala de Finanzas): qué es cada cosa y de dónde sale

Nada está puesto porque sí; cada objeto dice algo verdadero o es un adorno declarado:

| Objeto | Qué muestra | Origen |
|---|---|---|
| Fuente con anillo de 12 gemas | gasto de hoy frente al tope diario: cada gema es 1/12 del tope; verde, ámbar desde el 70 %, rojo desde el tope o en modo ahorro | `dinero.gasto_eur`, `dinero.tope_eur`, `dinero.modo_ahorro` |
| Rótulo «hoy X de Y» | las mismas cifras en euros | `dinero` |
| Cofre «sin atribuir X» | gasto de la plataforma que no es de ningún cubo (se muestra, no se esconde) | `dinero.sin_atribuir_eur` |
| Estantería de libros de cuentas | un lomo por cada día desde el alta de Finanzas (hasta 28) | `cubos[finanzas].ts_alta` |
| Ábaco | las cuentas se deslizan cuando llega un evento de Finanzas | evento con `cubo = finanzas` |
| Daruma | lleva un ojo; se pinta el segundo cuando entra un cobro mientras miras (solo en esta sesión) | evento `finanzas.cobro.registrado` |
| Lluvia de monedas | un cobro real o un pedido atribuido | `finanzas.cobro.registrado`, `comercial.pedido.atribuido` |
| Orbes y halo de la sala | un orbe por evento de las últimas 24 h del cubo | `salud.eventos_24h` |
| Maneki-neko, medallón de parqué, mostrador en media luna, barandilla baja | adorno (la barandilla deja ver la sala desde el pasillo) | — |

## Comercial (sala): el camino del cliente

| Objeto | Qué muestra | Origen |
|---|---|---|
| Seis faroles en un sendero de piedras | los leads por paso (fríos, contactados, en conversación, comprometidos, con pedido, clientes): el farol crece y brilla con la cuenta y lleva un punto por lead | `cubos[comercial].pipeline.leads` |
| Cesta, papelera y sello rojo | dormidos, descartados y excluidos (quien pidió que no le contactemos) | `pipeline.leads` |
| Pilas del mostrador | valor atribuido y coste de 30 días; se vacían si no hay dato | `rendimiento.valor_eur`, `rendimiento.coste_eur` |
| Rótulo «ROI X×» o «ROI sin medir» | el ROI de 30 días o por qué no hay | `rendimiento` |
| Caja | la tapa salta y caen monedas con cada pedido atribuido de verdad; al tocarla dice cuántos hay y cuántos esperan validación | evento `comercial.pedido.atribuido`, `pipeline.pedidos` |
| Campanilla de la puerta | suena con cada evento real de Comercial; un punto de luz recorre el sendero con cada lead nuevo | eventos `comercial.*` |
| Barandilla baja en el lado de Marketing | adorno: deja ver el sendero | — |

## Marketing (sala): cometas y taller de tinta

| Objeto | Qué muestra | Origen |
|---|---|---|
| Una cometa atada a un carrete por campaña activa o pausada (hasta 6) | la cuerda se tensa con el gasto del presupuesto; al 90 % (kill-switch) cuerda y cometa se ponen rojas; la pausada descansa plegada en el suelo; con zoom, el porcentaje | `marketing.gasto` |
| Mesa de tinta con cuatro bandejas | borradores, validados por Marca, rechazados y lanzados (pila de hasta 6 hojas) | `marketing.contenidos` |
| Sello de Marca | se hunde y deja un destello verde con cada contenido aprobado de verdad | evento `marketing.contenido.aprobado` |
| Gong | vibra con cada evento real de Marketing; una chispa sube con cada campaña lanzada | eventos `marketing.*` |
| Barandilla baja hacia Marca | adorno: deja ver la sala | — |

