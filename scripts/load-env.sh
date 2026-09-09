#!/usr/bin/env bash
# Source shared credentials. Demo-local .env wins over repo root.
set -a
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
EXAMPLES_ROOT="$(cd "$ROOT/.." && pwd)"

for file in "$REPO_ROOT/.env" "$EXAMPLES_ROOT/.env" "$ROOT/.env"; do
  if [[ -f "$file" ]]; then
    # shellcheck disable=SC1090
    source "$file"
  fi
done
set +a
