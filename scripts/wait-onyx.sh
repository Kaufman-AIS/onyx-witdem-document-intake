#!/usr/bin/env bash
set -euo pipefail
BASE="${ONYX_API_BASE_URL:-http://127.0.0.1:3001/api}"
BASE="${BASE%/}"

candidates=(
  "$BASE/health"
  "$BASE/healthcheck"
  "http://127.0.0.1:3001/api/health"
  "http://127.0.0.1:3001"
  "http://127.0.0.1:3000/auth/login"
  "https://127.0.0.1:3000/api/health"
  "https://127.0.0.1:3000"
)

for _ in $(seq 1 120); do
  for url in "${candidates[@]}"; do
    if [[ "$url" == https://* ]]; then
      if curl -ksf "$url" >/dev/null 2>&1; then
        echo "Onyx reachable at $url"
        exit 0
      fi
    elif curl -sf "$url" >/dev/null 2>&1; then
      echo "Onyx reachable at $url"
      exit 0
    fi
  done
  sleep 5
done

echo "Onyx did not become reachable within 10 minutes." >&2
echo "Check: docker compose -f .onyx-upstream/deployment/docker_compose/docker-compose.yml logs" >&2
exit 1
