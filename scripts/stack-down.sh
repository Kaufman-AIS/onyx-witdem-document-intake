#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"

if [[ -f "$COMPOSE_DIR/docker-compose.yml" ]]; then
  docker compose -f "$COMPOSE_DIR/docker-compose.yml" -f "$ROOT/docker-compose.witdem-proxy.yml" down 2>/dev/null || true
fi

npx -y witdem@0.2.6 down 2>/dev/null || true
echo "Stack stopped."
