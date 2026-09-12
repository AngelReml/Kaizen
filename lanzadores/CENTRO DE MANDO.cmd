@echo off
title Kaizen - Centro de Mando (D10)
cd /d "%~dp0.."
echo === CENTRO DE MANDO KAIZEN ===
echo Arrancando el panel; el navegador se abrira solo, ya con tu clave (un toque).
start "Centro de Mando (no cerrar)" /min cmd /c "python -X utf8 -m panel_mando --abrir & pause"
echo Listo. Esta ventana puede cerrarse.
pause
