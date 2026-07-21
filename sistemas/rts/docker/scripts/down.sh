#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# down.sh — derruba containers (preserva imagens e volumes)
# ================================================
# Uso:
#   bash down.sh            # para e remove containers
#   bash down.sh --volumes  # remove TAMBÉM os volumes nomeados (se existirem)

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$DOCKER_DIR"

EXTRA_ARGS=()
if [ "${1:-}" = "--volumes" ]; then
    EXTRA_ARGS+=("--volumes")
    echo "[down] Também removendo volumes nomeados."
fi

docker compose -f docker-compose.yml down "${EXTRA_ARGS[@]}"
echo "[down] OK."
