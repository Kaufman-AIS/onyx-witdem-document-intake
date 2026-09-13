# Design: CUAD live showcase → demo.witdem.com

**Status:** Approved (conversation) — awaiting written-spec review  
**Date:** 2026-09-13  
**Repos:** [Kaufman-AIS/onyx-witdem-document-intake](https://github.com/Kaufman-AIS/onyx-witdem-document-intake) (deploy docs + run script)  
**Showcase source:** [ebrahimisoheil/haystack-cuad-contract-review](https://github.com/ebrahimisoheil/haystack-cuad-contract-review)  
**Host:** `187.124.175.57` (existing Hostinger VPS)  
**Related:** [2026-09-09 Hostinger deploy design](./2026-09-09-hostinger-onyx-witdem-deploy-design.md)

## Goal

Make the Haystack CUAD contract-review **live** showcase visible in the existing Witdem dashboard at [https://demo.witdem.com](https://demo.witdem.com), via a **manual, repeatable** VPS script (no new public UI, no Cron).

## Decisions (locked)

| Topic | Choice |
| --- | --- |
| Surface | **Dashboard only** — runs appear in `demo.witdem.com` |
| Run mode | **Live** providers (`OPENAI`, `MISTRAL`, `DEEPSEEK`, `VOYAGE`) |
| Trigger | Repeatable host script (run before customer demos) |
| Packaging | Approach **A** — git checkout on VPS + `.env` + script (not Compose service, not submodule mirror) |
| Telemetry target | Existing Witdem receiver on `127.0.0.1:4318` |
| Dashboard verify | Showcase CLI polls `http://127.0.0.1:8501` (same host; nginx not required for verification) |

## Non-goals

- Public CUAD web UI or new subdomain
- Exposing OTLP `:4318` on the internet
- Cron / always-on CUAD worker
- Redeploying or restarting Onyx for this work
- Vendoring the full CUAD app into `witdem-oss` or this repo
- Committing provider keys

## Architecture

```text
Operator (SSH)
  └─ onyx-witdem-document-intake/scripts/run-cuad-demo.sh
       └─ CUAD_DIR=/home/deploy/haystack-cuad-contract-review
            ├─ readiness: http://127.0.0.1:4318/readiness
            ├─ WITDEM_ENDPOINT=http://127.0.0.1:4318
            ├─ CONTRACT_REVIEW_MODE=live  (+ provider keys from CUAD .env)
            ├─ create showcase scanned PDF (once or if missing)
            └─ uv run contract-review-showcase <scan.pdf>
                 --dashboard-url http://127.0.0.1:8501

Haystack CUAD (host process)
  ──OTLP/SDK──► Witdem receiver :4318  (Docker, 127.0.0.1 only)
                     │
                     ▼
               DuckDB + ELT worker
                     │
                     ▼
               Dashboard :8501  ◄── nginx ◄── https://demo.witdem.com
```

### Why host process, not Compose

CUAD is a CLI showcase (`contract-review-showcase`), not a long-running service. Running it on the host next to the already-bound localhost ports matches how Document Intake tooling already uses local endpoints, avoids a second image build, and keeps provider secrets in a single host `.env`.

### Endpoint override

Upstream `.witdem/witdem.yaml` defaults to `http://localhost:24318`. The run script **must** set `WITDEM_ENDPOINT=http://127.0.0.1:4318` so the SDK posts traces/records to the live demo receiver (env override already supported by `witdem-sdk`).

## Components

| Unit | Responsibility | Depends on |
| --- | --- | --- |
| VPS checkout | Source tree at fixed path; `uv sync` | GitHub public repo, `uv`, Python |
| Host `.env` | Provider keys + mode; never committed | Operator-supplied secrets |
| `scripts/run-cuad-demo.sh` (this repo) | Preflight, env, showcase invocation, print execution id / verify result | Witdem up on `:4318`/`:8501`; CUAD checkout |
| Deploy doc section | Operator steps: clone, env template, first run, re-run | `docs/deploy-hostinger.md` |

### Script location

Canonical script: `onyx-witdem-document-intake/scripts/run-cuad-demo.sh`.

Default CUAD checkout path: `/home/deploy/haystack-cuad-contract-review` (overridable via `CUAD_DIR`).

### Script behavior (normative)

1. Fail fast if `curl -fsS http://127.0.0.1:4318/readiness` fails.
2. `cd` to `$CUAD_DIR`; require `.env` present (document copying from `.env.example`).
3. Export `WITDEM_ENDPOINT=http://127.0.0.1:4318` and `CONTRACT_REVIEW_MODE=live`.
4. Ensure a raster showcase PDF exists (`uv run --extra dev python examples/create_showcase_scan.py` → known output path under `$CUAD_DIR`).
5. Run `uv run contract-review-showcase <pdf> --dashboard-url http://127.0.0.1:8501` (timeout generous enough for OCR + multi-model path).
6. Exit non-zero if showcase verification fails; on success print the observed `execution_id` and remind the operator to open `https://demo.witdem.com`.

## Secrets

| Variable | Where | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | CUAD host `.env` | Required for live judge path |
| `MISTRAL_API_KEY` | CUAD host `.env` | OCR branch |
| `DEEPSEEK_API_KEY` | CUAD host `.env` | Text transforms |
| `VOYAGE_API_KEY` | CUAD host `.env` | Embeddings when memory/embeddings used |
| `WITDEM_API_KEY` | Only if demo Witdem enforces it | Pass through if set on receiver |

Do **not** put these in GitHub Actions secrets for v1 unless we later automate the script; operator places `.env` once via SSH.

## Error handling

| Failure | Behavior |
| --- | --- |
| Witdem down / readiness fail | Script exits before spending provider money |
| Missing `.env` or keys | Exit with clear message listing required vars |
| Showcase verification timeout | Non-zero exit; leave partial run in dashboard for inspection |
| Wrong Witdem endpoint (24318) | Prevented by forced `WITDEM_ENDPOINT` in script |

## Testing / verification

1. SSH to VPS; run script once.
2. Confirm script prints a terminal run with providers including deepseek, mistral, openai (default showcase expectations).
3. Open `https://demo.witdem.com` and find service `haystack-cuad-contract-review` / new execution.
4. Confirm `:4318` remains bound to localhost only (`ss` / deploy doc constraint unchanged).

## Rollout steps (implementation summary)

1. Add `scripts/run-cuad-demo.sh` in this repo (targets `$CUAD_DIR`).
2. Document clone path, `.env` template, and re-run command in `docs/deploy-hostinger.md`.
3. On VPS: clone CUAD, `uv sync`, write `.env` (operator keys), pull this repo’s script, first showcase run.
4. Smoke-check dashboard; no Onyx compose recreate.

## Open follow-ups (out of scope)

- Linking the external repo from `witdem-oss` README as a “full demo”
- Scheduled refresh of demo population
- Pinning a specific CUAD commit/tag in the deploy doc for reproducibility
