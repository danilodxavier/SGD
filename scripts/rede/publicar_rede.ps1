<#
.SYNOPSIS
  Publica o SAD-GD na rede interna em https://sistemasad.sema.mt.gov.br (ou desfaz).

.DESCRIPTION
  -Acao status   : mostra configuracao, certificado, DNS, firewall, tarefa de inicio e porta.
  -Acao publicar : (executar como Administrador) backup do .env; APP_HOST=<IP>, APP_PORT=443, ALLOWED_HOSTS,
                   SSL_CERTFILE/SSL_KEYFILE; regra de firewall de entrada TCP 443 apenas para faixas internas;
                   tarefa "SAD-GD" no logon do usuario (inicia Ollama e servidor).
  -Acao remover  : volta ao uso local (127.0.0.1:8000), remove a regra de firewall e a tarefa.

  Pre-requisitos da STI: DNS sistemasad.sema.mt.gov.br -> IP fixo desta maquina; certificado instalado com
  scripts\rede\instalar_certificado.py. Acesso: rede interna + login (perfis do sistema), consultas auditadas.
#>
param(
    [ValidateSet("status", "publicar", "remover")][string]$Acao = "status",
    [string]$Nome = "sistemasad.sema.mt.gov.br",
    [string]$IP = ""
)
$ErrorActionPreference = "Stop"
$Raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Env = Join-Path $Raiz ".env"
$Cert = Join-Path $Raiz "ferramentas\certificados\sistemasad.crt"
$Chave = Join-Path $Raiz "ferramentas\certificados\sistemasad.key"
$Regra = "SAD-GD HTTPS (443)"
$Tarefa = "SAD-GD"
$Faixas = @("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")

function Get-IPRede {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*" -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "169.254*" } | Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $ip) { throw "Nao encontrei o IP da placa Ethernet; informe -IP." }
    return $ip
}

function Set-ChaveEnv([string]$chave, [string]$valor) {
    $linhas = [IO.File]::ReadAllLines($Env, [Text.Encoding]::UTF8)
    $achou = $false
    $novas = foreach ($l in $linhas) {
        if ($l -match "^\s*$([regex]::Escape($chave))\s*=") { $achou = $true; "$chave=$valor" } else { $l }
    }
    if (-not $achou) { $novas = @($novas) + "$chave=$valor" }
    [IO.File]::WriteAllLines($Env, [string[]]$novas, (New-Object Text.UTF8Encoding($false)))
}

function Get-ChaveEnv([string]$chave) {
    $l = [IO.File]::ReadAllLines($Env, [Text.Encoding]::UTF8) | Where-Object { $_ -match "^\s*$([regex]::Escape($chave))\s*=" } |
        Select-Object -Last 1
    if ($l) { return ($l -split "=", 2)[1].Trim() } else { return "" }
}

