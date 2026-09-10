#!/usr/bin/env bash
# Ensure Document Intake can download the admin user's chat uploads.
#
# Onyx service-account API keys (prefix on_/dn_) authenticate as a separate
# SERVICE_ACCOUNT user. That identity gets 403 on /user/files/recent without
# group grants, and even with admin still cannot read another user's files
# (ownership check on /chat/file → 404). Intake needs a Personal Access Token
# (prefix onyx_pat_) owned by the real admin user who uploads PDFs.
#
# Idempotent:
# - Reuse secrets/onyx-api-key or .env when value is already an onyx_pat_*.
# - Otherwise create/rotate PAT named witdem-intake-deploy for the admin user.
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

is_user_pat() {
  [[ "${1:-}" == onyx_pat_* ]]
}

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
if [[ -n "${EXISTING:-}" ]] && is_user_pat "$EXISTING"; then
  printf '%s' "$EXISTING" >"$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
  upsert_env_key "$EXISTING"
  echo "ensure-onyx-api-key: reused existing user PAT (len=${#EXISTING})"
  exit 0
fi

if [[ -n "${EXISTING:-}" ]]; then
  echo "ensure-onyx-api-key: replacing non-PAT credential (service API keys cannot read user uploads)" >&2
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$API_CONTAINER"; then
  echo "ensure-onyx-api-key: missing container $API_CONTAINER" >&2
  exit 1
fi

# Create/rotate a user PAT via Onyx internals inside api_server
NEW_KEY="$(
  OWNER_EMAIL="$OWNER_EMAIL" KEY_NAME="$KEY_NAME" docker exec -i -e OWNER_EMAIL -e KEY_NAME "$API_CONTAINER" python - <<'PY'
import os
from datetime import datetime, timezone

from sqlalchemy import select

from onyx.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from onyx.db.models import PersonalAccessToken, User
from onyx.db.pat import create_pat

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
            "no Onyx user found to own PAT — complete admin signup first"
        )

    # Revoke prior deploy PATs with the same name (plaintext cannot be recovered).
    now = datetime.now(timezone.utc)
    for old in db.scalars(
        select(PersonalAccessToken).where(
            PersonalAccessToken.user_id == owner.id,
            PersonalAccessToken.name == KEY_NAME,
        )
    ).all():
        if old.expires_at is None or old.expires_at > now:
            old.expires_at = now
            old.is_revoked = True

    _row, raw = create_pat(
        db_session=db,
        user_id=owner.id,
        name=KEY_NAME,
        expiration_days=None,
        scopes=None,
    )
    db.commit()

    if not raw.startswith("onyx_pat_"):
        raise SystemExit(f"unexpected PAT format: {raw[:12]!r}")
    print("API_KEY_BEGIN")
    print(raw)
    print("API_KEY_END")
PY
)"
NEW_KEY="$(printf '%s\n' "$NEW_KEY" | awk '/^API_KEY_BEGIN$/{p=1;next} /^API_KEY_END$/{p=0} p' | tr -d '\r' | tail -n1)"

if [[ -z "${NEW_KEY}" ]] || ! is_user_pat "$NEW_KEY"; then
  echo "ensure-onyx-api-key: failed to create user PAT" >&2
  exit 1
fi

umask 077
printf '%s' "$NEW_KEY" >"$SECRET_FILE"
chmod 600 "$SECRET_FILE"
upsert_env_key "$NEW_KEY"
echo "ensure-onyx-api-key: created/rotated user PAT name=$KEY_NAME len=${#NEW_KEY}"
echo "ensure-onyx-api-key: stored in $SECRET_FILE and $ENV_FILE"
echo "ensure-onyx-api-key: optionally copy into GitHub Secret ONYX_API_KEY for multi-host deploys"
