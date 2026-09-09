#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh"

"$ROOT/scripts/setup-onyx.sh"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
  echo "Set OPENAI_API_KEY in $REPO_ROOT/.env or $ROOT/.env (required for Onyx chat)." >&2
  exit 1
fi

echo "Starting Witdem..."
npx -y witdem@0.2.6 up --no-open

echo "Starting Onyx (this may take several minutes on first pull)..."
COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"
if grep -q '^HOST_PORT=' "$COMPOSE_DIR/.env" 2>/dev/null; then
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' 's|^HOST_PORT=.*|HOST_PORT=13000|' "$COMPOSE_DIR/.env"
  else
    sed -i 's|^HOST_PORT=.*|HOST_PORT=13000|' "$COMPOSE_DIR/.env"
  fi
else
  echo "HOST_PORT=13000" >> "$COMPOSE_DIR/.env"
fi
docker build -t onyx-witdem-proxy:local -f "$ROOT/Dockerfile.proxy" "$ROOT"
docker compose -f "$COMPOSE_DIR/docker-compose.yml" -f "$ROOT/docker-compose.witdem-proxy.yml" up -d

"$ROOT/scripts/wait-onyx.sh"

cat <<EOF

Stack is up.
  Onyx UI:     http://127.0.0.1:3000/auth/login   (via witdem-proxy — HTTPS also works on same port)
  Onyx API:    http://127.0.0.1:3001/api          (scripts / ONYX_API_BASE_URL)
  Witdem:      http://127.0.0.1:8501

Next steps (first time only):
  1. Open http://127.0.0.1:3000/auth/login and complete admin setup
  2. Admin Panel → create an API key with chat + ingestion permissions
  3. Add ONYX_API_KEY to examples/onyx-demo/.env
  4. python scripts/bootstrap-onyx.py
  5. Chat in the Onyx UI — runs appear in Witdem automatically
  6. python run_demo.py  (optional contract regression cases)

EOF
