@echo off
title Kaizen - Commit local (git SOLO local, jamas push)
cd /d "%~dp0.."
echo === KAIZEN - COMMIT LOCAL ===
echo Regla R1: git solo local. Este lanzador NUNCA hace push ni configura remotes.
echo.
if exist .git\index.lock (
  echo Borrando .git\index.lock huerfano...
  del /f .git\index.lock
)
for /f "delims=" %%i in ('git config user.name') do set GITNOMBRE=%%i
if "%GITNOMBRE%"=="" (
  echo No hay identidad git configurada en este repo.
  set /p GITNOMBRE=Tu nombre para los commits:
  set /p GITEMAIL=Tu email para los commits:
  git config user.name "%GITNOMBRE%"
  git config user.email "%GITEMAIL%"
)
echo.
echo === Mapa vivo: hook obligatorio (L2, nada invisible) ===
if not exist ".git\hooks" mkdir ".git\hooks"
copy /y "herramientas\hooks\pre-commit" ".git\hooks\pre-commit" >nul
echo Hook pre-commit instalado/actualizado: centinela de datos + MAPA_VIVO.md al dia.
echo.
echo === CENTINELA DE DATOS (R-REV-1): ningun dato de tercero sale de esta maquina ===
echo Preparando el indice para revisarlo ANTES de gastar tiempo en la suite...
git add -A
python -X utf8 herramientas\centinela_datos.py --staged
if errorlevel 1 (
  echo.
  echo ***********************************************************
  echo  COMMIT CANCELADO POR EL CENTINELA DE DATOS.
  echo  Arriba tienes la lista exacta de ficheros y el motivo.
  echo  Hay datos de cliente, PII o secretos en el indice.
  echo.
  echo  Que hacer:
  echo   1^) Saca cada fichero del indice:  git restore --staged ^<ruta^>
  echo   2^) Y si de verdad debe entrar, deja constancia del porque:
  echo        set CENTINELA_OVERRIDE=motivo de la excepcion
  echo      y vuelve a lanzar este mismo fichero.
  echo.
  echo  Tus cambios NO se han perdido: siguen en el indice ^(git status^).
  echo ***********************************************************
  pause
  exit /b 1
)
echo Centinela OK: el indice esta limpio de datos de terceros y secretos.
echo.
echo === Suite completa (regla R6: la linea base solo puede subir) ===
set LINEA_BASE_CIFRA=
for /f "delims=" %%L in ('python -X utf8 herramientas\mapa_vivo.py --linea-base') do set LINEA_BASE_CIFRA=%%L
if "%LINEA_BASE_CIFRA%"=="" set LINEA_BASE_CIFRA=(no se pudo leer LINEA_BASE.md, revisa a mano)
echo Linea base vigente: %LINEA_BASE_CIFRA% (ver LINEA_BASE.md)
python -m pytest -q
echo.
echo Compara la cifra de arriba con LINEA_BASE.md.
set /p CONFIRMA=La cifra IGUALA O SUPERA %LINEA_BASE_CIFRA%? (S/N):
if /i not "%CONFIRMA%"=="S" (
  echo Commit CANCELADO. Si bajo la suite: bloqueo R6, investigar antes de committear.
  echo Pista DT-26.07.03-1: si fallo por quota de voz 25/25, resetear state\voz\quota\quota_AAAAMMDD.json y reintentar.
  pause
  exit /b 1
)
echo.
set MSG=
set /p MSG=Mensaje del commit (Enter = "kaizen: avance de sesion"):
if "%MSG%"=="" set MSG=kaizen: avance de sesion %DATE%
git add -A
git commit -m "%MSG%" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.
echo === Verificacion del mapa vivo (cobertura de commits) ===
python -X utf8 herramientas\mapa_vivo.py --verificar
echo.
echo Hecho. Si la cifra de la suite SUPERO la linea base, registra la nueva en LINEA_BASE.md.
pause
