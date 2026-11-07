@echo off
REM NeuroMed Pro - instalar o actualizar en esta PC (Windows 11)
title Instalador de NeuroMed Pro
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\instalar.ps1"
