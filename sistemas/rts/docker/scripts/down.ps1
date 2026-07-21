# =========== RTS - REAL TIME SUPPORT ============
# down.ps1 - derruba containers (Windows)
# ================================================
# Uso:
#   .\down.ps1              # para e remove containers
#   .\down.ps1 -Volumes     # remove tambem os volumes nomeados

param([switch]$Volumes)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

$Extra = @()
if ($Volumes) {
    $Extra += "--volumes"
    Write-Host "[down] Removendo tambem volumes nomeados." -ForegroundColor Yellow
}

docker compose -f docker-compose.yml down @Extra
Write-Host "[down] OK." -ForegroundColor Green
