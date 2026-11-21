@echo off
setlocal
cd /d "%~dp0..\.."
rem Inicio automatico na rede (tarefa "SAD-GD"): Ollama do projeto e, em seguida, o servidor.
rem Mensagens do servidor em data\logs\servidor_console.log. NAO redirecionar nem encadear a saida do ollama.ps1:
rem o "ollama serve" herda o identificador e o lote nunca chega ao servidor (verificado em 2026-11-21).
if not exist "data\logs" mkdir "data\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sadgd\ollama.ps1" -Acao iniciar
call "%~dp0..\..\servidor.bat"
exit /b %errorlevel%
