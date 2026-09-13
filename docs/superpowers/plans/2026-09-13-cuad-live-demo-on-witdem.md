# CUAD Live Demo on demo.witdem.com Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the live Haystack CUAD contract-review showcase against the Hostinger Witdem receiver so executions appear on https://demo.witdem.com via a repeatable host script.

**Architecture:** Keep CUAD as a host checkout at `/home/deploy/haystack-cuad-contract-review`. Add `scripts/run-cuad-demo.sh` in `onyx-witdem-document-intake` that forces `WITDEM_ENDPOINT=http://127.0.0.1:4318` and `CONTRACT_REVIEW_MODE=live`, generates the scanned showcase PDF if missing, and invokes `contract-review-showcase`. Document operator steps in `docs/deploy-hostinger.md`. Do not expose OTLP publicly and do not recreate Onyx.

**Tech Stack:** bash, uv, haystack-cuad-contract-review CLI, existing Witdem Docker stack on VPS (`:4318`, `:8501`)

**Spec:** `docs/superpowers/specs/2026-09-13-cuad-live-demo-on-witdem-design.md`

---

## File map

| File | Responsibility |
| --- | --- |
| `scripts/run-cuad-demo.sh` | Preflight Witdem, force endpoint/mode, ensure PDF, run showcase |
| `docs/deploy-hostinger.md` | Operator docs: clone, `.env`, re-run command |
| VPS `$CUAD_DIR/.env` | Provider keys (from local `/Users/mvonhassel/Documents/env file for demo`); not in git |

---

### Task 1: Add `scripts/run-cuad-demo.sh`

**Files:**
- Create: `scripts/run-cuad-demo.sh`

- [ ] **Step 1: Create the script**

```bash
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
  # shellcheck disable=SC1091
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
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/run-cuad-demo.sh`

- [ ] **Step 3: Smoke syntax check**

Run: `bash -n scripts/run-cuad-demo.sh`  
Expected: no output, exit 0

- [ ] **Step 4: Commit**

```bash
git add scripts/run-cuad-demo.sh
git commit -m "feat: add repeatable CUAD live showcase script for Hostinger Witdem"
```

---

### Task 2: Document operator steps in deploy-hostinger.md

**Files:**
- Modify: `docs/deploy-hostinger.md` (append new section before Safety, or after Verification matrix)

- [ ] **Step 1: Append section “10. CUAD live showcase (manual)”**

Content to add:

```markdown
## 10. CUAD live showcase (manual)

Feed live multi-model contract-review runs into the existing Witdem dashboard
([demo.witdem.com](https://demo.witdem.com)). No new public port; OTLP stays on
`127.0.0.1:4318`.

### One-time setup on the VPS

```bash
git clone https://github.com/ebrahimisoheil/haystack-cuad-contract-review.git \
  /home/deploy/haystack-cuad-contract-review
cd /home/deploy/haystack-cuad-contract-review
uv sync
# Create .env with OPENAI/MISTRAL/DEEPSEEK/VOYAGE keys (never commit).
# CONTRACT_REVIEW_MODE in the file may say deterministic; the run script forces live.
cp .env.example .env
$EDITOR .env
```

Keep document-intake updated so the script exists:

```bash
cd /opt/onyx-witdem-document-intake
git pull --ff-only
```

### Re-run before a customer demo

```bash
cd /opt/onyx-witdem-document-intake
./scripts/run-cuad-demo.sh
```

Optional overrides: `CUAD_DIR`, `WITDEM_ENDPOINT`, `DASHBOARD_URL`, `SHOWCASE_TIMEOUT`.

### Verify

1. Script exits 0 and prints provider verification.
2. https://demo.witdem.com shows a new run for `haystack-cuad-contract-review`.
3. `ss -lntp | grep 4318` still shows localhost-only bind.
```

- [ ] **Step 2: Commit**

```bash
git add docs/deploy-hostinger.md
git commit -m "docs: explain CUAD live showcase against demo.witdem.com"
```

---

### Task 3: VPS — clone, env, sync, first live run

**Files (on VPS only):**
- `/home/deploy/haystack-cuad-contract-review` (clone)
- `/home/deploy/haystack-cuad-contract-review/.env` (from local `/Users/mvonhassel/Documents/env file for demo`)

- [ ] **Step 1: Push document-intake commits** (script + docs) if not yet on remote

- [ ] **Step 2: SSH — pull document-intake and ensure script**

```bash
ssh deploy@187.124.175.57 'cd /opt/onyx-witdem-document-intake && git pull --ff-only && test -x scripts/run-cuad-demo.sh'
```

- [ ] **Step 3: SSH — clone CUAD if missing and uv sync**

```bash
ssh deploy@187.124.175.57 'test -d /home/deploy/haystack-cuad-contract-review || git clone https://github.com/ebrahimisoheil/haystack-cuad-contract-review.git /home/deploy/haystack-cuad-contract-review; cd /home/deploy/haystack-cuad-contract-review && uv sync'
```

- [ ] **Step 4: Secure-copy `.env`**

From the operator machine (do not print secrets):

```bash
scp "/Users/mvonhassel/Documents/env file for demo" \
  deploy@187.124.175.57:/home/deploy/haystack-cuad-contract-review/.env
ssh deploy@187.124.175.57 'chmod 600 /home/deploy/haystack-cuad-contract-review/.env'
```

- [ ] **Step 5: Confirm Witdem readiness**

```bash
ssh deploy@187.124.175.57 'curl -fsS http://127.0.0.1:4318/readiness && curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8501/'
```

Expected: readiness OK; dashboard HTTP 200

- [ ] **Step 6: Run live showcase**

```bash
ssh deploy@187.124.175.57 'cd /opt/onyx-witdem-document-intake && ./scripts/run-cuad-demo.sh'
```

Expected: exit 0; verification passed for deepseek/mistral/openai providers

- [ ] **Step 7: Confirm public dashboard**

```bash
curl -fsS -o /dev/null -w "%{http_code}\n" https://demo.witdem.com/
```

Expected: `200`. Operator spot-checks UI for the new CUAD run.

---

## Spec coverage checklist

| Spec requirement | Task |
| --- | --- |
| Dashboard-only surface | Task 3 (no new nginx/host) |
| Live mode + keys | Task 1 force `live`; Task 3 scp env |
| Repeatable script | Task 1 |
| `WITDEM_ENDPOINT=http://127.0.0.1:4318` | Task 1 |
| Deploy doc section | Task 2 |
| No OTLP public / no Onyx recreate | Task 3 (only CUAD + script) |
