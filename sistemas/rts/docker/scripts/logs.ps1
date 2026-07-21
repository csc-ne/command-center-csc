# =========== RTS - REAL TIME SUPPORT ============
# logs.ps1 - streaming de logs (Windows)
# ================================================
# Uso:
#   .\logs.ps1                     # todos os servicos
#   .\logs.ps1 rts-core            # so o core
#   .\logs.ps1 rts-core 500        # ultimas 500 linhas + follow

param(
    [string]$Service = "",
    [int]$Tail = 200
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

if ($Service) {
    docker compose -f docker-compose.yml logs -f --tail=$Tail $Service
} else {
    docker compose -f docker-compose.yml logs -f --tail=$Tail
}
