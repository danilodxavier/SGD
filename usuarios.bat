@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.
    exit /b 1
)
if "%~1"=="" (
    echo Gestao de usuarios - exemplos:
    echo   usuarios.bat listar
    echo   usuarios.bat criar --usuario maria.silva --nome "Maria Silva" --perfil admin
    echo   usuarios.bat redefinir-senha --usuario maria.silva
    echo   usuarios.bat desbloquear --usuario maria.silva
    echo   usuarios.bat ativar --usuario maria.silva
    exit /b 0
)
".venv\Scripts\python.exe" scripts\usuarios.py %*
