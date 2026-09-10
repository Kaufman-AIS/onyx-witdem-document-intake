# Deploy on Hostinger VPS

One-time bootstrap and secrets checklist for production rollouts to
`onyx.kaufman-ais.com` and `demo.witdem.com` via GitHub Actions
(`.github/workflows/deploy.yml`).

**Do not run production deploy from a laptop unless you intend to.** First and
routine deploys go through Actions (`workflow_dispatch` or push to `main`).

## Prerequisites (DNS)

DNS for both hostnames already points at the VPS:

| Hostname | Target |
| --- | --- |
| `onyx.kaufman-ais.com` | `187.124.175.57` |
| `demo.witdem.com` | `187.124.175.57` |

Confirm with `dig +short onyx.kaufman-ais.com` / `demo.witdem.com` before TLS.

## 1. VPS packages

On the Hostinger VPS (Ubuntu):

1. Install **Docker Engine** and the **Compose plugin** (official Docker docs).
2. Install **nginx** and **certbot** (with the nginx plugin), e.g.:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

## 2. Host nginx + TLS

Enable HTTP-only first or use `certbot --nginx` before requiring TLS cert paths (templates assume certs exist).

Templates live in-repo under `deploy/nginx/`:

- `deploy/nginx/onyx.kaufman-ais.com.conf` → proxy to `127.0.0.1:3020` (witdem-proxy; host `:3000` reserved for SRS)
- `deploy/nginx/demo.witdem.com.conf` → proxy to `127.0.0.1:8501`

On the VPS (after the repo exists under `/opt/onyx-witdem-document-intake`, or
copy the files another way for first TLS):

```bash
sudo cp /opt/onyx-witdem-document-intake/deploy/nginx/*.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/onyx.kaufman-ais.com.conf /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/demo.witdem.com.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d onyx.kaufman-ais.com -d demo.witdem.com
```

Certbot may rewrite SSL paths; keep WebSocket/`Upgrade` headers from the templates.
Do **not** expose Witdem OTLP `:4318` on the public internet.

## 3. Deploy user + SSH secrets

1. Create a non-root deploy user with permission to run Docker and write
   `/opt/onyx-witdem-document-intake`.
2. Generate an SSH key for that user; install the public key in
   `~/.ssh/authorized_keys`.
3. In the GitHub repo **Settings → Secrets and variables → Actions**, set:

| Secret | Purpose |
| --- | --- |
| `SSH_HOST` | `187.124.175.57` |
| `SSH_USER` | Deploy username |
| `SSH_PRIVATE_KEY` | Private key PEM for that user |

**Note:** `SSH_PORT` is **not** a GitHub secret in the current workflow. Port is
hardcoded to **22** in `.github/workflows/deploy.yml`. For a non-default port,
edit the workflow (`port:`) and optionally introduce an `SSH_PORT` secret.

## 4. Application secrets (GitHub Actions)

These names match `env:` / `envs:` in `.github/workflows/deploy.yml` and are
rendered onto the server by `scripts/render-env-from-github.sh` during deploy.

| Secret | Purpose | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | Onyx LLM + intake extraction | Required for first useful deploy |
| `ONYX_API_KEY` | Onyx Admin API key | Leave empty until after admin bootstrap (step 7); then set and re-run deploy |
| `ONYX_PERSONA_ID` | Persona used by demo/intake clients | Optional until configured in Onyx |
| `WITDEM_API_KEY` | Witdem analytics auth (if enabled) | Optional depending on Witdem config |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Drive root for intake folders | Share folder with SA `client_email` |
| `GOOGLE_TASKS_LIST_ID` | Google Tasks list for extracted open items | Real Tasks need OAuth below |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth Desktop client ID | Tasks on company accounts |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth Desktop client secret | |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | Refresh token from OAuth flow | e.g. local `./scripts/google-oauth-tasks.sh` |
| `INTAKE_USE_MEMORY` | Force in-memory Drive/Tasks | `1` for smoke without Google; `0` for real filing |

