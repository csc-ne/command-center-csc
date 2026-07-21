# =========== RTS - REAL TIME SUPPORT ============
# INSTALL_TASK.ps1 — instala o Task Scheduler para auto-start (Windows)
# ================================================
# Roda como Admin. Cria uma tarefa chamada "RTS-Autostart" que dispara
# rts-autostart.ps1 no logon do usuário (ou no boot, se preferir).
#
# Uso (PowerShell como Administrador):
#   cd C:\RTS\docker\scripts
#   powershell -ExecutionPolicy Bypass -File .\INSTALL_TASK.ps1
#
# Desinstalar:
#   Unregister-ScheduledTask -TaskName "RTS-Autostart" -Confirm:$false

$ErrorActionPreference = "Stop"

# Verifica admin
$CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal   = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Este script precisa rodar como Administrador." -ForegroundColor Red
    Write-Host "Clique com botão direito no PowerShell → Executar como Administrador."
    exit 1
}

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$AutoScript = Join-Path $ScriptDir "rts-autostart.ps1"

if (-not (Test-Path $AutoScript)) {
    Write-Host "ERRO: rts-autostart.ps1 não encontrado em $ScriptDir" -ForegroundColor Red
    exit 1
}

$TaskName = "RTS-Autostart"

# Remove tarefa anterior se existir
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removendo tarefa anterior '$TaskName'..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Ação: rodar o PowerShell com o script de autostart
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$AutoScript`""

# Trigger: no logon do usuário atual
# (Alternativa: -AtStartup para subir antes do login, mas exige Docker em modo serviço)
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Settings: restart em falha, sem timeout, rodar se perdeu o evento
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

# Principal: rodar como usuário atual, nível mais alto (pode abrir portas, etc.)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERDOMAIN\$env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "Sobe os containers Docker do RTS (rts-core + rts-dashboard) no logon." `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal

Write-Host ""
Write-Host "[OK] Tarefa '$TaskName' criada." -ForegroundColor Green
Write-Host ""
Write-Host "Operação:"
Write-Host "  - Rodar agora         : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  - Ver status          : Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "  - Desabilitar         : Disable-ScheduledTask -TaskName '$TaskName'"
Write-Host "  - Remover             : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
Write-Host "Logs do wrapper: $ScriptDir\..\autostart.log"
