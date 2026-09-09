#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.env}"

required=(OPENAI_API_KEY)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required env: $name" >&2
    exit 1
  fi
done

umask 077
cat >"$OUT" <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
ONYX_API_BASE_URL=${ONYX_API_BASE_URL:-http://api_server:8080}
ONYX_API_KEY=${ONYX_API_KEY:-}
ONYX_PERSONA_ID=${ONYX_PERSONA_ID:-}
WITDEM_ENDPOINT=${WITDEM_ENDPOINT:-http://witdem:4318}
WITDEM_API_KEY=${WITDEM_API_KEY:-}
INTAKE_USE_MEMORY=${INTAKE_USE_MEMORY:-0}
GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS:-/run/secrets/google-sa.json}
GOOGLE_DRIVE_ROOT_FOLDER_ID=${GOOGLE_DRIVE_ROOT_FOLDER_ID:-}
GOOGLE_TASKS_LIST_ID=${GOOGLE_TASKS_LIST_ID:-}
GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID:-}
GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET:-}
GOOGLE_OAUTH_REFRESH_TOKEN=${GOOGLE_OAUTH_REFRESH_TOKEN:-}
EOF

# Onyx upstream compose env (OPENAI key)
COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"
if [[ -d "$COMPOSE_DIR" ]]; then
  if grep -q '^OPENAI_API_KEY=' "$COMPOSE_DIR/.env" 2>/dev/null; then
    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_API_KEY}|" "$COMPOSE_DIR/.env"
  else
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >>"$COMPOSE_DIR/.env"
  fi
  if ! grep -q '^HOST_PORT=' "$COMPOSE_DIR/.env" 2>/dev/null; then
    echo "HOST_PORT=13000" >>"$COMPOSE_DIR/.env"
  fi
fi

echo "wrote $OUT"
