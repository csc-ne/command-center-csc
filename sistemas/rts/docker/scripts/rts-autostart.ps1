# =========== RTS - REAL TIME SUPPORT ============
# rts-autostart.ps1 — wrapper chamado pelo Task Scheduler
# ================================================
# Sobe o stack RTS no boot da VM Windows. Aguarda o Docker Desktop
# estar pronto antes de rodar "docker compose up -d".
#
# Uso direto (teste manual):
#   powershell -ExecutionPolicy Bypass -File .\rts-autostart.ps1
#
# Agendado via Task Scheduler (ver INSTALL_TASK.ps1).

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
Set-Location $DockerDir

# Log do wrapper — separado dos logs dos containers
$LogFile = Join-Path $DockerDir "autostart.log"
function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$ts] $msg"
    Write-Host "[$ts] $msg"
}

Log "=== rts-autostart iniciando ==="

# ---- Espera o Docker Desktop estar pronto ----
# Na inicialização da VM, o Task Scheduler dispara antes do Docker
# Desktop terminar de subir o engine. Tentamos "docker info" até ele
# responder.
$MaxWaitSec = 180
$WaitedSec  = 0
$SleepSec   = 5

while ($WaitedSec -lt $MaxWaitSec) {
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Log "Docker Engine pronto após ${WaitedSec}s."
            break
        }
    } catch { }
    Log "Aguardando Docker Engine... (${WaitedSec}/${MaxWaitSec}s)"
    Start-Sleep -Seconds $SleepSec
    $WaitedSec += $SleepSec
}

if ($WaitedSec -ge $MaxWaitSec) {
    Log "ERRO: Docker Engine não respondeu em ${MaxWaitSec}s. Abortando."
    exit 1
}

# ---- docker compose up ----
Log "Executando: docker compose up -d"
docker compose -f docker-compose.yml up -d 2>&1 | ForEach-Object { Log $_ }

if ($LASTEXITCODE -eq 0) {
    Log "Stack RTS no ar."
    docker compose -f docker-compose.yml ps 2>&1 | ForEach-Object { Log $_ }
    exit 0
} else {
    Log "ERRO ao subir o stack. Ver logs acima."
    exit 1
}
