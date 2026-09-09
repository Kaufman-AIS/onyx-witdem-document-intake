# Design: Hostinger deploy — Onyx + Witdem + Document Intake

**Status:** Approved  
**Date:** 2026-09-09  
**Repo:** [Kaufman-AIS/onyx-witdem-document-intake](https://github.com/Kaufman-AIS/onyx-witdem-document-intake)  
**Host:** `187.124.175.57` (Hostinger VPS)

## Goal

Public demo stack on one VPS:

| Hostname | Role |
| --- | --- |
| `https://onyx.kaufman-ais.com` | Onyx UI (via witdem-proxy) |
| `https://demo.witdem.com` | Witdem Analytics dashboard |

Full stack (same as local demo): **Onyx + Witdem + witdem-proxy + Document Intake** (Drive/Tasks).

Deploy via **GitHub Actions** (SSH + `git pull` + `docker compose`), not manual-only.

## Decisions (locked)

| Topic | Choice |
| --- | --- |
| CI/CD host | GitHub Actions in this repo |
| Rollout method | **A** — SSH → `git pull` → write `.env` → `docker compose up -d` |
| TLS / edge | Existing **Hostinger nginx** + Let’s Encrypt; reverse-proxy to localhost ports |
| App packing | This repo root = former `examples/onyx-demo` |
| Scope | Full demo including intake |
| Triggers | `workflow_dispatch` + push to `main` |

## Non-goals (v1)

- Building/publishing all images to GHCR (approach B) — defer
- Ansible / Packer
- Multi-node / HA
- Putting secrets in the git tree
- Changing `witdem-oss` remotes or merging this into `witdem-oss` `main`

## Architecture

```text
Internet
  ├─ https://onyx.kaufman-ais.com  ──nginx──► 127.0.0.1:3000  (witdem-proxy → Onyx)
  └─ https://demo.witdem.com       ──nginx──► 127.0.0.1:8501  (Witdem dashboard)
                                              127.0.0.1:4318  (OTLP, localhost only)

GitHub Actions (this repo)
  └─ SSH → VPS
        /opt/onyx-witdem-document-intake
        docker compose up -d
        .env from GitHub Secrets
```

### Components

| Component | Source | Notes |
| --- | --- | --- |
| Onyx | Official `onyxdotapp/*` images | Cloned/setup via existing `scripts/setup-onyx.sh` (or server equivalent) |
| witdem-proxy | `Dockerfile.proxy` in this repo | UI/API on `:3000` / API path; records chat to Witdem |
| Witdem | `npx witdem@…` or Compose equivalent | Dashboard `:8501`, OTLP `:4318` |
| Intake | uvicorn service in Compose | Listens `0.0.0.0:8091` **inside** Docker network |

### Networking (critical)

- Bind published ports to **`127.0.0.1` only** (`3000`, `8501`, `4318`).
- Onyx custom tool URL must be Docker-DNS: `http://intake:8091/tools/run_intake` (not `host.docker.internal`).
- Proxy → Witdem OTLP: use Compose service name (e.g. `http://receiver:4318` / Witdem network), same lesson as local Docker Desktop IPv6 issues.

## GitHub Actions deploy flow

1. Checkout is not required on the runner for app files if the server is the git remote checkout; runner only needs SSH.
2. SSH to VPS as deploy user.
3. `cd /opt/onyx-witdem-document-intake && git fetch && git reset --hard origin/main` (or `pull --ff-only`).
4. Render `/opt/onyx-witdem-document-intake/.env` (and Onyx compose `.env` if separate) from GitHub Secrets — never commit.
5. `docker compose … up -d --build` (exact compose files to be listed in the implementation plan).
6. Optional health checks: `curl -fsS https://onyx.kaufman-ais.com/…`, `https://demo.witdem.com/…`.

### Suggested GitHub Secrets

| Secret | Purpose |
| --- | --- |
| `SSH_HOST` | `187.124.175.57` |
| `SSH_USER` | deploy user |
| `SSH_PRIVATE_KEY` | deploy key |
| `SSH_PORT` | optional, default 22 |
| `OPENAI_API_KEY` | Onyx + intake LLM |
| `ONYX_API_KEY` | after first admin bootstrap (may be filled on 2nd deploy) |
| Google Drive/Tasks vars | as in `.env.example` |
| `WITDEM_*` / dashboard auth | as needed for remote Witdem |

Exact names aligned with `.env.example` during implementation.

## Host nginx (sketch)

- `onyx.kaufman-ais.com` → `proxy_pass http://127.0.0.1:3000` (WebSocket-friendly headers for chat SSE).
- `demo.witdem.com` → `proxy_pass http://127.0.0.1:8501`.
- TLS via Certbot / Hostinger SSL.
- Do **not** expose `:4318` publicly.

Nginx site snippets live in-repo under `deploy/nginx/` (to be added in implementation) for copy onto the VPS once.

## First-time bootstrap (manual / documented)

1. VPS: Docker Engine + Compose plugin; nginx sites + certificates for both hostnames.
2. Create deploy user + SSH key registered in GitHub Actions secrets.
3. Clone this repo to `/opt/onyx-witdem-document-intake`.
4. Run first Actions deploy (or manual compose once).
5. Open Onyx → create admin, configure LLM, create API key → put `ONYX_API_KEY` in GitHub Secrets.
6. Register Intake OpenAPI tool pointing at `http://intake:8091/tools/run_intake`.
7. Verify: chat on Onyx host appears in Witdem; intake files to Drive.

## Failure / rollback

- Failed `compose up` should not delete volumes; previous containers remain until a successful recreate.
- Actions job fails loudly; no silent partial DNS cutover (nginx stays pointing at localhost ports).
- Document: take Onyx DB/volume backup before major Onyx image upgrades.
- No automatic destructive `docker compose down -v` in CI.

## Testing / verification

| Check | Expect |
| --- | --- |
| `https://onyx.kaufman-ais.com` | Onyx login / chat UI |
| `https://demo.witdem.com` | Witdem dashboard |
| Chat via Onyx UI | Run + tokens/cost in Witdem (when usage patch applied) |
| Intake tool | File in Google Drive; spans in Witdem |
| `:4318` from public internet | Connection refused / filtered |

## Open items for implementation plan

- Exact Compose file set (upstream Onyx + override for proxy/intake/witdem).
- Whether Witdem runs via `npx witdem` systemd unit or Docker services on the VPS.
- Apply/re-apply `patches/onyx-llm-usage.patch` on server Onyx checkout.
- Nginx WebSocket/SSE timeouts for long chat streams.
