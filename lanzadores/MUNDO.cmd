@echo off
title Kaizen - El Mundo
cd /d "%~dp0.."
echo === EL MUNDO DE KAIZEN ===
echo Arrancando el panel; el navegador se abrira solo en el juego, ya con tu clave (un toque).
start "Kaizen (no cerrar)" /min cmd /c "python -X utf8 -m panel_mando --abrir --pagina /mundo & pause"
echo Listo. Esta ventana puede cerrarse. Para parar Kaizen, cierra la ventana minimizada.
pause