SSH secrets (`SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`) are listed in section 3.
Never commit `.env` or service-account JSON to git.

## 5. Google service account file on the VPS

Compose mounts `./secrets` read-only at `/run/secrets`. Place the SA JSON on the
server (not in GitHub Secrets as a file):

```bash
sudo mkdir -p /opt/onyx-witdem-document-intake/secrets
sudo install -m 600 /path/to/google-sa.json \
  /opt/onyx-witdem-document-intake/secrets/google-sa.json
sudo chown "$DEPLOY_USER:$DEPLOY_USER" \
  /opt/onyx-witdem-document-intake/secrets/google-sa.json
```

Rendered `.env` should set
`GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-sa.json`.
Skip this file only if you keep `INTAKE_USE_MEMORY=1`.

## 6. First Actions deploy

1. Ensure nginx + certs and SSH secrets are ready.
2. In GitHub Actions, run **Deploy Hostinger** via **`workflow_dispatch`**
   (or push to `main` once the workflow is on that branch).
3. The job SSHes in, clones or updates `/opt/onyx-witdem-document-intake`, and
   runs `./scripts/deploy-remote.sh` (`docker compose … up -d`, no volume wipe).

## 7. Onyx admin bootstrap + API key

After the stack is up:

1. Open `https://onyx.kaufman-ais.com` and complete admin registration.
2. Configure the LLM provider (OpenAI + key) if prompted.
3. Admin Panel → create an **API key** (chat + ingestion as needed).
4. Set GitHub secret `ONYX_API_KEY` to that value.
5. **Re-run** the Deploy Hostinger workflow so the server `.env` picks it up.

## 8. Document Intake OpenAPI tool (automated)

Each successful `./scripts/deploy-remote.sh` run calls
`./scripts/register-intake-onyx-tool.sh`, which **idempotently**:

1. Upserts the custom Onyx tool **Document Intake** (`run_intake`) with OpenAPI
   server URL `http://intake:8091` (Docker DNS — not `host.docker.internal`).
2. Attaches it to persona **0** (Assistant).
3. Appends `run_intake` filing instructions to that persona’s `system_prompt` if
   missing.

Manual Admin registration is **not** required after a green deploy. To re-run
only the registration step on the VPS:

```bash
cd /opt/onyx-witdem-document-intake
./scripts/register-intake-onyx-tool.sh
```

Local Mac setup (tool on the host) still uses
`http://host.docker.internal:8091` — see
[docs/intake-onyx-tool-setup.md](intake-onyx-tool-setup.md).

**Still manual (not in git):** configure an LLM provider in Onyx Admin, create
`ONYX_API_KEY`, set the GitHub secret, and re-deploy so intake can download
original upload bytes from Onyx.

## 9. Verification matrix

| Check | Expect |
| --- | --- |
| Hosts resolve to VPS IP | `onyx.kaufman-ais.com` and `demo.witdem.com` → `187.124.175.57` |
| HTTPS on both hostnames | Valid certs; HTTP redirects to HTTPS |
| Onyx UI via proxy | `https://onyx.kaufman-ais.com` login / chat loads |
| Witdem dashboard | `https://demo.witdem.com` loads |
| Chat → Witdem spans/costs | Chat creates runs/spans; costs when LLM usage patch is applied |
| Intake reachable from Onyx | Tool URL `http://intake:8091` (health / `run_intake`) |
| Drive/Tasks side effects | When not memory mode: files in Drive, tasks when OAuth configured |
| End-to-end demo | Chat on Onyx host appears in Witdem; intake files to Drive |

## Safety: volumes and rollback

- **Do not** run `docker compose down -v` for routine deploys — that deletes
  named volumes (Onyx DB, Witdem data, etc.).
- Deploy scripts use `up -d` / recreate without wiping volumes.
- **Rollback:** on the VPS checkout, `git reset --hard <previous-sha>` (or reset
  `main` / re-point the remote SHA) and **re-run** the GitHub Actions deploy job
  so Compose recreates containers from that revision.
