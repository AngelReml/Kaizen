@echo off
title Kaizen - Preparacion inicial (solo una vez)
cd /d "%~dp0.."
echo === Preparacion inicial de Kaizen ===
echo (1 de 3) Instalando dependencias...
python -m pip install -r requirements.txt
echo.
echo (2 de 3) Creando la base de datos con tus leads reales...
python kaizen.py registro migrar
echo.
echo (3 de 3) Generando el primer panel...
python kaizen.py director --html
echo.
echo LISTO. A partir de ahora usa: "CENTRO DE MANDO.cmd" y "REVISION DIARIA.cmd"
pause
