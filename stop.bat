@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado.
    exit /b 1
)
".venv\Scripts\python.exe" -m app parar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\ollama.ps1" -Acao parar
timeout /t 3 >nul 2>nul
