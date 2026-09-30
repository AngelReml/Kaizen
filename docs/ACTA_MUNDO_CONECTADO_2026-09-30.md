# ACTA — El Mundo conectado al backend real

**Tipo:** acta de puerta (capa 4) · **Fecha:** 2026-09-30 · **Estado:** cerrada por el lado de la máquina; **pendiente el visto bueno visual del operador** (ver §4).

## 1. Qué se observó funcionando (salida literal)

- Suite: `1380 passed, 8 skipped` (línea previa reproducida antes en el mismo entorno: `1343 passed, 8 skipped`). Fila nueva en `docs/LINEA_BASE.md`.
- Extremo a extremo, contra la app real de `panel_mando` sobre datos sintéticos (`node tests/e2e/mundo.e2e.js`): `17 de 17 escenarios en verde`:
  arranque vacío (5 salas cerradas, 5 pabellones reservados, 0 agentes) · alta de directores desde RRHH con un clic (10 directores, 5 pabellones construidos) · evento de la bitácora (aparece, habla el director, se sella) · evento del bus · chat de la Colmena (en su mesa y en la Sala de Reunión) · texto hostil (se muestra literal, no se ejecuta) · ventanilla (SÍ corto no aprueba, SÍ mantenido arma la mecha, deshacer aborta, NO deniega, aprobación interna se ejecuta) · gasto real (salud DEGRADADA, polvo en las salas, modo ahorro) · PARAR TODO con 2 s y REANUDAR · sello íntegro y sello roto (también en la barra) · caída del backend (lo dice, no inventa, no duplica al volver) · recarga · cubo nuevo (se reserva el solar libre y se construye al darlo de alta) · ráfaga de 300 eventos (gotas acotadas a 40) · modo con clave (redirige sin sesión, CSRF aceptado, al caducar la sesión vuelve al acceso) · sin errores de JavaScript.
- Capturas de cada estado contra el backend real: enviadas al operador en la sesión.

## 2. Qué NO está hecho (honesto)

- **Visto bueno visual del operador en su PC:** no dado. Hasta entonces no se retira nada del entorno de ensayo (`tests/e2e`).
- **Rendimiento en GPU real:** solo medido en un navegador de pruebas sin GPU (Chromium con SwiftShader). No hay cifra válida para el PC del operador.
- **Productores reales por tipo de evento:** no auditados uno a uno (`docs/MAPA_EVENTOS_MUNDO.md`, §3). Un tipo sin productor nunca dispara nada y el juego no lo simula.
- **Fuera del juego por no existir en el backend:** laboratorio de nichos, jurado externo, WebLLM/OmniRoute, misión con plazo, cuota por agente, propuestas de inversión, emisión 24/7. El brainstorming las describe; el backend actual no las implementa. Decisión de producto pendiente (punto a hablar).
- **Alertas de rendimiento de RRHH:** el cubo RRHH no tiene fuente persistente (lo dice su propia herramienta); el juego no las inventa.
- **Datos reales del operador:** no probado con su `KAIZEN_DATOS`, solo con el tenant sintético.
- **Maqueta anterior (artifact de claude.ai, versión 3):** sigue siendo la maqueta con `[DEMO]`; no se conecta ni se actualiza. El producto es `mundo/index.html` servido por el backend.

## 3. Hallazgos del backend (a la lista única de deuda, no arreglados salvo lo dicho)

