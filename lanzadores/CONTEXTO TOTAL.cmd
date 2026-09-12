@echo off
title Kaizen - Contexto total para IA
cd /d "%~dp0.."
python _workspace\wiki\generar_contexto.py
echo.
echo Generados: CONTEXTO_TOTAL.txt (SOLO uso local) y CONTEXTO_TOTAL_SIN_TERCEROS.txt (apto para nube).
pause
