@echo off
title Kaizen - Tarjetas de demo para la Mesa
cd /d "%~dp0.."
python kaizen.py mesa proponer-demo --n 3
echo.
echo Ahora doble clic en "MESA DEL JEFE.cmd" para decidir SI o NO.
pause
