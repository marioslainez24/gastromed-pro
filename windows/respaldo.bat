@echo off
REM NeuroMed Pro - respaldo automatico (lo ejecuta la tarea programada diaria)
chcp 65001 >nul
set "GASTROMED_ENV_FILE=%~dp0..\..\datos\neuromed.env"
cd /d "%~dp0.."
".venv\Scripts\python.exe" scripts\respaldo.py automatico
