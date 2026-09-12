@echo off
title Kaizen - Mesa del Jefe
cd /d "%~dp0.."
start "Mesa del Jefe (no cerrar)" /min cmd /c "python mesa_jefe.py & pause"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8700
echo La Mesa del Jefe esta abierta en el navegador.
pause
