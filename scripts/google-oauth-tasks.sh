#!/usr/bin/env bash
# One-time OAuth login for Google Tasks (company user).
# Requires GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET in .env
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f scripts/load-env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/load-env.sh || true
fi
exec .venv/bin/python -m witdem_onyx_demo.intake.oauth_login
