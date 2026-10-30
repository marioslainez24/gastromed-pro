@echo off
REM GastroMed Pro - iniciar el servidor y abrir el navegador. No cierre esta ventana mientras usa el sistema.
chcp 65001 >nul
title GastroMed Pro - servidor (NO CERRAR)
set "GASTROMED_ENV_FILE=%~dp0..\..\datos\gastromed.env"
cd /d "%~dp0.."
".venv\Scripts\python.exe" servidor.py --abrir
echo.
echo El servidor se detuvo. Si fue un error, tome una foto de esta ventana.
pause
