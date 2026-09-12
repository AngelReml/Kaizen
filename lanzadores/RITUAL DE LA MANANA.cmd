@echo off
title Kaizen - Ritual de la manana (gasta centimos, con freno)
cd /d "%~dp0.."
echo === Ritual de la manana: el comercial fabrica tarjetas REALES ===
python kaizen.py ritual manana --n 3
echo.
echo Tarjetas listas. Abriendo la Mesa del Jefe...
start "Mesa del Jefe (no cerrar)" /min cmd /c "python mesa_jefe.py & pause"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8700
pause
