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
  python3 - "$COMPOSE_DIR/.env" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = "OPENAI_API_KEY"
raw = os.environ["OPENAI_API_KEY"]
if raw == "" or all(c.isalnum() or c in "-_./:@+%" for c in raw):
    val = raw
else:
    val = '"' + raw.replace("\\", "\\\\").replace('"', '\\"') + '"'

lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, found = [], False
for line in lines:
    if line.startswith(f"{key}="):
        out.append(f"{key}={val}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={val}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
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
