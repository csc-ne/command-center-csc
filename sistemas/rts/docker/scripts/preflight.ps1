# =========== RTS - REAL TIME SUPPORT ============
# preflight.ps1 - checagens antes do build/up (Windows)
# ================================================
# Escrito sem acentos de proposito: PowerShell 5.1 le arquivos .ps1
# como ANSI por padrao. Salvar em UTF-8 sem BOM quebra o parser em
# caracteres como i-acento, c-cedilha, a-til.
#
# Uso:
#   cd C:\RTS\docker\scripts
#   powershell -ExecutionPolicy Bypass -File .\preflight.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir
$RootDir   = Split-Path -Parent $DockerDir

function Ok   ($m) { Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err  ($m) { Write-Host "[ERRO] $m" -ForegroundColor Red }

$Errors = 0

Write-Host "============================================================"
Write-Host "RTS preflight (Windows) - $(Get-Date)"
Write-Host "Raiz do projeto: $RootDir"
Write-Host "============================================================"

# ---- 1. Docker ----
try {
    $dockerVer = docker --version 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "docker encontrado: $dockerVer" }
    else { Err "docker nao responde. Docker Desktop esta rodando?"; $Errors++ }
} catch {
    Err "docker nao esta no PATH. Instale o Docker Desktop for Windows."
    $Errors++
}

try {
    $composeVer = docker compose version --short 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "docker compose v2 disponivel: $composeVer" }
    else { Err "docker compose v2 nao encontrado."; $Errors++ }
} catch {
    Err "docker compose v2 nao encontrado."
    $Errors++
}

# ---- 2. .env ----
$EnvFile = Join-Path $RootDir ".env"
if (Test-Path $EnvFile) {
    Ok ".env encontrado em $EnvFile"
    $RequiredKeys = @(
        "USERDB","PSS","IPDESKTOPDB",
        "USERNAME_DB","PASSWORD_DB","HOST_DB","SCHEMA_DB",
        "DATABASE_URL","SERVICE_ACCOUNT","UID",
        "TKWPP","PHONE_NUMBER_ID","SESSION_SECRET"
    )
    $EnvContent = Get-Content $EnvFile
    $Missing = @()
    foreach ($key in $RequiredKeys) {
        if (-not ($EnvContent | Select-String -Pattern "^$key=" -Quiet)) {
            $Missing += $key
        }
    }
    if ($Missing.Count -eq 0) {
        Ok "Todas as chaves obrigatorias do .env estao presentes."
    } else {
        Err ".env esta faltando: $($Missing -join ', ')"
        $Errors++
    }
} else {
    Err ".env NAO encontrado em $EnvFile. Copie de docker/.env.vm (ou .env.example)."
    $Errors++
}

# ---- 3. serviceAccount.json ----
$SaFile = Join-Path $RootDir "connection\serviceAccount.json"
if (Test-Path $SaFile) {
    Ok "serviceAccount.json encontrado."
    try {
        Get-Content $SaFile -Raw | ConvertFrom-Json | Out-Null
        Ok "serviceAccount.json e JSON valido."
    } catch {
        Warn "serviceAccount.json existe mas nao e JSON valido."
    }
} else {
    Err "serviceAccount.json NAO encontrado em $SaFile."
    Write-Host "       O dashboard Node NAO sobe sem esse arquivo."
    $Errors++
}

# ---- 4. Conectividade MySQL ----
if (Test-Path $EnvFile) {
    $HostDbMatch = (Get-Content $EnvFile | Select-String -Pattern "^HOST_DB=" | Select-Object -First 1)
    if ($HostDbMatch) {
        $HostDb = ($HostDbMatch.ToString() -replace "^HOST_DB=","").Trim("`"'")
        if ($HostDb -and $HostDb -ne "host.docker.internal") {
            $testConn = Test-NetConnection -ComputerName $HostDb -Port 3306 -WarningAction SilentlyContinue -InformationLevel Quiet
            if ($testConn) { Ok "MySQL ($HostDb`:3306) responde." }
            else { Warn "MySQL ($HostDb`:3306) nao responde. Confira firewall/rede." }
        } else {
            Warn "HOST_DB=host.docker.internal - teste de porta so roda de dentro do container."
        }
    }
}

# ---- 5. Timezone ----
$tz = (Get-TimeZone).Id
if ($tz -match "America" -or $tz -match "Recife" -or $tz -match "Sao_Paulo" -or $tz -match "Brasilia") {
    Ok "Timezone do host: $tz (dentro do Brasil)"
} else {
    Warn "Timezone do host: $tz. Os containers forcam America/Recife internamente, mas convem alinhar."
}

# ---- 6. Arquivos criticos ----
$CriticalFiles = @(
    "main.py","rts_core.py","business_hours.py",
    "BD_alertas.py","alerts_api.py","whatsapp_api.py",
    "batch_alert_sender.py","validators.py",
    "token_wpp_manager.py",
    "connection\server.js","connection\db.js",
    "package.json"
)
$MissingFiles = @()
foreach ($f in $CriticalFiles) {
    if (-not (Test-Path (Join-Path $RootDir $f))) {
        $MissingFiles += $f
    }
}
if ($MissingFiles.Count -eq 0) {
    Ok "Todos os arquivos Python/JS criticos estao presentes."
} else {
    $listMissing = $MissingFiles -join ', '
    Err ("Arquivos criticos faltando: " + $listMissing)
    $Errors++
}

# ---- 7. docker-compose.yml monta .env como volume ----
# rts_core.py faz sys.exit(2) se /app/.env nao existe (checagem explicita
# em rts_core.py linhas 49-55). env_file injeta variaveis mas nao cria arquivo.
$ComposeFile = Join-Path $DockerDir "docker-compose.yml"
if (Test-Path $ComposeFile) {
    $composeContent = Get-Content $ComposeFile -Raw
    if ($composeContent -match "\.env:/app/\.env") {
        Ok "docker-compose.yml monta .env como volume (exigido por rts_core.py)."
    } else {
        Err "docker-compose.yml NAO monta .env como volume. rts_core.py vai crashar com exit 2."
        Write-Host "       Adicione em volumes: - ../.env:/app/.env:ro"
        $Errors++
    }
}

# ---- 8. .dockerignore nao bloqueando a pasta docker/ ----
$DockerIgnore = Join-Path $RootDir ".dockerignore"
if (Test-Path $DockerIgnore) {
    $diContent = Get-Content $DockerIgnore -Raw
    $bareDocker = ($diContent -match "(?m)^\s*docker/\s*$")
    $hasKeep    = ($diContent -match "!docker/Dockerfile") -and ($diContent -match "!docker/requirements.docker.txt")
    if ($bareDocker -and -not $hasKeep) {
        Err ".dockerignore bloqueia a pasta docker/ inteira - o build nao encontrara Dockerfile/requirements."
        Write-Host "       Corrija trocando 'docker/' por 'docker/*' com excecoes para Dockerfile.* e requirements.docker.txt"
        $Errors++
    } else {
        Ok ".dockerignore nao esta bloqueando arquivos de build."
    }
}

# ---- Resumo ----
Write-Host "============================================================"
if ($Errors -eq 0) {
    Ok "Preflight OK - rode: .\build.ps1 e depois .\up.ps1"
    exit 0
} else {
    Err "Preflight falhou com $Errors erro(s). Corrija antes de subir."
    exit 1
}
