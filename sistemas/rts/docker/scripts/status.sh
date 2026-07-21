#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# status.sh — resumo rápido de saúde dos containers
# ================================================

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$DOCKER_DIR"

echo "============================================================"
echo "RTS status — $(date)"
echo "============================================================"

echo ""
echo "[compose ps]"
docker compose -f docker-compose.yml ps

echo ""
echo "[rts-core /status]"
if curl -fsS --max-time 3 http://127.0.0.1:5001/status 2>/dev/null | python3 -m json.tool 2>/dev/null; then
    true
else
    echo "  (sem resposta em :5001/status — container pode estar parado ou ainda subindo)"
fi

echo ""
echo "[rts-dashboard / (HTTP 200?)]"
if curl -fsS -o /dev/null -w "  HTTP %{http_code}\n" --max-time 3 http://127.0.0.1:8080/ 2>/dev/null; then
    true
else
    echo "  (sem resposta em :8080 — container pode estar parado)"
fi

echo ""
echo "[stats (último snapshot)]"
docker stats --no-stream --format \
    'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}' \
    rts-core rts-dashboard 2>/dev/null || true

echo "============================================================"
