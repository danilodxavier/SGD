@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem Backup na pasta BACKUP do projeto, mantendo os 30 mais recentes.
rem Usado manualmente (duplo clique) ou pelo Agendador de Tarefas do Windows.
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.
    exit /b 1
)
".venv\Scripts\python.exe" scripts\backup.py --destino "%~dp0BACKUP" --manter 30
exit /b %errorlevel%
