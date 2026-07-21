#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# up.sh — sobe rts-core + rts-dashboard em modo detached
# ================================================
# Uso:
#   bash up.sh               # sobe tudo
#   bash up.sh rts-core      # sobe só o core
#   bash up.sh rts-dashboard # sobe só o dashboard

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$DOCKER_DIR"

SERVICE="${1:-}"
if [ -n "$SERVICE" ]; then
    echo "[up] Subindo serviço: $SERVICE"
    docker compose -f docker-compose.yml up -d "$SERVICE"
else
    echo "[up] Subindo todos os serviços em modo detached..."
    docker compose -f docker-compose.yml up -d
fi

echo ""
echo "[up] Status dos containers:"
docker compose -f docker-compose.yml ps

echo ""
echo "[up] Endpoints locais:"
echo "  - rts-core status : http://localhost:5001/status"
echo "  - rts-core health : http://localhost:5001/healthz"
echo "  - rts-dashboard   : http://localhost:8080/"
echo ""

# ─── Firebase Functions Deploy ────────────────────────────────────────────────
# Executa firebase deploy --only functions apos subir os containers.
# O resultado e logado em logs/firebase_deploy.log para visibilidade no painel.
RTS_ROOT="$( cd "$DOCKER_DIR/.." && pwd )"
FIREBASE_LOG="$RTS_ROOT/logs/firebase_deploy.log"
mkdir -p "$RTS_ROOT/logs"

echo "[up] Executando firebase deploy --only functions..."
echo "=== Firebase Deploy — $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$FIREBASE_LOG"

if command -v firebase &>/dev/null; then
    cd "$RTS_ROOT"
    if firebase deploy --only functions --project rts-real-time-support-6ec6b 2>&1 | tee -a "$FIREBASE_LOG"; then
        echo "[up] Firebase deploy concluido com sucesso."
        echo "STATUS: SUCESSO — $(date '+%H:%M:%S')" >> "$FIREBASE_LOG"
    else
        echo "[up] AVISO: Firebase deploy falhou. Verifique $FIREBASE_LOG"
        echo "STATUS: FALHA — $(date '+%H:%M:%S')" >> "$FIREBASE_LOG"
    fi
    echo "---" >> "$FIREBASE_LOG"
    cd "$DOCKER_DIR"
else
    echo "[up] AVISO: firebase-tools nao encontrado. Instale com: npm install -g firebase-tools"
    echo "STATUS: SKIP — firebase-tools nao instalado — $(date '+%H:%M:%S')" >> "$FIREBASE_LOG"
fi

echo ""
echo "[up] Logs em tempo real: bash logs.sh"
