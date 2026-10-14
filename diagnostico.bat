@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\diagnostico.py
) else (
    echo [WARNING] Ambiente virtual .venv nao encontrado - usando o Python do sistema.
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado no PATH.
    ) else (
        python scripts\diagnostico.py
    )
)
echo.
pause
