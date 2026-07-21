#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# logs.sh — streaming de logs dos containers
# ================================================
# Uso:
#   bash logs.sh              # todos os serviços (follow)
#   bash logs.sh rts-core     # só o core
#   bash logs.sh rts-dashboard
#   bash logs.sh rts-core 200 # últimas 200 linhas + follow

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$DOCKER_DIR"

SERVICE="${1:-}"
TAIL="${2:-200}"

if [ -n "$SERVICE" ]; then
    exec docker compose -f docker-compose.yml logs -f --tail="$TAIL" "$SERVICE"
else
    exec docker compose -f docker-compose.yml logs -f --tail="$TAIL"
fi
