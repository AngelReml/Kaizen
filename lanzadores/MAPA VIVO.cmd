@echo off
title Kaizen - Mapa vivo (registro obligatorio de acciones)
cd /d "%~dp0.."
echo === KAIZEN - MAPA VIVO ===
echo Instala el hook obligatorio y regenera MAPA_VIVO.md desde git (todas las ramas).
echo.
if not exist ".git\hooks" mkdir ".git\hooks"
copy /y "herramientas\hooks\pre-commit" ".git\hooks\pre-commit" >nul
echo Hook pre-commit instalado/actualizado.
echo.
python -X utf8 herramientas\mapa_vivo.py --generar
python -X utf8 herramientas\mapa_vivo.py --verificar
echo.
echo Si el mapa cambio, entrara en el proximo commit (COMMIT LOCAL.cmd).
pause
