@echo off
REM GastroMed Pro - diagnostico del estado del sistema y de los respaldos
chcp 65001 >nul
title GastroMed Pro - Verificar estado
set "GASTROMED_ENV_FILE=%~dp0..\..\datos\gastromed.env"
cd /d "%~dp0.."
".venv\Scripts\python.exe" scripts\diagnostico.py
echo.
echo Ultimas lineas del registro de respaldos:
powershell.exe -NoProfile -Command "Get-Content -Tail 5 -Encoding UTF8 '%~dp0..\..\datos\respaldo.log' -ErrorAction SilentlyContinue"
echo.
pause
