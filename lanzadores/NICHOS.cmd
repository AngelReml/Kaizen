@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Kaizen - Buscar nichos
cd /d "%~dp0.."
:menu
echo.
echo === KAIZEN: BUSCAR NICHOS ===
echo  1) Lanzar una tanda de exploracion (3 ciclos; puede tardar; deja un informe)
echo  2) Ver las apuestas
echo  3) Leer una apuesta (pide el id)
echo  4) Elegir una apuesta para probarla (pide el id)
echo  5) Descartar una apuesta (pide el id y unas preguntas)
echo  0) Salir
echo.
set "op="
set /p op=Elige una opcion: 
if "!op!"=="1" goto tanda
if "!op!"=="2" goto listar
if "!op!"=="3" goto ver
if "!op!"=="4" goto elegir
if "!op!"=="5" goto descartar
if "!op!"=="0" goto fin
goto menu

:tanda
python -X utf8 herramientas\apuestas.py tanda --ciclos 3
goto menu

:listar
python -X utf8 herramientas\apuestas.py listar
goto menu

:ver
set "id="
set /p id=Id: 
python -X utf8 herramientas\apuestas.py ver "!id!"
goto menu

:elegir
set "id="
set /p id=Id: 
python -X utf8 herramientas\apuestas.py elegir "!id!"
goto menu

:descartar
set "id="
set /p id=Id: 
python -X utf8 herramientas\apuestas.py descartar "!id!"
goto menu

:fin
pause
