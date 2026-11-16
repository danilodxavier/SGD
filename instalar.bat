@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Instalacao - SAD-GD

echo ============================================================
echo  Instalacao - SAD-GD (Apoio a Decisao e Gestao Documental)
echo  Tudo e instalado dentro desta pasta (ADR-001).
echo ============================================================
echo.

rem Caches de pip, Hugging Face e torch dentro do projeto
set "PIP_CACHE_DIR=%~dp0data\cache\pip"
set "HF_HOME=%~dp0modelos\hf"
set "TORCH_HOME=%~dp0modelos\torch"
set "HF_HUB_DISABLE_TELEMETRY=1"

echo [1/11] Verificando Windows...
ver | findstr /i "Windows" >nul
if errorlevel 1 goto :erro_windows
echo [OK] Windows identificado.

echo [2/11] Verificando Python...
where python >nul 2>nul
if errorlevel 1 goto :erro_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"
if errorlevel 1 goto :erro_versao
for /f "delims=" %%v in ('python --version') do echo [OK] %%v

echo [3/11] Criando ambiente virtual .venv...
if exist ".venv\Scripts\python.exe" (
    echo [OK] Ambiente virtual ja existe.
) else (
    python -m venv .venv
    if errorlevel 1 goto :erro_venv
    echo [OK] Ambiente virtual criado.
)

echo [4/11] Criando diretorios de trabalho...
for %%d in (data\database data\index data\cache data\logs data\reports data\backups data\observabilidade modelos\hf modelos\ollama ferramentas corpus\publico corpus\sintetico avaliacao\golden_set avaliacao\execucoes) do (
    if not exist "%%d" mkdir "%%d"
)
echo [OK] Diretorios criados.

echo [5/11] Instalando dependencias principais...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :erro_pip
echo [OK] Dependencias principais instaladas.

echo [6/11] Instalando PyTorch (GPU NVIDIA quando disponivel)...
where nvidia-smi >nul 2>nul
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q torch
) else (
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
)
if errorlevel 1 goto :erro_pip
".venv\Scripts\python.exe" -c "import torch; print('[OK] torch', torch.__version__, '- GPU:', torch.cuda.is_available())"

echo [7/11] Instalando dependencias de IA, avaliacao, observabilidade e testes...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements-ia.txt -r requirements-avaliacao.txt -r requirements-observabilidade.txt -r requirements-dev.txt
if errorlevel 1 goto :erro_pip
echo [OK] Dependencias de IA instaladas.

echo [8/11] Verificando configuracao .env...
if exist ".env" (
    echo [OK] .env ja existe - mantido sem alteracoes.
) else (
    copy ".env.example" ".env" >nul
    echo [OK] .env criado a partir de .env.example.
)

echo [9/11] Ferramentas locais: Ollama portatil e modelo padrao...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\ollama.ps1" -Acao instalar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\ollama.ps1" -Acao iniciar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\ollama.ps1" -Acao modelo
if not exist "ferramentas\tesseract\tesseract.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sadgd\tesseract.ps1" -Acao instalar
)

echo [10/11] Banco de dados e importacoes...
".venv\Scripts\python.exe" -c "from app.core.database import init_db; init_db(); from app.main import app; print('[OK] Banco migrado e aplicacao carregada.')"
if errorlevel 1 goto :erro_teste

echo [11/11] Executando diagnostico...
echo.
".venv\Scripts\python.exe" scripts\diagnostico.py
set DIAG=%errorlevel%
echo.
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
echo        Instale o Python 3.13 ou superior em https://www.python.org/downloads/
echo        e marque a opcao "Add python.exe to PATH" durante a instalacao.
goto :falha
:erro_versao
echo [ERRO] E necessario Python 3.13 ou superior.
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