1. `GET /api/colmena/agentes` da de alta a los 10 directores **al leerlo** (escribe y sella eventos con un GET). El juego no lo llama al cargar; solo lo hace el botón «Dar de alta a los directores».
2. **Dos contadores de coste que no se hablan:** el de los cubos (`sustrato/coste.py`, límite por defecto 16 €) y el ledger del tenant (`core/techos.py`, tope 5 €). La salud de un cubo y el «modo ahorro» miden cosas distintas.
3. Nombres dobles entre manifests y catálogo (`ops`/`operaciones`, `inteligencia`/`inteligencia_mercado`, `qa`/`opengravity`) y dossier D03 inexistente: `docs/MATRIZ_CUBOS.md`.
4. El cubo Comercial salía en ERROR en una instalación nueva (tablas del registro sin crear): **corregido** (ahora `SIN DATOS`, con test).
5. La cadena RUE empieza en `n = 0`: el cursor de un tenant vacío era 0 y el primer evento se perdía. **Corregido** (`-1`, con test).
6. `panel_mando/colmena.py::NOMBRES` escribe «Exito de cliente» sin tilde; el juego muestra lo que dice el backend.

## 4. Acciones exclusivas del operador (≤ 5)

1. Abrir el juego en su PC con `lanzadores/MUNDO.cmd` (o `python -m panel_mando --abrir --pagina /mundo`), pulsar «Dar de alta a los directores» en la pestaña **Cubos** y dar su visto bueno visual (o decir qué cambia).
2. Decidir el punto de producto del §2: ¿el backend debe implementar la misión de nichos y la cuota por agente, o el brainstorming se ajusta a lo que hay?
3. Confirmar que el brainstorming (revisión 24) puede actualizarse con lo decidido en esta ronda (RRHH como sustrato, salas = cubos).

## 5. Adenda — rediseño estético y de interacción (2026-09-30, misma sesión)

**Petición del operador:** el mundo se veía rígido y cuadrado; quería curvas, un aire de anime (Naruto / Final Fantasy sin perder lo japonés), mucha más interacción y que lo bonito pesara más que lo demás.

**Qué cambió (solo forma; el contrato con el backend no se toca):**
- Casa: huella de esquinas redondas, veranda curva, alero de tejas que sube en las puntas, ventanas de campana y de luna, arcos lacados en las puertas. Pabellones con la misma lógica (plataforma curva, alero).
- Jardín: arroyo serpenteante con puente de arco rojo, torii grande, bosque de bambú con bordes curvos y claros, senderos suavizados, rastrillado ondulado. Se quitaron los setos rectos.
- Cielo: monte nevado, tres islas flotantes con cascada, una grulla que cruza de vez en cuando, motas de luz.
- Directores: pelo, ojos y cinta de la frente (hitai-ate) propios de cada cubo; ojos grandes con iris y brillos. **Aura de chakra solo mientras el director acaba de hacer algo real** (un evento o un mensaje suyo): un clic tuyo no la enciende.
- Interacción: árboles, torii, puente, arroyo (farolillos), islas, sol, nubes, bambú (oleadas), furin del alero, faroles, césped (brota una flor), salas y directores reaccionan al clic; 5 kodamas escondidos; sonido opcional (botón «Sonido»); contador de rincones descubiertos.
- Interfaz: paneles y botones en píldora, cristal de sakura, tipografías redondeadas.

**Qué se comprobó (salida literal):**
- `node tests/e2e/mundo.e2e.js` → `18 de 18 escenarios en verde` (los 17 anteriores + `10e rincones`, que comprueba que cada clic hace algo **y** que eventos, dinero, aprobaciones y parada quedan exactamente igual).
- `pytest tests/test_mundo_api.py` → `36 passed`. El backend no se ha modificado en este rediseño.
- Rendimiento comparado en el mismo navegador sin GPU (SwiftShader, 1440×900, Nitidez ×2): antes 54,6 ms por fotograma, ahora 48,4 ms. No es una cifra válida para el PC del operador.

**Qué NO está hecho / límites honestos:**
- El visto bueno visual del operador en su PC sigue pendiente (y ahora sobre un aspecto nuevo).
- El sonido y el aspecto con la paleta de las otras estaciones (invierno, primavera) no se han revisado uno a uno; se vio otoño (la estación real de la fecha), atardecer y noche.
- Las flores, farolillos y destellos son adorno puro: no se guardan y no dicen nada de la empresa. Solo persisten los rincones descubiertos y la preferencia de sonido (`localStorage`).

