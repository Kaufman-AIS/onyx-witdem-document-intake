# Hostinger Onyx + Witdem Document Intake Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the full Onyx + Witdem + witdem-proxy + Document Intake stack to Hostinger VPS `187.124.175.57` via GitHub Actions, served at `onyx.kaufman-ais.com` and `demo.witdem.com` behind host nginx.

**Architecture:** Actions SSHs to the VPS, syncs this repo to `/opt/onyx-witdem-document-intake`, writes `.env` from GitHub Secrets, and runs Docker Compose (Onyx upstream + prod overrides for proxy/intake + separate Witdem compose). Host nginx terminates TLS and reverse-proxies to `127.0.0.1:3000` / `127.0.0.1:8501`.

**Tech Stack:** GitHub Actions, Docker Compose, official Onyx images, `ghcr.io/ebrahimisoheil/witdem-analytics:0.2.6`, nginx + Let’s Encrypt, Starlette intake/proxy from this repo.

**Spec:** `docs/superpowers/specs/2026-09-09-hostinger-onyx-witdem-deploy-design.md`

---

## File map

| File | Responsibility |
| --- | --- |
| `docker-compose.witdem.yml` | Witdem receiver + elt-worker + dashboard; creates `witdem_default` network |
| `docker-compose.prod.yml` | Prod overrides: localhost binds, relative proxy build, intake service, Witdem endpoint |
| `Dockerfile.intake` | Image for `run_intake` uvicorn tool server |
| `deploy/nginx/onyx.kaufman-ais.com.conf` | nginx site → `127.0.0.1:3000` (SSE/WebSocket-friendly) |
| `deploy/nginx/demo.witdem.com.conf` | nginx site → `127.0.0.1:8501` |
| `scripts/deploy-remote.sh` | Server-side: pull, write env, compose up, health checks |
| `scripts/render-env-from-github.sh` | Map env vars (set by Actions) into `.env` files |
| `.github/workflows/deploy.yml` | SSH deploy on `workflow_dispatch` + push `main` |
| `docs/deploy-hostinger.md` | One-time VPS bootstrap + secrets checklist |
| `docker-compose.witdem-proxy.yml` | Fix absolute Mac `build.context` → `.` (breaks Linux CI/server) |

---

### Task 1: Fix proxy compose build context (portable)

**Files:**
- Modify: `docker-compose.witdem-proxy.yml`

- [ ] **Step 1: Replace absolute build context**

Change `build.context` from the Mac absolute path to `.`:

```yaml
services:
  witdem-proxy:
    image: onyx-witdem-proxy:local
    build:
      context: .
      dockerfile: Dockerfile.proxy
    ports:
      - "3000:3000"
      - "3001:8080"
    environment:
      ONYX_UPSTREAM: http://nginx:80
      WITDEM_ENDPOINT: http://receiver:4318
      WITDEM_CONFIG: /app/witdem.yml
    depends_on:
      nginx:
        condition: service_started
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - default
      - witdem_default
    restart: unless-stopped

networks:
  witdem_default:
    external: true
    name: witdem_default
```

Note: Witdem official compose names the OTLP service `witdem`, while `npx witdem` uses `receiver`. Prod Witdem compose (Task 2) will expose service name `receiver` as an alias **or** set `WITDEM_ENDPOINT: http://witdem:4318` consistently. Prefer **`http://witdem:4318`** everywhere in prod files and update this override’s `WITDEM_ENDPOINT` to `http://witdem:4318`.

- [ ] **Step 2: Commit**

```bash
git add docker-compose.witdem-proxy.yml
git commit -m "fix: use relative context for witdem-proxy build"
```

---

### Task 2: Add Witdem Compose for the VPS

**Files:**
- Create: `docker-compose.witdem.yml`

- [ ] **Step 1: Write `docker-compose.witdem.yml`**

Use published analytics image (matches local `npx witdem@0.2.6` channel). Network name must be `witdem_default` so the proxy can join it.

