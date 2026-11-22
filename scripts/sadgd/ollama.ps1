# Gestao do Ollama portatil do SAD-GD (ADR-001/004): binario em ferramentas\ollama, modelos em modelos\ollama.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts\sadgd\ollama.ps1 -Acao iniciar|parar|status|instalar|modelo
#   instalar : baixa o Ollama portatil (zip oficial do GitHub) para ferramentas\ollama
#   modelo   : cria o modelo padrao (importa o GGUF do LM Studio, se existir; senao baixa do registro Ollama)

param(
    [ValidateSet("iniciar", "parar", "status", "instalar", "modelo")]
    [string]$Acao = "status",
    [string]$Versao = "v0.40.16",
    [string]$Modelo = "sadgd-qwen2.5-7b",
    [string]$ModeloRegistro = "qwen2.5:7b-instruct-q4_K_M"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Exe = Join-Path $Raiz "ferramentas\ollama\ollama.exe"
$Modelos = Join-Path $Raiz "modelos\ollama"
$Logs = Join-Path $Raiz "data\logs"
$Url = "http://127.0.0.1:11434"

$env:OLLAMA_MODELS = $Modelos
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NOPRUNE = "1"
# Mantem o LLM carregado entre perguntas (padrao do Ollama: 5 min; recarregar custa 10-15 s na 1a pergunta)
if (-not $env:OLLAMA_KEEP_ALIVE) { $env:OLLAMA_KEEP_ALIVE = "12h" }

function Testar-Servidor {
    try { Invoke-RestMethod "$Url/api/version" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

switch ($Acao) {
    "instalar" {
        if (Test-Path $Exe) { Write-Host "[OK] Ollama ja instalado em ferramentas\ollama"; break }
        $destDl = Join-Path $Raiz "ferramentas\downloads"
        New-Item -ItemType Directory -Force $destDl | Out-Null
        $zip = Join-Path $destDl "ollama-windows-amd64.zip"
        Write-Host "Baixando Ollama $Versao (cerca de 1,5 GB)..."
        Invoke-WebRequest "https://github.com/ollama/ollama/releases/download/$Versao/ollama-windows-amd64.zip" -OutFile $zip
        Expand-Archive $zip -DestinationPath (Join-Path $Raiz "ferramentas\ollama") -Force
        Remove-Item $zip -Force
        Write-Host "[OK] Ollama instalado em ferramentas\ollama"
    }
    "iniciar" {
        if (-not (Test-Path $Exe)) { Write-Host "[WARNING] Ollama nao instalado (scripts\sadgd\ollama.ps1 -Acao instalar)."; exit 0 }
        if (Testar-Servidor) { Write-Host "[OK] Ollama ja em execucao."; exit 0 }
        New-Item -ItemType Directory -Force $Modelos, $Logs | Out-Null
        Start-Process -FilePath $Exe -ArgumentList "serve" -WindowStyle Hidden `
            -RedirectStandardError (Join-Path $Logs "ollama.log") -RedirectStandardOutput (Join-Path $Logs "ollama.out.log")
        foreach ($i in 1..40) { if (Testar-Servidor) { Write-Host "[OK] Ollama iniciado em $Url"; exit 0 }; Start-Sleep -Milliseconds 500 }
        Write-Host "[ERRO] Ollama nao respondeu. Veja data\logs\ollama.log"; exit 1
    }
    "parar" {
        $procs = Get-Process -Name "ollama", "llama-server" -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -and $_.Path.StartsWith((Join-Path $Raiz "ferramentas\ollama"), [StringComparison]::OrdinalIgnoreCase) }
        if ($procs) { $procs | Stop-Process -Force; Write-Host "[OK] Ollama do projeto encerrado." } else { Write-Host "[OK] Ollama do projeto nao estava em execucao." }
    }
    "status" {
        if (-not (Test-Path $Exe)) { Write-Host "[WARNING] Ollama nao instalado"; exit 0 }
        if (-not (Testar-Servidor)) { Write-Host "[WARNING] Ollama instalado, mas parado"; exit 0 }
        $tags = Invoke-RestMethod "$Url/api/tags" -TimeoutSec 5
        Write-Host "[OK] Ollama em execucao. Modelos: $(($tags.models | ForEach-Object name) -join ', ')"
    }
    "modelo" {
        if (-not (Testar-Servidor)) { Write-Host "[ERRO] Inicie o Ollama primeiro (-Acao iniciar)."; exit 1 }
        $existentes = (Invoke-RestMethod "$Url/api/tags").models | ForEach-Object name
        if ($existentes -contains "$Modelo`:latest") { Write-Host "[OK] Modelo $Modelo ja existe."; break }
        $gguf = Get-ChildItem (Join-Path $env:USERPROFILE ".lmstudio\models") -Recurse -Filter "Qwen2.5-7B-Instruct-Q4_K_M.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
        $mf = Join-Path $Raiz "data\cache\Modelfile.$Modelo"
        New-Item -ItemType Directory -Force (Split-Path $mf) | Out-Null
        if ($gguf) {
            Write-Host "Importando GGUF do LM Studio: $($gguf.FullName)"
            $origem = $gguf.FullName
        } else {
            Write-Host "Baixando $ModeloRegistro do registro Ollama (cerca de 4,7 GB)..."
            & $Exe pull $ModeloRegistro
            $origem = $ModeloRegistro
        }
        @("FROM $origem", "PARAMETER temperature 0", "PARAMETER num_ctx 8192") | Set-Content -Encoding ascii $mf
        & $Exe create $Modelo -f $mf
        Write-Host "[OK] Modelo $Modelo criado em modelos\ollama"
    }
}
