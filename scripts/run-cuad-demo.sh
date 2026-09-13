#!/usr/bin/env bash
set -euo pipefail

CUAD_DIR="${CUAD_DIR:-/home/deploy/haystack-cuad-contract-review}"
WITDEM_ENDPOINT="${WITDEM_ENDPOINT:-http://127.0.0.1:4318}"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8501}"
SHOWCASE_PDF="${SHOWCASE_PDF:-output/showcase/scanned-vendor-saas.pdf}"
SHOWCASE_TIMEOUT="${SHOWCASE_TIMEOUT:-300}"

if ! curl -fsS "${WITDEM_ENDPOINT%/}/readiness" >/dev/null; then
  echo "Witdem receiver not ready at ${WITDEM_ENDPOINT%/}/readiness" >&2
  exit 1
fi

if [[ ! -d "$CUAD_DIR" ]]; then
  echo "CUAD checkout missing: $CUAD_DIR" >&2
  echo "Clone: git clone https://github.com/ebrahimisoheil/haystack-cuad-contract-review.git $CUAD_DIR" >&2
  exit 1
fi

cd "$CUAD_DIR"

if [[ ! -f .env ]]; then
  echo "Missing $CUAD_DIR/.env (copy from .env.example and add provider keys)" >&2
  exit 1
fi

for key in OPENAI_API_KEY MISTRAL_API_KEY DEEPSEEK_API_KEY VOYAGE_API_KEY; do
  if ! grep -Eq "^${key}=.+" .env; then
    echo "Required key missing or empty in .env: $key" >&2
    exit 1
  fi
done

export WITDEM_ENDPOINT
export CONTRACT_REVIEW_MODE=live

if [[ ! -f "$SHOWCASE_PDF" ]]; then
  echo "Creating showcase scanned PDF at $SHOWCASE_PDF ..."
  uv run --extra dev python examples/create_showcase_scan.py --output "$SHOWCASE_PDF"
fi

echo "Running live CUAD showcase → Witdem ${WITDEM_ENDPOINT} (dashboard ${DASHBOARD_URL})"
uv run contract-review-showcase "$SHOWCASE_PDF" \
  --dashboard-url "$DASHBOARD_URL" \
  --timeout "$SHOWCASE_TIMEOUT"

echo
echo "Open https://demo.witdem.com and look for service haystack-cuad-contract-review"
