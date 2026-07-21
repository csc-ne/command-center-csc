# =========== RTS - REAL TIME SUPPORT ============
# build.ps1 - build das imagens (Windows)
# ================================================
# Uso:
#   .\build.ps1             # com cache
#   .\build.ps1 -NoCache    # rebuild do zero

param([switch]$NoCache)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

$Extra = @()
if ($NoCache) { $Extra += "--no-cache" }

Write-Host "[build] Construindo imagens RTS..." -ForegroundColor Cyan
docker compose -f docker-compose.yml build @Extra
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] ERRO no build." -ForegroundColor Red
    exit 1
}

Write-Host "[build] OK. Imagens:" -ForegroundColor Green
docker images --filter "reference=rts-*" --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}`t{{.CreatedSince}}"
