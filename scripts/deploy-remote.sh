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
export ONYX_DEMO_ROOT="$ROOT"
docker compose \
  --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" \
  -f "$ROOT/docker-compose.witdem-proxy.yml" \
  -f "$ROOT/docker-compose.prod.yml" \
  up -d --build

./scripts/wait-onyx.sh || true

# Proxy may still be minting a self-signed cert for a few seconds after start.
healthy=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 http://127.0.0.1:8501/health >/dev/null \
    && curl -fsS --max-time 5 http://127.0.0.1:8091/health >/dev/null \
    && curl -fsS --max-time 5 http://127.0.0.1:3020/auth/login >/dev/null \
    && curl -fsS --max-time 5 http://127.0.0.1:3021/api/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done
if [[ "$healthy" -ne 1 ]]; then
  echo "deploy-remote: health checks failed" >&2
  exit 1
fi

# Register Document Intake OpenAPI tool + persona wiring (idempotent).
./scripts/register-intake-onyx-tool.sh

echo "deploy-remote: OK (local health checks passed)"
