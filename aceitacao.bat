@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.
    pause
    exit /b 1
)
echo Verificando os criterios de conclusao com documentos ficticios...
echo Seus documentos e o banco da aplicacao nao sao utilizados.
echo.
".venv\Scripts\python.exe" scripts\aceitacao.py
echo.
pause
