# ================================================================
# stop-all.ps1 — derruba todos os containers
# ================================================================

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Down($relPath, $composeFile) {
    Push-Location (Join-Path $RepoRoot $relPath)
    Write-Host "`n>>> $relPath" -ForegroundColor Cyan
    docker compose -f $composeFile down
    Pop-Location
}

# Ordem inversa do deploy: satelites primeiro, portal por ultimo
Down "sistemas\fleet-intelligence" "docker-compose.yml"
Down "sistemas\rca\docker" "docker-compose.yml"
Down "sistemas\rda\docker" "docker-compose.yml"
Down "sistemas\rta\docker" "docker-compose.yml"
Down "sistemas\rts\docker" "docker-compose.yml"
Down "sistemas\portal\psi-dashboard\docker" "docker-compose.yml"
Down "sistemas\portal\dfa-dashboard\docker" "docker-compose.yml"
Down "sistemas\portal\csc-dashboard\docker" "docker-compose.yml"
Down "sistemas\portal\docker" "docker-compose.prod.yml"

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "Stop concluido." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
