@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
title KAIZEN - Verificar E0-E1
cd /d "%~dp0.."

REM Activar el entorno del proyecto si existe (para tener pytest).
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo ============================================================
echo   VERIFICACION DE E0-E1  (lo construido esta sesion)
echo ============================================================
echo.
echo [1/5] SUITE COMPLETA — no debe haber NINGUN rojo (FAILED).
echo       Esperado: "... passed, 7 skipped"  y  0 failed.
echo ------------------------------------------------------------
python -m pytest -q
echo.
echo [2/5] LAS PRUEBAS NUEVAS DE E0-E1  (21 comprobaciones).
echo       Esperado: "21 passed".
echo ------------------------------------------------------------
python -m pytest tests\test_i123_persistencia.py tests\test_aiact_email_mecanismo.py tests\test_registro_sync_y_watchdog.py tests\test_tenant_laboratorio.py -q
echo.
echo [3/5] CANDADO AI ACT DE EMAIL — estado del canal.
echo       Esperado HOY: "CERRADO" (aun no has aprobado ningun texto).
echo ------------------------------------------------------------
python -c "from core.aiact_gate import variante_email_activa as v; x=v(); print('   >> CANAL EMAIL CERRADO (correcto, fail-closed): no hay texto de transparencia aprobado.' if x is None else '   >> CANAL ABIERTO con el texto: '+x[:60])"
echo.
echo [4/5] TENANT SINTETICO — se genera en un fichero temporal (NO toca tus datos).
echo       Esperado: "50 leads sinteticos (50 con email .invalid)".
echo ------------------------------------------------------------
python herramientas\generar_tenant_laboratorio.py --knowledge "%TEMP%\kz_verif_laboratorio.json" --n 50
del "%TEMP%\kz_verif_laboratorio.json" >nul 2>nul
echo.
echo [5/5] COMMIT — el ultimo commit local debe ser el de E0-E1.
echo       Esperado: "kaizen D11 E0-E1: ...".
echo ------------------------------------------------------------
git log -1 --format="   >> %%h  %%s"
echo.
echo ============================================================
echo   LECTURA DEL RESULTADO
echo   - Paso 1 y 2 sin FAILED  = lo nuevo funciona y no rompi nada.
echo   - Paso 3 "CERRADO"        = la ley se cumple sola; el email
echo                               NO puede salir hasta que apruebes texto.
echo   - Paso 4 "50 ... .invalid"= el campo de pruebas esta listo.
echo   - Paso 5 con "E0-E1"      = el trabajo esta sellado en git.
echo ============================================================
pause
