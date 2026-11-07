@echo off
REM NeuroMed Pro - MODO DEMOSTRACION con pacientes ficticios (base separada, puerto 8001, solo esta PC)
chcp 65001 >nul
title NeuroMed Pro - DEMOSTRACION (NO CERRAR)
set "GASTROMED_ENV_FILE=%~dp0..\..\demostracion\no-existe.env"
set "GASTROMED_ENV=desarrollo"
set "GASTROMED_DEMO=1"
set "GASTROMED_DATABASE_PATH=%~dp0..\..\demostracion\neuromed.sqlite3"
set "GASTROMED_FILES_DIR=%~dp0..\..\demostracion\archivos"
set "GASTROMED_BACKUP_DIR=%~dp0..\..\demostracion\respaldos"
set "GASTROMED_PORT=8001"
set "GASTROMED_HOST=127.0.0.1"
cd /d "%~dp0.."
if not exist "%~dp0..\..\demostracion\neuromed.sqlite3" (
  ".venv\Scripts\python.exe" scripts\seed_demo.py
)
start "" notepad.exe "%~dp0..\..\demostracion\credenciales_demo.txt"
".venv\Scripts\python.exe" servidor.py --abrir
pause
