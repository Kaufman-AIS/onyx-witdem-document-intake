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

# Onyx nginx resolves upstream IPs at start; after api/web recreate it can
# keep a dead address and serve 502 until restarted.
docker compose \
  --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" \
  -f "$ROOT/docker-compose.witdem-proxy.yml" \
  -f "$ROOT/docker-compose.prod.yml" \
  restart nginx

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
  echo "deploy-remote: health checks failed — retrying nginx restart once" >&2
  docker compose \
    --project-directory "$COMPOSE_DIR" \
    -f "$COMPOSE_DIR/docker-compose.yml" \
    -f "$ROOT/docker-compose.witdem-proxy.yml" \
    -f "$ROOT/docker-compose.prod.yml" \
    restart nginx
  sleep 3
  if ! curl -fsS --max-time 5 http://127.0.0.1:3021/api/health >/dev/null; then
    echo "deploy-remote: health checks failed" >&2
    exit 1
  fi
fi

# Stale Celery locks after api/background recreate leave uploads stuck on
# "Waiting for processing" (Lock held, skipping) until the 30m TTL expires.
if docker ps --format '{{.Names}}' | grep -qx onyx-cache-1; then
  cleared="$(
    docker exec onyx-cache-1 sh -c \
      'redis-cli --scan --pattern "*:da_lock:user_file_processing:*" | xargs -r redis-cli DEL' \
      2>/dev/null || true
  )"
  echo "deploy-remote: cleared stale user-file processing locks (${cleared:-0})"
fi

# Create/reuse Onyx API key for intake file downloads; persist outside empty GitHub secrets.
./scripts/ensure-onyx-api-key.sh "$ROOT/.env"

# Reload intake so it picks up ONYX_API_KEY from .env
export ONYX_DEMO_ROOT="$ROOT"
docker compose \
  --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" \
  -f "$ROOT/docker-compose.witdem-proxy.yml" \
  -f "$ROOT/docker-compose.prod.yml" \
  up -d intake

# Register Document Intake OpenAPI tool + persona wiring (idempotent).
./scripts/register-intake-onyx-tool.sh

echo "deploy-remote: OK (local health checks passed)"