```yaml
name: witdem

services:
  witdem:
    image: ${WITDEM_ANALYTICS_IMAGE:-ghcr.io/ebrahimisoheil/witdem-analytics:0.2.6}
    command: ["witdem", "serve", "--host", "0.0.0.0", "--port", "4318", "--db", "/app/data/live.duckdb"]
    ports:
      - "127.0.0.1:4318:4318"
    environment:
      WITDEM_DATA_DIR: /app/data
      WITDEM_DB_PATH: /app/data/live.duckdb
      WITDEM_API_KEY: ${WITDEM_API_KEY:-}
    volumes:
      - witdem-live-data:/app/data
    networks:
      witdem_default:
        aliases: [receiver]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://localhost:4318/readiness', timeout=2)"]
      interval: 5s
      timeout: 3s
      start_period: 10s
      retries: 12
    restart: unless-stopped

  elt-worker:
    image: ${WITDEM_ANALYTICS_IMAGE:-ghcr.io/ebrahimisoheil/witdem-analytics:0.2.6}
    command: ["witdem", "elt", "worker", "--poll-interval", "0.25"]
    environment:
      WITDEM_DATA_DIR: /app/data
      WITDEM_DB_PATH: /app/data/live.duckdb
    volumes:
      - witdem-live-data:/app/data
    networks: [witdem_default]
    depends_on:
      witdem:
        condition: service_healthy
    restart: unless-stopped

  dashboard:
    image: ${WITDEM_ANALYTICS_IMAGE:-ghcr.io/ebrahimisoheil/witdem-analytics:0.2.6}
    command: ["witdem", "dashboard", "--db", "/app/data/live.duckdb", "--dashboard-host", "0.0.0.0", "--dashboard-port", "8501"]
    ports:
      - "127.0.0.1:8501:8501"
    environment:
      WITDEM_DATA_DIR: /app/data
      WITDEM_DB_PATH: /app/data/live.duckdb
    volumes:
      - witdem-live-data:/app/data
    networks: [witdem_default]
    depends_on:
      witdem:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8501/health', timeout=2)"]
      interval: 10s
      timeout: 3s
      start_period: 15s
      retries: 12
    restart: unless-stopped

networks:
  witdem_default:
    name: witdem_default

volumes:
  witdem-live-data:
```

- [ ] **Step 2: Validate compose file locally**

Run: `docker compose -f docker-compose.witdem.yml config`
Expected: prints merged config without errors

- [ ] **Step 3: Commit**

```bash
git add docker-compose.witdem.yml
git commit -m "feat: add Witdem compose stack for VPS deploy"
```

---

### Task 3: Intake Dockerfile + prod Compose override

**Files:**
- Create: `Dockerfile.intake`
- Create: `docker-compose.prod.yml`
- Test: smoke via `docker compose … config`

- [ ] **Step 1: Write `Dockerfile.intake`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY witdem.yml ./
COPY contracts ./contracts
COPY workflows ./workflows
COPY src ./src
RUN pip install --no-cache-dir -e .
ENV WITDEM_CONFIG=/app/witdem.yml
EXPOSE 8091
CMD ["uvicorn", "witdem_onyx_demo.intake.tool_server:app", "--host", "0.0.0.0", "--port", "8091"]
```

- [ ] **Step 2: Write `docker-compose.prod.yml`**

This file is merged with Onyx upstream compose + `docker-compose.witdem-proxy.yml`:

```yaml
services:
  witdem-proxy:
    ports:
      - "127.0.0.1:3000:3000"
      - "127.0.0.1:3001:8080"
    environment:
      WITDEM_ENDPOINT: http://witdem:4318
    restart: unless-stopped

  api_server:
    # ensure Onyx can resolve intake hostname on the default network
    extra_hosts: []

  intake:
    build:
      context: .
      dockerfile: Dockerfile.intake
    image: onyx-witdem-intake:local
    env_file:
      - .env
    environment:
      WITDEM_ENDPOINT: http://witdem:4318
      WITDEM_CONFIG: /app/witdem.yml
      ONYX_API_BASE_URL: http://api_server:8080
      INTAKE_USE_MEMORY: ${INTAKE_USE_MEMORY:-0}
    ports:
      - "127.0.0.1:8091:8091"
    networks:
      - default
      - witdem_default
    restart: unless-stopped
    volumes:
      # Mount SA JSON if path is provided as a file next to compose
      - ${GOOGLE_APPLICATION_CREDENTIALS_MOUNT:-./secrets/google-sa.json}:/run/secrets/google-sa.json:ro
    # When using the mount, set GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sa.json in .env

