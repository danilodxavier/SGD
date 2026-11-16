@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title SAD-GD - Apoio a Decisao e Gestao Documental

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.
    pause
    exit /b 1
)

echo Iniciando o servidor de IA local (Ollama do projeto)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\ollama.ps1" -Acao iniciar

echo Iniciando o SAD-GD...
echo Mantenha esta janela aberta. Para encerrar, execute stop.bat ou pressione Ctrl+C.
echo.
".venv\Scripts\python.exe" -m app %*
if errorlevel 1 (
    echo.
    echo [ERRO] O servidor foi encerrado com erro. Execute diagnostico.bat e consulte data\logs\app.log.
    pause
)
