@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
title KAIZEN (REAL)
cd /d "%~dp0.."

REM ============================================================
REM  Launcher de KAIZEN en MODO REAL (panel con Claude de verdad).
REM  Crea un venv local la primera vez, instala dependencias,
REM  arranca el servidor y abre el navegador. Sin tocar nada.
REM ============================================================

REM --- a) Python instalado? ---
set "PYEXE=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul && set "PYEXE=py"
)
where %PYEXE% >nul 2>nul
if errorlevel 1 (
  echo.
  echo   ============================================================
  echo    Falta Python. Descargalo desde https://python.org
  echo    Durante la instalacion marca "Add Python to PATH".
  echo    Luego vuelve a hacer doble clic en este icono.
  echo   ============================================================
  echo.
  pause
  exit /b 1
)

REM --- b) Crear venv la primera vez ---
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Primer arranque: creando entorno virtual .venv ...
  echo   esto solo pasa una vez
  %PYEXE% -m venv .venv
  if errorlevel 1 (
    echo   No se pudo crear el entorno virtual.
    pause
    exit /b 1
  )
)

REM --- activar venv ---
call ".venv\Scripts\activate.bat"

REM --- c) Instalar dependencias si faltan (primera vez) ---
python -c "import uvicorn, fastapi" >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Instalando dependencias del backend...
  echo   La PRIMERA vez tarda varios minutos. Las siguientes, instantaneo.
  echo.
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   Fallo instalando dependencias. Revisa el error de arriba.
    pause
    exit /b 1
  )
)

REM --- d) Modo REAL: comprobar API key (NO se define SOE_SIM) ---
if not exist ".env" (
  echo.
  echo   Falta .env con ANTHROPIC_API_KEY ^(el modo REAL lo necesita^).
  echo   Copia .env.example a .env y pon tu clave.
  echo.
  pause
  exit /b 1
)

REM --- f/g) Abrir el navegador predeterminado tras 3s, en segundo plano ---
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8000'"

REM --- e/h) Arrancar el servidor en primer plano (logs visibles) ---
echo.
echo   ============================================================
echo    KAIZEN  en  http://127.0.0.1:8000   [ MODO REAL - Claude ]
echo    Prospeccion y redaccion usan el LLM real y la web (CON COSTE).
echo    El navegador se abrira solo en unos segundos.
echo    Cierra esta ventana o pulsa Ctrl+C para detener el servidor.
echo   ============================================================
echo.
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000

REM --- i) Al detenerse, la ventana se queda abierta para leer ---
echo.
echo   Servidor detenido.
pause