networks:
  witdem_default:
    external: true
    name: witdem_default
```

If `GOOGLE_APPLICATION_CREDENTIALS_MOUNT` is optional and missing, prefer documenting copying the SA JSON to `./secrets/google-sa.json` on the server (gitignored) rather than a broken default mount. **Adjust Step 2** so the credentials volume is only documented in `docs/deploy-hostinger.md` and the compose volume is:

```yaml
    volumes:
      - ./secrets:/run/secrets:ro
```

with `.gitignore` entry `secrets/` and `.env` containing `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sa.json`.

- [ ] **Step 3: Ensure `.gitignore` ignores secrets**

Append if missing:

```
secrets/
.env
.onyx-upstream/
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.intake docker-compose.prod.yml .gitignore
git commit -m "feat: add intake image and production compose override"
```

---

### Task 4: nginx site configs

**Files:**
- Create: `deploy/nginx/onyx.kaufman-ais.com.conf`
- Create: `deploy/nginx/demo.witdem.com.conf`

- [ ] **Step 1: Write Onyx nginx site**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name onyx.kaufman-ais.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name onyx.kaufman-ais.com;

    # Managed by Certbot — paths may differ on Hostinger; adjust after certbot --nginx
    ssl_certificate     /etc/letsencrypt/live/onyx.kaufman-ais.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/onyx.kaufman-ais.com/privkey.pem;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

- [ ] **Step 2: Write Witdem dashboard nginx site**

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name demo.witdem.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name demo.witdem.com;

    ssl_certificate     /etc/letsencrypt/live/demo.witdem.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/demo.witdem.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add deploy/nginx/
git commit -m "docs: add nginx site templates for onyx and witdem hosts"
```

---

### Task 5: Server deploy scripts

**Files:**
- Create: `scripts/render-env-from-github.sh`
- Create: `scripts/deploy-remote.sh`

- [ ] **Step 1: Write `scripts/render-env-from-github.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.env}"

required=(OPENAI_API_KEY)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required env: $name" >&2
    exit 1
  fi
done

umask 077
cat >"$OUT" <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
ONYX_API_BASE_URL=${ONYX_API_BASE_URL:-http://api_server:8080}
ONYX_API_KEY=${ONYX_API_KEY:-}
ONYX_PERSONA_ID=${ONYX_PERSONA_ID:-}
WITDEM_ENDPOINT=${WITDEM_ENDPOINT:-http://witdem:4318}
WITDEM_API_KEY=${WITDEM_API_KEY:-}
INTAKE_USE_MEMORY=${INTAKE_USE_MEMORY:-0}
GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS:-/run/secrets/google-sa.json}
GOOGLE_DRIVE_ROOT_FOLDER_ID=${GOOGLE_DRIVE_ROOT_FOLDER_ID:-}
GOOGLE_TASKS_LIST_ID=${GOOGLE_TASKS_LIST_ID:-}
GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID:-}
GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET:-}
GOOGLE_OAUTH_REFRESH_TOKEN=${GOOGLE_OAUTH_REFRESH_TOKEN:-}
EOF

# Onyx upstream compose env (OPENAI key)
COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"
if [[ -d "$COMPOSE_DIR" ]]; then
  if grep -q '^OPENAI_API_KEY=' "$COMPOSE_DIR/.env" 2>/dev/null; then
    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_API_KEY}|" "$COMPOSE_DIR/.env"
  else
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >>"$COMPOSE_DIR/.env"
  fi
  if ! grep -q '^HOST_PORT=' "$COMPOSE_DIR/.env" 2>/dev/null; then
    echo "HOST_PORT=13000" >>"$COMPOSE_DIR/.env"
  fi
fi

echo "wrote $OUT"
```

