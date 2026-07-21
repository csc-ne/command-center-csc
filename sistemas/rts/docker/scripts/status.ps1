# =========== RTS - REAL TIME SUPPORT ============
# status.ps1 - snapshot de saude (Windows)
# ================================================
# Escrito sem acentos: PowerShell 5.1 le .ps1 como ANSI por padrao
# e UTF-8 sem BOM quebra o parser em caracteres especiais.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

Write-Host "============================================================"
Write-Host "RTS status - $(Get-Date)"
Write-Host "============================================================"

Write-Host ""
Write-Host "[compose ps]" -ForegroundColor Cyan
docker compose -f docker-compose.yml ps

Write-Host ""
Write-Host "[rts-core /status]" -ForegroundColor Cyan
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:5001/status" -TimeoutSec 3 -ErrorAction Stop
    $resp | ConvertTo-Json -Depth 5
} catch {
    Write-Host "  (sem resposta em :5001/status - container pode estar parado ou subindo)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[rts-dashboard / (HTTP)]" -ForegroundColor Cyan

# Porta do dashboard pode ter sido trocada via RTS_DASHBOARD_PORT no .env
$DashPort = 8080
$EnvFile = Join-Path (Split-Path -Parent $DockerDir) ".env"
if (Test-Path $EnvFile) {
    $portMatch = (Get-Content $EnvFile | Select-String -Pattern "^RTS_DASHBOARD_PORT=" | Select-Object -First 1)
    if ($portMatch) {
        $DashPort = ($portMatch.ToString() -replace "^RTS_DASHBOARD_PORT=","").Trim("`"'")
    }
}
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$DashPort/" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    Write-Host "  HTTP $($resp.StatusCode) (porta $DashPort)"
} catch {
    Write-Host "  (sem resposta em :$DashPort - container pode estar parado)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[stats (snapshot)]" -ForegroundColor Cyan
docker stats --no-stream --format "table {{.Name}}`t{{.CPUPerc}}`t{{.MemUsage}}`t{{.NetIO}}" rts-core rts-dashboard 2>$null

Write-Host "============================================================"
