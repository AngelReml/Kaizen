@echo off
title Kaizen - Revision diaria
cd /d "%~dp0.."
echo === Revision diaria de Kaizen ===
echo (1) Sincronizando knowledge con el registro...
python kaizen.py registro sync
if errorlevel 1 (echo FALLO en este paso & pause & exit /b 1)
echo.
echo (2) Verificacion forense (cadenas, coste, avisos)...
python kaizen.py forense diario
if errorlevel 1 (echo FALLO en este paso & pause & exit /b 1)
echo.
python kaizen.py director --html
if errorlevel 1 (echo FALLO en este paso & pause & exit /b 1)
start "" "%~dp0..\panel\director.html"
echo.
echo Revision terminada. El panel se ha abierto en el navegador.
pause
