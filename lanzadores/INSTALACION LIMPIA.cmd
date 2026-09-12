@echo off
title Kaizen - Verificacion de instalacion limpia (B1.4, E5)
cd /d "%~dp0.."
echo === KAIZEN - INSTALACION LIMPIA: venv virgen + requirements.txt + suite ===
echo Sustituto local del CI de instalacion limpia (D00 B1.4) hasta que haya infra CI.
echo No toca tu entorno normal: crea _workspace\venv_limpia y la borra tu cuando quieras.
echo.
set LINEA_BASE_CIFRA=
for /f "delims=" %%L in ('python -X utf8 herramientas\mapa_vivo.py --linea-base') do set LINEA_BASE_CIFRA=%%L
if "%LINEA_BASE_CIFRA%"=="" set LINEA_BASE_CIFRA=(no se pudo leer LINEA_BASE.md, revisa a mano)
if exist _workspace\venv_limpia rmdir /s /q _workspace\venv_limpia
python -m venv _workspace\venv_limpia || (echo ERROR creando venv & pause & exit /b 1)
call _workspace\venv_limpia\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt || (echo ERROR instalando requirements & pause & exit /b 1)
python -m pip install --quiet pytest
echo.
echo === Suite completa en el entorno virgen ===
python -m pytest -q
echo.
echo Si la cifra iguala LINEA_BASE.md (%LINEA_BASE_CIFRA%), la instalacion limpia esta VERDE (E5 cerrado).
echo Si faltan modulos: el bug es de requirements.txt, no del entorno. Anotarlo en DEUDA_TECNICA.md.
pause
