#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh"
UPSTREAM="$ROOT/.onyx-upstream"
COMPOSE_DIR="$UPSTREAM/deployment/docker_compose"

if [[ ! -d "$UPSTREAM/.git" ]]; then
  echo "Cloning onyx-dot-app/onyx (shallow)..."
  git clone --depth 1 https://github.com/onyx-dot-app/onyx.git "$UPSTREAM"
fi

if [[ ! -f "$COMPOSE_DIR/.env" ]]; then
  if [[ -f "$COMPOSE_DIR/env.template" ]]; then
    cp "$COMPOSE_DIR/env.template" "$COMPOSE_DIR/.env"
  else
    cp "$ROOT/onyx.env.example" "$COMPOSE_DIR/.env"
  fi
  echo "Created $COMPOSE_DIR/.env"
fi

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  if grep -q '^OPENAI_API_KEY=' "$COMPOSE_DIR/.env" 2>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_API_KEY}|" "$COMPOSE_DIR/.env"
    else
      sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_API_KEY}|" "$COMPOSE_DIR/.env"
    fi
  else
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> "$COMPOSE_DIR/.env"
  fi
fi

if grep -q '^USER_AUTH_SECRET=""$' "$COMPOSE_DIR/.env" 2>/dev/null || grep -q '^USER_AUTH_SECRET=$' "$COMPOSE_DIR/.env" 2>/dev/null; then
  secret="$(openssl rand -hex 32)"
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|^USER_AUTH_SECRET=.*|USER_AUTH_SECRET=\"${secret}\"|" "$COMPOSE_DIR/.env"
  else
    sed -i "s|^USER_AUTH_SECRET=.*|USER_AUTH_SECRET=\"${secret}\"|" "$COMPOSE_DIR/.env"
  fi
  echo "Generated USER_AUTH_SECRET in $COMPOSE_DIR/.env"
fi

echo "Onyx upstream ready: $COMPOSE_DIR"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
echo "Set OPENAI_API_KEY in $REPO_ROOT/.env before stack-up."