- [ ] **Step 2: Write `scripts/deploy-remote.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/setup-onyx.sh
./scripts/render-env-from-github.sh "$ROOT/.env"

# Optional LLM usage patch (ignore if already applied)
if [[ -f patches/onyx-llm-usage.patch ]]; then
  git -C .onyx-upstream apply --check patches/onyx-llm-usage.patch 2>/dev/null \
    && git -C .onyx-upstream apply patches/onyx-llm-usage.patch \
    || echo "onyx-llm-usage.patch already applied or not applicable"
fi

docker compose -f docker-compose.witdem.yml up -d

COMPOSE_DIR="$ROOT/.onyx-upstream/deployment/docker_compose"
docker compose \
  -f "$COMPOSE_DIR/docker-compose.yml" \
  -f "$ROOT/docker-compose.witdem-proxy.yml" \
  -f "$ROOT/docker-compose.prod.yml" \
  up -d --build

./scripts/wait-onyx.sh || true

curl -fsS --max-time 10 http://127.0.0.1:8501/health >/dev/null
curl -fsS --max-time 10 http://127.0.0.1:8091/health >/dev/null
echo "deploy-remote: OK (local health checks passed)"
```

- [ ] **Step 3: Make scripts executable and commit**

```bash
chmod +x scripts/render-env-from-github.sh scripts/deploy-remote.sh
git add scripts/render-env-from-github.sh scripts/deploy-remote.sh
git commit -m "feat: add remote deploy and env render scripts"
```

---

### Task 6: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write deploy workflow**

```yaml
name: Deploy Hostinger

on:
  workflow_dispatch:
  push:
    branches: [main]

concurrency:
  group: deploy-hostinger
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          port: ${{ secrets.SSH_PORT || 22 }}
          command_timeout: 45m
          script: |
            set -euo pipefail
            APP=/opt/onyx-witdem-document-intake
            if [[ ! -d "$APP/.git" ]]; then
              sudo mkdir -p /opt
              sudo git clone https://github.com/Kaufman-AIS/onyx-witdem-document-intake.git "$APP"
              sudo chown -R "$USER:$USER" "$APP"
            fi
            cd "$APP"
            git fetch origin main
            git reset --hard origin/main
            export OPENAI_API_KEY='${{ secrets.OPENAI_API_KEY }}'
            export ONYX_API_KEY='${{ secrets.ONYX_API_KEY }}'
            export ONYX_PERSONA_ID='${{ secrets.ONYX_PERSONA_ID }}'
            export WITDEM_API_KEY='${{ secrets.WITDEM_API_KEY }}'
            export GOOGLE_DRIVE_ROOT_FOLDER_ID='${{ secrets.GOOGLE_DRIVE_ROOT_FOLDER_ID }}'
            export GOOGLE_TASKS_LIST_ID='${{ secrets.GOOGLE_TASKS_LIST_ID }}'
            export GOOGLE_OAUTH_CLIENT_ID='${{ secrets.GOOGLE_OAUTH_CLIENT_ID }}'
            export GOOGLE_OAUTH_CLIENT_SECRET='${{ secrets.GOOGLE_OAUTH_CLIENT_SECRET }}'
            export GOOGLE_OAUTH_REFRESH_TOKEN='${{ secrets.GOOGLE_OAUTH_REFRESH_TOKEN }}'
            export INTAKE_USE_MEMORY='${{ secrets.INTAKE_USE_MEMORY }}'
            ./scripts/deploy-remote.sh
```

Security note for implementer: prefer writing secrets via `envs` of `appleboy/ssh-action` (`envs: OPENAI_API_KEY` + `environment:` mapping) instead of interpolating secrets into the remote script string, so they do not appear in process lists. Equivalent:

