#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/setup-onyx.sh
./scripts/render-env-from-github.sh "$ROOT/.env"

# Optional LLM usage patch (ignore if already applied)
if [[ -f patches/onyx-llm-usage.patch ]]; then
  git -C .onyx-upstream apply --check patches/onyx-llm-usage.patch 2>/dev/null \
    && git -C .onyx-upstream apply patches/onyx-llm-usage.patch \
    || echo "onyx-llm-usage.patch already applied or not applicable"
fi

docker compose -f docker-compose.witdem.yml up -d

COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"
docker compose \
  -f "$COMPOSE_DIR/docker-compose.yml" \
  -f "$ROOT/docker-compose.witdem-proxy.yml" \
  -f "$ROOT/docker-compose.prod.yml" \
  up -d --build

./scripts/wait-onyx.sh || true

curl -fsS --max-time 10 http://127.0.0.1:8501/health >/dev/null
curl -fsS --max-time 10 http://127.0.0.1:8091/health >/dev/null
curl -fsS --max-time 10 http://127.0.0.1:3000/ >/dev/null
echo "deploy-remote: OK (local health checks passed)"
