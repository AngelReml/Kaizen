# El Mundo de Kaizen

El edificio isométrico en el que se ve trabajar a los directores de los cubos. **No es una
maqueta**: es la vista del backend real. Cada sala es un cubo, cada director nace del alta de la
Colmena, cada movimiento sale de un evento sellado, la ventanilla es la cola de aprobaciones y el
sello se comprueba de verdad. Sin conexión lo dice y no inventa nada.

Contrato con el backend: `docs/CONTRATO_MUNDO.md`. Implementación de los endpoints:
`panel_mando/mundo.py`.

## Verlo

En Windows: doble clic en `lanzadores/MUNDO.cmd` (arranca el panel y abre `/mundo`).
En cualquier sistema: `python -m panel_mando --abrir --pagina /mundo` → http://127.0.0.1:8600/mundo

Al primer arranque de una empresa nueva las salas de cubo salen «SIN DAR DE ALTA»: en la pestaña
**Cubos**, RRHH propone dar de alta a los directores y un clic los da de alta.

## Cómo está hecho

Un solo fichero, `mundo/index.html` (HTML + CSS + JS, sin dependencias ni build), servido por el
backend en el mismo origen: reutiliza la sesión, la cookie y el CSRF del panel. Se edita
directamente. La resolución (Nitidez ×1, ×2, ×3) es una preferencia del navegador.

## Probarlo

`node tests/e2e/mundo.e2e.js` levanta la app real sobre datos sintéticos y recorre el juego con un
navegador (ver `tests/e2e/README.md`). Los endpoints tienen sus tests en `tests/test_mundo_api.py`.
