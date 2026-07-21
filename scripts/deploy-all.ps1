# ================================================================
# deploy-all.ps1 — sobe todos os containers na VM 192.168.0.106
# ================================================================
# Ordem obrigatoria: portal primeiro (emite JWT usado pelos satelites).
# ================================================================

$ErrorActionPreference = "Stop"
$EnvFile = "C:\env\.env"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $EnvFile)) {
    Write-Host "ERRO: $EnvFile nao encontrado. Crie o .env central antes de rodar." -ForegroundColor Red
    exit 1
}

function Up($relPath, $composeFile) {
    Push-Location (Join-Path $RepoRoot $relPath)
    Write-Host "`n>>> $relPath" -ForegroundColor Cyan
    docker compose --env-file $EnvFile -f $composeFile up -d --build
    Pop-Location
}

# 1. Command Center (SSO — outros dependem)
Up "sistemas\portal\docker" "docker-compose.prod.yml"

# 2. Sub-dashboards do portal
Up "sistemas\portal\csc-dashboard\docker" "docker-compose.yml"
Up "sistemas\portal\dfa-dashboard\docker" "docker-compose.yml"
Up "sistemas\portal\psi-dashboard\docker" "docker-compose.yml"

# 3. Sistemas satelites
Up "sistemas\rts\docker" "docker-compose.yml"
Up "sistemas\rta\docker" "docker-compose.yml"
Up "sistemas\rda\docker" "docker-compose.yml"
Up "sistemas\rca\docker" "docker-compose.yml"
Up "sistemas\fleet-intelligence" "docker-compose.yml"

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "Deploy concluido." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Sort-Object
