# =========== RTS - REAL TIME SUPPORT ============
# up.ps1 - sobe containers em modo detached (Windows)
# ================================================
# Uso:
#   .\up.ps1                   # sobe tudo
#   .\up.ps1 rts-core          # sobe apenas um servico

param([string]$Service = "")

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

if ($Service) {
    Write-Host "[up] Subindo servico: $Service" -ForegroundColor Cyan
    docker compose -f docker-compose.yml up -d $Service
} else {
    Write-Host "[up] Subindo todos os servicos em modo detached..." -ForegroundColor Cyan
    docker compose -f docker-compose.yml up -d
}

Write-Host ""
Write-Host "[up] Status:" -ForegroundColor Green
docker compose -f docker-compose.yml ps

# Le porta do dashboard do .env (se sobrescrita)
$DashPort = 8080
$EnvFile = Join-Path (Split-Path -Parent $DockerDir) ".env"
if (Test-Path $EnvFile) {
    $portMatch = (Get-Content $EnvFile | Select-String -Pattern "^RTS_DASHBOARD_PORT=" | Select-Object -First 1)
    if ($portMatch) {
        $DashPort = ($portMatch.ToString() -replace "^RTS_DASHBOARD_PORT=","").Trim("`"'")
    }
}

Write-Host ""
Write-Host "[up] Endpoints locais:" -ForegroundColor Green
Write-Host "  - rts-core status : http://localhost:5001/status"
Write-Host "  - rts-core health : http://localhost:5001/healthz"
Write-Host "  - rts-dashboard   : http://localhost:$DashPort/"
Write-Host ""
Write-Host "[up] Logs em tempo real: .\logs.ps1"
