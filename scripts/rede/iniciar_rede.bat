@echo off
setlocal
cd /d "%~dp0..\.."
rem Inicio automatico na rede (tarefa "SAD-GD"): Ollama do projeto e, em seguida, o servidor.
rem Mensagens do servidor em data\logs\servidor_console.log. NAO redirecionar nem encadear a saida do ollama.ps1:
rem o "ollama serve" herda o identificador e o lote nunca chega ao servidor (verificado em 2026-11-21).
if not exist "data\logs" mkdir "data\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sadgd\ollama.ps1" -Acao iniciar
rem Vigia: se o servidor cair com erro (ex.: 0xC0000005 em 2026-11-23), reinicia em 15 s. O Agendador so
rem reinicia quando a tarefa falha ao iniciar. Saida normal (codigo 0) encerra; no maximo 20 reinicios.
set /a REINICIOS=0
:servidor
call "%~dp0..\..\servidor.bat"
set CODIGO=%errorlevel%
if "%CODIGO%"=="0" exit /b 0
if %REINICIOS% geq 20 exit /b %CODIGO%
set /a REINICIOS+=1
echo ==== %date% %time% servidor caiu (codigo %CODIGO%); reinicio %REINICIOS% em 15 s ====>> "data\logs\servidor_console.log"
ping -n 16 127.0.0.1 >nul
goto servidor