```yaml
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ONYX_API_KEY: ${{ secrets.ONYX_API_KEY }}
          # …same list…
        with:
          envs: OPENAI_API_KEY,ONYX_API_KEY,ONYX_PERSONA_ID,WITDEM_API_KEY,GOOGLE_DRIVE_ROOT_FOLDER_ID,GOOGLE_TASKS_LIST_ID,GOOGLE_OAUTH_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET,GOOGLE_OAUTH_REFRESH_TOKEN,INTAKE_USE_MEMORY
          script: |
            set -euo pipefail
            APP=/opt/onyx-witdem-document-intake
            …
            ./scripts/deploy-remote.sh
```

Use the `envs` form in the committed workflow.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add Hostinger SSH deploy workflow"
```

---

### Task 7: Deploy documentation + secrets checklist

**Files:**
- Create: `docs/deploy-hostinger.md`
- Modify: `README.md` (add link under Quick start / Deploy)

- [ ] **Step 1: Write `docs/deploy-hostinger.md`**

Must include:

1. DNS already pointing both hosts to `187.124.175.57`
2. VPS: install Docker Engine + Compose plugin; install nginx + certbot
3. Copy nginx templates from `deploy/nginx/` → `/etc/nginx/sites-available/`, enable, `certbot --nginx`
4. Create deploy user, SSH key → GitHub Secrets `SSH_HOST` / `SSH_USER` / `SSH_PRIVATE_KEY`
5. Full secrets table matching Task 6
6. Place Google SA JSON at `/opt/onyx-witdem-document-intake/secrets/google-sa.json` (mode `600`)
7. First Actions `workflow_dispatch`
8. Onyx admin bootstrap + create API key → set `ONYX_API_KEY` secret → re-run deploy
9. Register OpenAPI tool URL: `http://intake:8091/tools/run_intake`
10. Verify matrix from the design spec

- [ ] **Step 2: Link from README**

Add under a `## Deploy` heading:

```markdown
## Deploy (Hostinger)

See [docs/deploy-hostinger.md](docs/deploy-hostinger.md) for VPS + GitHub Actions rollout
(`onyx.kaufman-ais.com`, `demo.witdem.com`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/deploy-hostinger.md README.md
git commit -m "docs: Hostinger deploy bootstrap and secrets guide"
```

---

### Task 8: Dry-run validation (local) + handoff checklist

**Files:** none new

- [ ] **Step 1: Local compose config merge dry-run**

Requires a local `.onyx-upstream` (run `./scripts/setup-onyx.sh` once):

```bash
docker compose -f docker-compose.witdem.yml config >/dev/null
docker compose \
  -f .onyx-upstream/deployment/docker_compose/docker-compose.yml \
  -f docker-compose.witdem-proxy.yml \
  -f docker-compose.prod.yml \
  config >/dev/null
```

Expected: exit 0

- [ ] **Step 2: Push `main` and confirm workflow file visible on GitHub**

```bash
git push origin main
gh workflow list --repo Kaufman-AIS/onyx-witdem-document-intake
```

Expected: `Deploy Hostinger` listed

- [ ] **Step 3: Manual gate before first production Actions run**

Operator confirms:

- [ ] SSH secrets set in GitHub
- [ ] `OPENAI_API_KEY` set
- [ ] nginx sites + certs live
- [ ] `/opt` clone path writable by deploy user
- [ ] Google secrets file on server if intake not memory mode

Then run: `gh workflow run "Deploy Hostinger" --repo Kaufman-AIS/onyx-witdem-document-intake`

---

## Spec coverage (self-review)

| Spec requirement | Task |
| --- | --- |
| Actions SSH + pull + compose | 5, 6 |
| nginx edge TLS | 4, 7 |
| Full stack incl. intake | 3, 5 |
| Localhost-only app ports | 2, 3 |
| Intake Docker DNS `http://intake:8091` | 3, 7 |
| Secrets not in git | 5, 6, 7 |
| Rollback / no `down -v` | 5 (`up -d` only) |
| Usage patch optional | 5 |
| Verification hosts | 7, 8 |

## Placeholder scan

No TBD/FIXME left; Witdem service naming standardized on `witdem` with alias `receiver`.
