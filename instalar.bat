@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Instalacao - Agente de Inteligencia Documental

echo ============================================================
echo  Instalacao - Agente de Inteligencia Documental
echo ============================================================
echo.

echo [1/9] Verificando Windows...
ver | findstr /i "Windows" >nul
if errorlevel 1 goto :erro_windows
echo [OK] Windows identificado.

echo [2/9] Verificando Python...
where python >nul 2>nul
if errorlevel 1 goto :erro_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :erro_versao
for /f "delims=" %%v in ('python --version') do echo [OK] %%v

echo [3/9] Criando ambiente virtual .venv...
if exist ".venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual ja existe.
) else (
    python -m venv .venv
    if errorlevel 1 goto :erro_venv
    echo [OK] Ambiente virtual criado.
)

echo [4/9] Criando diretorios de trabalho...
for %%d in (data\database data\index data\cache data\logs data\reports data\backups) do (
    if not exist "%%d" mkdir "%%d"
)
echo [OK] Diretorios em data\

echo [5/9] Instalando dependencias - pode levar alguns minutos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :erro_pip
echo [OK] Dependencias instaladas.

echo [6/9] Verificando configuracao .env...
if exist ".env" (
    echo [OK] .env ja existe - mantido sem alteracoes.
) else (
    copy ".env.example" ".env" >nul
    echo [OK] .env criado a partir de .env.example. Revise DOCUMENTS_ROOT se necessario.
)

echo [7/9] Testando importacoes, SQLite e FastAPI...
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, pypdf, docx, openpyxl, sqlite3; from app.main import app; print('[OK] Importacoes e aplicacao carregadas.')"
if errorlevel 1 goto :erro_teste

echo [8/9] Executando diagnostico...
echo.
".venv\Scripts\python.exe" scripts\diagnostico.py
set DIAG=%errorlevel%
echo.

echo [9/9] Resultado
if "%DIAG%"=="0" (
    echo [OK] Instalacao concluida. Execute start.bat para abrir o painel em http://127.0.0.1:8000
) else (
    echo [WARNING] Instalacao concluida, mas o diagnostico apontou erros. Veja as mensagens acima.
)
echo.
pause
exit /b 0

:erro_windows
echo [ERRO] Este instalador deve ser executado no Windows.
goto :falha
:erro_python
echo [ERRO] Python nao encontrado no PATH.
echo        Instale o Python 3.10 ou superior em https://www.python.org/downloads/
echo        e marque a opcao "Add python.exe to PATH" durante a instalacao.
goto :falha
:erro_versao
echo [ERRO] E necessario Python 3.10 ou superior.
goto :falha
:erro_venv
echo [ERRO] Nao foi possivel criar o ambiente virtual .venv.
goto :falha
:erro_pip
echo [ERRO] Falha ao instalar as dependencias. Verifique a conexao com a Internet ou o proxy.
goto :falha
:erro_teste
echo [ERRO] A aplicacao nao pode ser carregada. Veja a mensagem acima.
goto :falha
:falha
echo.
echo Instalacao NAO concluida.
pause
exit /b 1
