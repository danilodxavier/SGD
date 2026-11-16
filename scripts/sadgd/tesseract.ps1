# Tesseract portatil do SAD-GD (ADR-007) em ferramentas\tesseract, com idioma portugues (tessdata_best).
#
# O instalador oficial (UB Mannheim) ignora a pasta de destino e instala em "C:\Program Files\Tesseract-OCR".
# Por isso o script: instala silenciosamente, COPIA para ferramentas\tesseract e DESINSTALA do sistema,
# deixando o computador como estava. Requer permissao de administrador apenas durante a instalacao temporaria.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts\sadgd\tesseract.ps1 [-Acao instalar|status]

param(
    [ValidateSet("instalar", "status")]
    [string]$Acao = "status",
    [string]$Versao = "5.4.0.20240606",
    [string]$Sha256 = "C885FFF6998E0608BA4BB8AB51436E1C6775C2BAFC2559A19B423E18678B60C9"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Destino = Join-Path $Raiz "ferramentas\tesseract"
$Exe = Join-Path $Destino "tesseract.exe"
$Sistema = "C:\Program Files\Tesseract-OCR"

if ($Acao -eq "status") {
    if (Test-Path $Exe) {
        $langs = (& $Exe --list-langs 2>&1 | Select-Object -Skip 1) -join ", "
        Write-Host "[OK] Tesseract em ferramentas\tesseract (idiomas: $langs)"
    } else { Write-Host "[WARNING] Tesseract nao instalado em ferramentas\tesseract" }
    exit 0
}

if (Test-Path $Exe) { Write-Host "[OK] Tesseract ja instalado em ferramentas\tesseract"; exit 0 }
if (Test-Path "$Sistema\tesseract.exe") {
    Write-Host "[ERRO] Ja existe um Tesseract em $Sistema. Para nao alterar uma instalacao existente,"
    Write-Host "       copie manualmente a pasta para ferramentas\tesseract."
    exit 1
}

$downloads = Join-Path $Raiz "ferramentas\downloads"
New-Item -ItemType Directory -Force $downloads | Out-Null
$instalador = Join-Path $downloads "tesseract-setup-$Versao.exe"
Write-Host "Baixando instalador do Tesseract $Versao..."
Invoke-WebRequest "https://github.com/UB-Mannheim/tesseract/releases/download/v$Versao/tesseract-ocr-w64-setup-$Versao.exe" -OutFile $instalador
if ((Get-FileHash $instalador -Algorithm SHA256).Hash -ne $Sha256) {
    Remove-Item $instalador -Force
    Write-Host "[ERRO] Hash SHA-256 do instalador nao confere. Download descartado."; exit 1
}

Write-Host "Instalacao temporaria (sera removida em seguida)..."
$p = Start-Process $instalador -ArgumentList "/S" -Wait -PassThru
if ($p.ExitCode -ne 0 -or -not (Test-Path "$Sistema\tesseract.exe")) {
    Write-Host "[ERRO] Instalacao falhou (codigo $($p.ExitCode)). Execute como administrador."; exit 1
}
New-Item -ItemType Directory -Force $Destino | Out-Null
Copy-Item "$Sistema\*" $Destino -Recurse -Force
Remove-Item (Join-Path $Destino "tesseract-uninstall.exe") -ErrorAction SilentlyContinue
Start-Process "$Sistema\tesseract-uninstall.exe" -ArgumentList "/S" -Wait | Out-Null
foreach ($i in 1..20) { if (-not (Test-Path $Sistema)) { break }; Start-Sleep 1 }
Remove-Item $instalador -Force

Write-Host "Baixando modelo de idioma portugues (tessdata_best)..."
Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata_best/raw/main/por.traineddata" -OutFile (Join-Path $Destino "tessdata\por.traineddata")

& $Exe --version 2>&1 | Select-Object -First 1
if (Test-Path $Sistema) { Write-Host "[WARNING] A pasta $Sistema ainda existe; remova-a manualmente." }
Write-Host "[OK] Tesseract instalado em ferramentas\tesseract"
