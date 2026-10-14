@echo off
setlocal
cd /d "%~dp0"

rem Inicia o sistema sem janela de navegador e sem pausas, para uso pelo Agendador de Tarefas do Windows
rem (inicio automatico). As mensagens do servidor vao para data\logs\servidor_console.log.
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Execute instalar.bat primeiro.>> "%~dp0data\logs\servidor_console.log"
    exit /b 1
)
if not exist "data\logs" mkdir "data\logs"
echo ==== %date% %time% inicio do servidor ====>> "data\logs\servidor_console.log"
".venv\Scripts\python.exe" -m app --sem-navegador >> "data\logs\servidor_console.log" 2>&1
exit /b %errorlevel%
