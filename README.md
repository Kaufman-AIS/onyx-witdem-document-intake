# Witdem + Onyx agency demo

Self-contained showcase: **local Onyx** (knowledge brain) + **Witdem** (audit analytics) +
seed documents + instrumented chat cases.

Demonstrates that Witdem is an **observability layer** — not a replacement platform. Onyx runs
from upstream official images; this demo orchestrates deployment and instruments the API boundary.

## Prerequisites

- Docker with Compose (~8 GB RAM recommended for Onyx Standard)
- Node.js (for `npx witdem@0.2.6`)
- Python 3.10+
- **OpenAI API key** (Onyx uses it as the LLM backend)

## Quick start

```bash
cd examples/onyx-demo
# Credentials: witdem-oss/.env (repo root, preferred) or examples/onyx-demo/.env

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

./scripts/stack-up.sh
```

`stack-up.sh` starts **witdem-proxy** on ports **3000 (Onyx UI — HTTP or HTTPS)** and **3001 (HTTP API)**.
Open **http://127.0.0.1:3000/auth/login** in your browser — text, file,
and image chats are recorded in Witdem automatically.

First-time Onyx setup (once per machine):

1. Open **http://127.0.0.1:3000/auth/login** (or **https://127.0.0.1:3000/auth/login** if your browser forces HTTPS — accept the self-signed certificate once)
   and complete admin registration
2. Configure an LLM provider if prompted (OpenAI + your key)
3. Admin Panel → create an **API key** (chat + ingestion permissions)
4. Add `ONYX_API_KEY=...` to `.env`

Seed the knowledge base (optional regression cases):

```bash
python scripts/bootstrap-onyx.py
python run_demo.py   # optional YAML contract cases
```

Use **http://127.0.0.1:3000** for normal Onyx chat — runs appear in Witdem with the
`ui_knowledge_answer` workflow contract. File uploads use `document_upload`.
Scripts and `ONYX_API_BASE_URL` use **http://127.0.0.1:3001/api** (no TLS).
Open **http://localhost:8501** for Runs, Workflow replay (`onyx-agent`), and contract
outcomes from UI chats and `run_demo.py` cases.

### Document intake

Optional extension: Onyx calls custom tool `run_intake` to file invoices and documents
to Google Drive and create Google Tasks. Start the tool server alongside the stack:

```bash
./scripts/run-intake-tool.sh
```

Register the tool in Onyx Admin and configure persona instructions — see
[docs/intake-onyx-tool-setup.md](docs/intake-onyx-tool-setup.md).

## Workflow contracts

Every Witdem execution in this demo must complete with an explicit YAML workflow contract.
There is no telemetry-only run path.

| Contract | Used by | Evaluates |
| --- | --- | --- |
| `knowledge_answer` | `run_demo.py` YAML cases | Non-empty answer and grounding vs held-out `expected_grounded` |
| `ui_knowledge_answer` | Onyx UI chat via witdem-proxy | Non-empty answer and observed grounding (no held-out expectation) |
| `document_upload` | Onyx UI file upload route | At least one accepted file for chat context |

Declarations live in [`witdem.yml`](witdem.yml) (business contracts) and
[`workflows/onyx-agent.yml`](workflows/onyx-agent.yml) (execution topology). Demo cases
declare `contract: knowledge_answer` in each file under `cases/`.

Python entry points call `require_contract(...)` then `report_contract(...)` (which maps
payloads to `witdem.report(...)`) so missing contracts fail fast instead of falling back
to implicit defaults.

Stop everything:

```bash
./scripts/stack-down.sh
```

## What the agency should see

| Question | Demo answer |
| --- | --- |
| Redeploy agents on Witdem? | No — instrumentation at the Onyx API boundary |
| Audit log? | Immutable corpus, execution replay, workflow paths, contract evaluation |
| Works with existing stack? | Same pattern for LangChain, n8n boundaries, sub-agents via OTel |
| Onyx modified? | No — upstream Docker Compose + transparent witdem-proxy |
| **Costs in Witdem?** | Apply the local Onyx LLM-usage patch, rebuild `api_server`, then chat via the proxy — Witdem shows tokens and model cost when the catalog matches. See [docs/onyx-llm-usage-patch.md](docs/onyx-llm-usage-patch.md). |

## Cases

| Case | Input | Contract | Expected grounding |
| --- | --- | --- | --- |
| `grounded-answer` | Enterprise refund policy | `knowledge_answer` | Yes (seed data) |
| `support-sla` | Enterprise support SLA | `knowledge_answer` | Yes (seed data) |
| `no-evidence` | Fictional Antarctic revenue | `knowledge_answer` | No |

## Development

```bash
pytest -v
```

Unit tests use fixtures only — no live Onyx or Witdem required.

## Troubleshooting

- **Browser hangs on `http://localhost:3000/` or shows blank page:** try
  **http://127.0.0.1:3000/auth/login** (not `localhost` — some browsers cache HSTS for that name).
  If the browser upgrades to HTTPS automatically, use **https://127.0.0.1:3000/auth/login** and
  accept the self-signed certificate once.
- **Still stuck:** close all tabs for `localhost` / `127.0.0.1`, then in Chrome open
  `chrome://net-internals/#hsts` → delete entries for `localhost` and `127.0.0.1`.
  Fallback without Witdem telemetry: **http://127.0.0.1:13000/auth/login** (avoid in browser
  after using the proxy — upstream Onyx sends HSTS headers).
- **Verify the stack from terminal:**
  `curl -sI http://127.0.0.1:3000/auth/login` and
  `curl -s http://127.0.0.1:3001/api/health` should both succeed.
- **Onyx slow on first start:** image pull + DB migration can take 10+ minutes
- **Grounding cases fail:** re-run `bootstrap-onyx.py`, wait for indexing
- **Missing ONYX_API_KEY:** create key in Admin Panel after UI setup
- **OPENAI_API_KEY:** required in `.env` before `stack-up.sh`

See [docs/agency-positioning.md](docs/agency-positioning.md) for integration FAQ.
