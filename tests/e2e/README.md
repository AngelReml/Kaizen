# Pruebas de extremo a extremo del Mundo

`mundo.e2e.js` arranca `servidor_e2e.py` (la app REAL de `panel_mando` sobre datos temporales del
tenant sintético `laboratorio`) y recorre el juego con un navegador: arranque vacío, alta de
directores, eventos de la bitácora y del bus, chat de la Colmena, texto hostil, ventanilla (SÍ
mantenido, mecha, deshacer, NO), gasto y modo ahorro, PARAR TODO, sello íntegro y roto, caída y
vuelta del backend, recarga, un cubo nuevo y los «rincones» (cada clic de adorno hace algo sin tocar
el estado de la empresa).

`servidor_e2e.py` añade rutas `/_e2e/*` **solo en ese proceso de prueba** para provocar hechos por los
caminos reales del backend. Nada de eso existe en el producto.

```
python -m pip install -r requirements-dev.txt        # backend
npm i playwright && npx playwright install chromium  # navegador
node tests/e2e/mundo.e2e.js
```

Variables: `KAIZEN_PY` (intérprete, por defecto `python3`), `KAIZEN_CHROME` (ruta del Chromium),
`PLAYWRIGHT_MODULE`, `KAIZEN_E2E_PUERTO` (8631), `VERBOSO=1`. Sale con código 1 si falla algún
escenario. Tarda unos cinco minutos (el navegador de pruebas dibuja despacio).
