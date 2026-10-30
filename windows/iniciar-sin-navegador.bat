@echo off
REM GastroMed Pro - inicio automatico al encender la PC (sin abrir el navegador)
chcp 65001 >nul
title GastroMed Pro - servidor (NO CERRAR)
set "GASTROMED_ENV_FILE=%~dp0..\..\datos\gastromed.env"
cd /d "%~dp0.."
".venv\Scripts\python.exe" servidor.py
pause
