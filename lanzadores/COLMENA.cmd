@echo off
title Kaizen - Colmena (chat de directores)
cd /d "%~dp0.."
echo === COLMENA KAIZEN ===
echo Arrancando la Colmena; el navegador se abrira solo, ya con tu clave (un toque).
echo Si el Centro de Mando ya estaba abierto, se reutiliza: no arranca nada doble.
start "Colmena (no cerrar)" /min cmd /c "python -X utf8 -m panel_mando.colmena --abrir & pause"
echo Listo. Esta ventana puede cerrarse.
pause