function Test-Admin {
    return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Status {
    Write-Host "Configuracao (.env): APP_HOST=$(Get-ChaveEnv 'APP_HOST') APP_PORT=$(Get-ChaveEnv 'APP_PORT') ALLOWED_HOSTS=$(Get-ChaveEnv 'ALLOWED_HOSTS')"
    Write-Host "HTTPS: SSL_CERTFILE=$(Get-ChaveEnv 'SSL_CERTFILE')"
    & (Join-Path $Raiz ".venv\Scripts\python.exe") (Join-Path $Raiz "scripts\rede\instalar_certificado.py") --verificar --nome $Nome
    try {
        $dns = (Resolve-DnsName $Nome -Type A -ErrorAction Stop | Where-Object Type -eq "A").IPAddress -join ", "
        Write-Host "DNS: $Nome -> $dns (IP desta maquina: $(Get-IPRede))"
    } catch { Write-Host "DNS: $Nome ainda nao existe (pedir a STI: registro A -> $(Get-IPRede), com IP fixo)" }
    $r = Get-NetFirewallRule -DisplayName $Regra -ErrorAction SilentlyContinue
    Write-Host ("Firewall: " + $(if ($r) { "regra '$Regra' ativa=$($r.Enabled)" } else { "sem regra" }))
    $t = Get-ScheduledTask -TaskName $Tarefa -ErrorAction SilentlyContinue
    Write-Host ("Inicio automatico: " + $(if ($t) { "tarefa '$Tarefa' ($($t.State))" } else { "sem tarefa" }))
    $porta = [int]$(if (Get-ChaveEnv 'APP_PORT') { Get-ChaveEnv 'APP_PORT' } else { 8000 })
    $escuta = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
    Write-Host ("Servidor: " + $(if ($escuta) { "escutando em " + (($escuta | ForEach-Object { "$($_.LocalAddress):$porta" }) -join ", ") } else { "parado (porta $porta)" }))
}

function Backup-Env {
    $dir = Join-Path $Raiz "BACKUP"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $destino = Join-Path $dir ("env_antes_rede_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".bak")
    Copy-Item $Env $destino
    Write-Host "[OK] Backup do .env: $destino"
}

switch ($Acao) {
    "status" { Show-Status; exit 0 }
    "publicar" {
        if (-not (Test-Admin)) { throw "Execute o PowerShell como Administrador (firewall e tarefa de inicio)." }
        if (-not ((Test-Path $Cert) -and (Test-Path $Chave))) {
            throw "Certificado ausente. Instale antes: .venv\Scripts\python.exe scripts\rede\instalar_certificado.py --pfx <arquivo>"
        }
        & (Join-Path $Raiz ".venv\Scripts\python.exe") (Join-Path $Raiz "scripts\rede\instalar_certificado.py") --verificar --nome $Nome
        if ($LASTEXITCODE -ne 0) { throw "Certificado invalido para $Nome." }
        if (-not $IP) { $IP = Get-IPRede }
        Backup-Env
        Set-ChaveEnv "APP_HOST" $IP          # IP especifico: a porta 443 de outro adaptador esta ocupada
        Set-ChaveEnv "APP_PORT" "443"
        Set-ChaveEnv "ALLOWED_HOSTS" "$Nome,$IP"
        Set-ChaveEnv "ALLOWED_CLIENTS" ("127.0.0.1/32,::1/128," + ($Faixas -join ","))
        Set-ChaveEnv "SSL_CERTFILE" $Cert
        Set-ChaveEnv "SSL_KEYFILE" $Chave
        Write-Host "[OK] .env configurado para https://$Nome (escuta em ${IP}:443)"
        Get-NetFirewallRule -DisplayName $Regra -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        New-NetFirewallRule -DisplayName $Regra -Direction Inbound -Protocol TCP -LocalPort 443 -LocalAddress $IP `
            -RemoteAddress $Faixas -Action Allow -Profile Domain, Private | Out-Null
        Write-Host "[OK] Firewall: entrada TCP 443 liberada apenas para a rede interna ($($Faixas -join ', '))"
        $acao = New-ScheduledTaskAction -Execute (Join-Path $Raiz "scripts\rede\iniciar_rede.bat") -WorkingDirectory $Raiz
        $gatilho = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
        $config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        Register-ScheduledTask -TaskName $Tarefa -Action $acao -Trigger $gatilho -Settings $config -Force `
            -Description "SAD-GD: Ollama + servidor HTTPS na rede interna" | Out-Null
        Write-Host "[OK] Inicio automatico: tarefa '$Tarefa' no logon de $env:USERNAME"
        Write-Host "Proximo passo: reinicie o servidor (stop.bat e scripts\rede\iniciar_rede.bat) e teste https://$Nome"
    }
    "remover" {
        if (-not (Test-Admin)) { throw "Execute o PowerShell como Administrador." }
        Backup-Env
        Set-ChaveEnv "APP_HOST" "127.0.0.1"
        Set-ChaveEnv "APP_PORT" "8000"
        Get-NetFirewallRule -DisplayName $Regra -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        Unregister-ScheduledTask -TaskName $Tarefa -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "[OK] Voltou ao uso local (http://127.0.0.1:8000); regra de firewall e tarefa removidas."
    }
}
