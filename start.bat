@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Agente de Inteligencia Documental

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.
    pause
    exit /b 1
)

echo Iniciando o Agente de Inteligencia Documental...
echo Mantenha esta janela aberta. Para encerrar, execute stop.bat ou pressione Ctrl+C.
echo.
".venv\Scripts\python.exe" -m app %*
if errorlevel 1 (
    echo.
    echo [ERRO] O servidor foi encerrado com erro. Execute diagnostico.bat e consulte data\logs\app.log.
    pause
)
