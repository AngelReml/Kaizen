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
