@echo off
setlocal
cd /d "%~dp0..\.."
rem Inicio automatico na rede (tarefa "SAD-GD"): Ollama do projeto e, em seguida, o servidor HTTPS.
rem Mensagens em data\logs\servidor_console.log. Nao encadear o ollama.ps1 com pipes (o processo herda o pipe).
if not exist "data\logs" mkdir "data\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sadgd\ollama.ps1" -Acao iniciar >> "data\logs\servidor_console.log" 2>&1
call "%~dp0..\..\servidor.bat"
exit /b %errorlevel%
