#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# build.sh — build das imagens rts-core e rts-dashboard
# ================================================
# Uso: bash build.sh [--no-cache]

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$DOCKER_DIR"

EXTRA_ARGS=()
if [ "${1:-}" = "--no-cache" ]; then
    EXTRA_ARGS+=("--no-cache")
fi

echo "[build] Construindo imagens RTS..."
docker compose -f docker-compose.yml build "${EXTRA_ARGS[@]}"
echo "[build] OK. Imagens disponíveis:"
docker images --filter=reference='rts-*' --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}'
