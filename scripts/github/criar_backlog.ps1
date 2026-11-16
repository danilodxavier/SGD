# Cria labels, milestones e issues no GitHub a partir de docs\projeto\backlog.csv
# e, opcionalmente, adiciona as issues a um GitHub Project.
#
# Pre-requisitos: gh instalado e autenticado (gh auth login), executado na raiz do projeto
# com o remoto 'origin' configurado. Nao grava credenciais.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\github\criar_backlog.ps1 [-ProjectNumber N] [-Owner usuario] [-DryRun]

param(
    [int]$ProjectNumber = 0,
    [string]$Owner = "@me",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$csv = Join-Path $root "docs\projeto\backlog.csv"
$items = Import-Csv -Path $csv -Encoding UTF8

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "[ERRO] gh nao encontrado. Instale com: winget install GitHub.cli" ; exit 1
}
gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "[ERRO] Execute 'gh auth login' primeiro." ; exit 1 }

function Invoke-Gh([string[]]$ghArgs) {
    if ($DryRun) { Write-Host "gh $($ghArgs -join ' ')" ; return "" }
    $out = & gh @ghArgs 2>&1
    return $out
}

# Labels
$labels = @{}
foreach ($i in $items) {
    $labels["fase-$($i.fase)"] = "0E4D92"
    $labels["epico:$($i.epico)"] = "5319E7"
    $labels["prioridade:$($i.prioridade)"] = "D93F0B"
}
foreach ($name in $labels.Keys) {
    Invoke-Gh @("label", "create", $name, "--color", $labels[$name], "--force") | Out-Null
}

# Milestones (uma por fase)
$existing = @()
if (-not $DryRun) { $existing = gh api "repos/{owner}/{repo}/milestones?state=all&per_page=100" --jq ".[].title" }
foreach ($f in ($items | Select-Object -ExpandProperty fase -Unique)) {
    $title = "Fase $f"
    if ($existing -notcontains $title) {
        Invoke-Gh @("api", "repos/{owner}/{repo}/milestones", "-f", "title=$title") | Out-Null
    }
}

# Issues (ignora as que ja existem pelo prefixo do id no titulo)
$open = @()
if (-not $DryRun) { $open = gh issue list --state all --limit 500 --json title --jq ".[].title" }
foreach ($i in $items) {
    $title = "[$($i.id)] $($i.titulo)"
    if ($open | Where-Object { $_ -like "[$($i.id)]*" }) { Write-Host "[OK] ja existe: $title" ; continue }
    $body = "**Epico:** $($i.epico)`n**Fase:** $($i.fase)`n**Prioridade (MoSCoW):** $($i.prioridade)`n**Pontos:** $($i.pontos)`n**Requisitos:** $($i.requisitos)`n`n### Criterio de aceite`n$($i.criterio_aceite)`n`n_Gerado de docs/projeto/backlog.csv_"
    $url = Invoke-Gh @("issue", "create", "--title", $title, "--body", $body,
        "--label", "fase-$($i.fase)", "--label", "epico:$($i.epico)", "--label", "prioridade:$($i.prioridade)",
        "--milestone", "Fase $($i.fase)")
    Write-Host "[OK] criada: $title $url"
    if ($ProjectNumber -gt 0 -and -not $DryRun) {
        gh project item-add $ProjectNumber --owner $Owner --url $url | Out-Null
    }
}
Write-Host "Concluido: $($items.Count) itens processados."
