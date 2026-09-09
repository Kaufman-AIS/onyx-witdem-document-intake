#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f scripts/load-env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/load-env.sh || true
fi
# Bind all interfaces so Onyx (Docker) can reach the host via host.docker.internal.
exec .venv/bin/uvicorn witdem_onyx_demo.intake.tool_server:app --host 0.0.0.0 --port 8091
