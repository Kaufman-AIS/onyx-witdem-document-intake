#!/usr/bin/env bash
# Ensure Onyx has a service API key for Document Intake and write it to .env.
#
# Idempotent:
# - If ONYX_API_KEY is already set in .env (or secrets/onyx-api-key), keep it.
# - Else create/regenerate named key "witdem-intake-deploy" via Onyx insert_api_key.
#
# Requires: onyx-api_server-1 healthy, python3, docker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"
SECRET_FILE="$ROOT/secrets/onyx-api-key"
KEY_NAME="${ONYX_INTAKE_API_KEY_NAME:-witdem-intake-deploy}"
API_CONTAINER="${ONYX_API_CONTAINER:-onyx-api_server-1}"
OWNER_EMAIL="${ONYX_ADMIN_EMAIL:-}"

mkdir -p "$ROOT/secrets"
chmod 700 "$ROOT/secrets" 2>/dev/null || true

read_existing() {
  if [[ -f "$SECRET_FILE" ]]; then
    local v
    v="$(tr -d '\r\n' <"$SECRET_FILE")"
    if [[ -n "$v" ]]; then
      printf '%s' "$v"
      return 0
    fi
  fi
  if [[ -f "$ENV_FILE" ]]; then
    local line v
    line="$(grep -E '^ONYX_API_KEY=' "$ENV_FILE" | head -n1 || true)"
    v="${line#ONYX_API_KEY=}"
    v="${v%\"}"
    v="${v#\"}"
    if [[ -n "$v" ]]; then
      printf '%s' "$v"
      return 0
    fi
  fi
  return 1
}

upsert_env_key() {
  local key="$1"
  python3 - "$ENV_FILE" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
val = sys.argv[2].replace("\r", "").replace("\n", "")
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, found = [], False
for line in lines:
    if line.startswith("ONYX_API_KEY="):
        out.append(f"ONYX_API_KEY={val}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"ONYX_API_KEY={val}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
path.chmod(0o600)
print(f"updated {path}")
PY
}

EXISTING="$(read_existing || true)"
if [[ -n "${EXISTING:-}" ]]; then
  printf '%s' "$EXISTING" >"$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
  upsert_env_key "$EXISTING"
  echo "ensure-onyx-api-key: reused existing key (len=${#EXISTING})"
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$API_CONTAINER"; then
  echo "ensure-onyx-api-key: missing container $API_CONTAINER" >&2
  exit 1
fi

# Create or regenerate via Onyx internals inside api_server
NEW_KEY="$(
  OWNER_EMAIL="$OWNER_EMAIL" KEY_NAME="$KEY_NAME" docker exec -i -e OWNER_EMAIL -e KEY_NAME "$API_CONTAINER" python - <<'PY'
import os
from sqlalchemy import select

from onyx.db.api_key import insert_api_key, regenerate_api_key
from onyx.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from onyx.db.models import ApiKey, User
from onyx.server.api_key.models import APIKeyArgs

KEY_NAME = os.environ.get("KEY_NAME", "witdem-intake-deploy")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip()

SqlEngine.set_app_name("ensure_onyx_api_key")
SqlEngine.init_engine(pool_size=2, max_overflow=0)

with get_session_with_current_tenant() as db:
    owner = None
    if OWNER_EMAIL:
        owner = db.scalars(select(User).where(User.email == OWNER_EMAIL)).first()
    if owner is None:
        users = list(db.scalars(select(User)).unique().all())
        for u in users:
            email = (u.email or "").lower()
            if (
                email.endswith("@onyx.app")
                or "api_key" in email
                or email.startswith("anonymous")
            ):
                continue
            owner = u
            break
        if owner is None and users:
            owner = users[0]
    if owner is None:
        raise SystemExit(
            "no Onyx user found to own API key — complete admin signup first"
        )

    existing = db.scalars(select(ApiKey).where(ApiKey.name == KEY_NAME)).first()
    if existing is not None:
        desc = regenerate_api_key(db, existing.id)
    else:
        desc = insert_api_key(db, APIKeyArgs(name=KEY_NAME, group_ids=[]), owner.id)

    if not desc.api_key:
        raise SystemExit("API key create/regenerate did not return plaintext key")
    # Markers keep docker/uvicorn logging noise out of the captured secret.
    print("API_KEY_BEGIN")
    print(desc.api_key)
    print("API_KEY_END")
PY
)"
NEW_KEY="$(printf '%s\n' "$NEW_KEY" | awk '/^API_KEY_BEGIN$/{p=1;next} /^API_KEY_END$/{p=0} p' | tr -d '\r' | tail -n1)"

if [[ -z "${NEW_KEY}" ]]; then
  echo "ensure-onyx-api-key: failed to create key" >&2
  exit 1
fi

umask 077
printf '%s' "$NEW_KEY" >"$SECRET_FILE"
chmod 600 "$SECRET_FILE"
upsert_env_key "$NEW_KEY"
echo "ensure-onyx-api-key: created/rotated key name=$KEY_NAME len=${#NEW_KEY}"
echo "ensure-onyx-api-key: stored in $SECRET_FILE and $ENV_FILE"
echo "ensure-onyx-api-key: optionally copy into GitHub Secret ONYX_API_KEY for multi-host deploys"
