#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# preflight.sh — checagens antes do build/up
# ================================================
# Valida o ambiente da VM antes de subir os containers:
#   - docker / docker compose instalados
#   - .env presente com as chaves essenciais
#   - serviceAccount.json presente
#   - conectividade com o MySQL do host
#   - timezone do host correto
#
# Uso: bash preflight.sh
# Sai com código != 0 se algo crítico estiver errado.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
ROOT_DIR="$( cd "$DOCKER_DIR/.." && pwd )"

ok()   { printf "\033[32m[OK]\033[0m   %s\n" "$*"; }
warn() { printf "\033[33m[WARN]\033[0m %s\n" "$*"; }
err()  { printf "\033[31m[ERRO]\033[0m %s\n" "$*"; }

ERRORS=0

echo "============================================================"
echo "RTS preflight — $(date)"
echo "Raiz do projeto: $ROOT_DIR"
echo "============================================================"

# ---- 1. Docker ----
if command -v docker >/dev/null 2>&1; then
    ok "docker encontrado: $(docker --version)"
else
    err "docker NÃO está instalado ou não está no PATH."
    ERRORS=$((ERRORS+1))
fi

if docker compose version >/dev/null 2>&1; then
    ok "docker compose (plugin v2) disponível: $(docker compose version --short 2>/dev/null || echo 'ok')"
else
    err "docker compose (plugin v2) não encontrado. Instale com: apt install docker-compose-plugin"
    ERRORS=$((ERRORS+1))
fi

# ---- 2. .env ----
ENV_FILE="$ROOT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    ok ".env encontrado em $ENV_FILE"
    REQUIRED_KEYS=(
        "USERDB" "PSS" "IPDESKTOPDB"
        "USERNAME_DB" "PASSWORD_DB" "HOST_DB" "SCHEMA_DB"
        "DATABASE_URL" "SERVICE_ACCOUNT" "UID"
        "TKWPP" "PHONE_NUMBER_ID"
        "SESSION_SECRET"
    )
    MISSING=()
    for key in "${REQUIRED_KEYS[@]}"; do
        if ! grep -qE "^${key}=" "$ENV_FILE"; then
            MISSING+=("$key")
        fi
    done
    if [ ${#MISSING[@]} -eq 0 ]; then
        ok "Todas as chaves obrigatórias do .env estão presentes."
    else
        err ".env está faltando as chaves: ${MISSING[*]}"
        ERRORS=$((ERRORS+1))
    fi
else
    err ".env NÃO encontrado em $ENV_FILE. Copie de docker/.env.example e preencha."
    ERRORS=$((ERRORS+1))
fi

# ---- 3. serviceAccount.json ----
SA_FILE="$ROOT_DIR/connection/serviceAccount.json"
if [ -f "$SA_FILE" ]; then
    ok "serviceAccount.json encontrado."
    # Checagem mínima de JSON válido
    if python3 -c "import json,sys; json.load(open('$SA_FILE'))" 2>/dev/null; then
        ok "serviceAccount.json é JSON válido."
    else
        warn "serviceAccount.json existe mas não é JSON válido."
    fi
else
    err "serviceAccount.json NÃO encontrado em $SA_FILE."
    echo "       O dashboard Node NÃO sobe sem esse arquivo."
    ERRORS=$((ERRORS+1))
fi

# ---- 4. Conectividade MySQL ----
if [ -f "$ENV_FILE" ]; then
    MYSQL_HOST="$(grep -E '^HOST_DB=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)"
    if [ -n "${MYSQL_HOST:-}" ] && [ "$MYSQL_HOST" != "host.docker.internal" ]; then
        if command -v nc >/dev/null 2>&1; then
            if nc -z -w 2 "$MYSQL_HOST" 3306 2>/dev/null; then
                ok "MySQL ($MYSQL_HOST:3306) responde."
            else
                warn "MySQL ($MYSQL_HOST:3306) não respondeu em 2s. Confira firewall/rede."
            fi
        else
            warn "'nc' (netcat) não instalado — pulando teste de porta MySQL."
        fi
    else
        warn "HOST_DB=host.docker.internal — o teste só roda de dentro do container."
    fi
fi

# ---- 5. Timezone do host ----
HOST_TZ="$(cat /etc/timezone 2>/dev/null || readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || echo 'desconhecido')"
if [ "$HOST_TZ" = "America/Recife" ]; then
    ok "Timezone do host: $HOST_TZ"
else
    warn "Timezone do host: $HOST_TZ (esperado: America/Recife). Os containers forçam TZ internamente, mas convém alinhar."
fi

# ---- 6. Arquivos críticos na raiz ----
CRITICAL_FILES=(
    "main.py" "rts_core.py" "business_hours.py"
    "BD_alertas.py" "alerts_api.py" "whatsapp_api.py"
    "batch_alert_sender.py" "validators.py"
    "token_wpp_manager.py" "refreshing_token.py"
    "connection/server.js" "connection/db.js"
    "package.json"
)
MISSING_FILES=()
for f in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$ROOT_DIR/$f" ]; then
        MISSING_FILES+=("$f")
    fi
done
if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    ok "Todos os arquivos Python/JS críticos estão presentes."
else
    err "Arquivos críticos faltando: ${MISSING_FILES[*]}"
    ERRORS=$((ERRORS+1))
fi

# ---- Resumo ----
echo "============================================================"
if [ $ERRORS -eq 0 ]; then
    ok "Preflight OK — pronto para 'bash build.sh' e 'bash up.sh'."
    exit 0
else
    err "Preflight falhou com $ERRORS erro(s) crítico(s). Corrija antes de subir."
    exit 1
fi
