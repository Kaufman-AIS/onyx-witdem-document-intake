# Document intake — Onyx custom tool setup

Wire Onyx to call `run_intake` when a user pastes or uploads content that should be
filed (invoice, bureaucracy, PDF, Excel, open tasks). The intake tool server runs on
the host; Onyx runs in Docker and reaches it via `host.docker.internal`.

## Prerequisites

- Onyx stack running (`./scripts/stack-up.sh`) and admin account created
- Python venv with demo package installed (`pip install -e ".[dev]"`)
- **OpenAI API key** in `.env` (LLM classify/extract when Google creds are set)
- **Google** (optional for real Drive/Tasks; omit creds to use in-memory smoke mode):

| Variable | Purpose |
| --- | --- |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service-account JSON (Drive uploads) |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Drive folder ID where `Invoices/`, `Documents/`, `Other/` are created |
| `GOOGLE_TASKS_LIST_ID` | Google Tasks list ID for open items extracted from documents |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth Desktop client ID (Tasks — company user) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth Desktop client secret |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | From `./scripts/google-oauth-tasks.sh` after browser login |
| `OPENAI_API_KEY` | LLM extraction (required for real classification beyond keyword heuristics) |

Set these in `witdem-oss/.env` (repo root), `examples/.env`, or `examples/onyx-demo/.env`.
`scripts/load-env.sh` loads them in order (demo-local wins).

**Drive** uses the service account (share the Drive root with `client_email`).  
**Tasks** on a company Google account usually need **user OAuth** — a service account cannot see personal task lists. Create an OAuth **Desktop** client (APIs & Services → Credentials), put client id/secret in `.env`, then:

```bash
./scripts/google-oauth-tasks.sh
```

Paste the printed `GOOGLE_OAUTH_REFRESH_TOKEN=…` into `.env` and restart the tool server.

Without `GOOGLE_APPLICATION_CREDENTIALS`, the tool server uses **memory mode**
(`InMemoryDrive` / `InMemoryTasks`) — fine for curl smoke tests, not for real filing.
Force memory mode with `INTAKE_USE_MEMORY=1`.

## 1. Start the stack

```bash
cd examples/onyx-demo
./scripts/stack-up.sh
```

Complete first-time Onyx setup if needed (admin login, LLM provider, API key). See
[README](../README.md).

## 2. Start the intake tool server

In a **second terminal** (keep it running):

```bash
cd examples/onyx-demo
source .venv/bin/activate   # if not already active
./scripts/run-intake-tool.sh
```

Listens on **http://127.0.0.1:8091** (`GET /health`, `POST /tools/run_intake`).

Processing is owned by the **Haystack 2.x pipeline** inside the tool server (classify/extract, Drive, Tasks, confirmation); Witdem records spans under runtime `haystack`.

Quick check:

```bash
curl -s http://127.0.0.1:8091/health
```

## 3. Register the custom tool in Onyx Admin

Onyx runs inside Docker; the tool server runs on your Mac host.

| Onyx location | Tool URL |
| --- | --- |
| Docker Desktop (Mac) — usual case | `http://host.docker.internal:8091/tools/run_intake` |
| Onyx can reach host `localhost` directly | `http://127.0.0.1:8091/tools/run_intake` or `http://localhost:8091/tools/run_intake` |

**Docker Desktop Mac:** `host.docker.internal` resolves from containers to the host
machine. Use that URL when adding the OpenAPI / custom HTTP tool in **Admin Panel →
Tools** (exact menu label may vary by Onyx version).

If Onyx reports connection refused, ensure `run-intake-tool.sh` is running and try
binding uvicorn to all interfaces:  
`.venv/bin/uvicorn witdem_onyx_demo.intake.tool_server:app --host 0.0.0.0 --port 8091`

Paste this **JSON** OpenAPI schema when registering the tool (Onyx expects JSON):

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Document Intake",
    "version": "1.0.0",
    "description": "Files invoices and documents to Google Drive and creates Google Tasks via run_intake."
  },
  "servers": [{ "url": "http://host.docker.internal:8091" }],
  "paths": {
    "/tools/run_intake": {
      "post": {
        "operationId": "run_intake",
        "summary": "File document to Drive and create Google Tasks",
        "description": "Pass OCR/message text for classification. For uploads, always pass file_id (or user_file_id) from the chat attachment so the original PDF/Excel bytes are stored — do not rely on file_base64.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "text": { "type": "string", "description": "Document or message text for classification" },
                  "filename": { "type": "string", "description": "Original filename if known" },
                  "mime_type": { "type": "string", "description": "MIME type of the file" },
                  "file_id": { "type": "string", "description": "Onyx chat file id from the uploaded attachment (preferred for binary files)" },
                  "user_file_id": { "type": "string", "description": "Onyx user_file_id alternative to file_id" },
                  "file_base64": { "type": "string", "description": "Optional base64 bytes; prefer file_id for uploads" },
                  "chat_session_id": { "type": "string", "description": "Optional Onyx chat session id" }
                }
              }
            }
          }
        },
        "responses": {
          "200": { "description": "Intake result with drive path and created tasks" }
        }
      }
    }
  }
}
```

Auth for the action: **None** (Google credentials live on the host tool server).  
The tool server uses `ONYX_API_BASE_URL` + `ONYX_API_KEY` to download original bytes via
`GET /chat/file/{file_id}`. If the model omits `file_id` but sends `filename`, the server
looks up the latest matching upload in `GET /user/files/recent` and downloads that file.
PDF/Excel uploads without resolvable bytes are rejected (no more text-as-fake-PDF).

Attach the tool to the persona you use for chat. If the tool already exists, **edit** its schema to include `file_id` / `user_file_id`.

## 4. Persona instructions

Add to the persona **system / custom instructions** (English example):

> When the user pastes or uploads an invoice, bureaucracy letter, PDF, Excel
> spreadsheet, or any text that should be filed or contains open tasks (payment
> deadlines, responses due, follow-ups), call the `run_intake` tool with the message
> text and any uploaded file metadata. For uploaded files, always pass `file_id`
> (the attachment id) or `user_file_id` so the original binary is filed — never
> invent file_base64. Do not ask the user to type special commands — decide from
> context. For normal knowledge questions, smalltalk, or content with nothing to
> file, answer in chat without calling the tool.

German variant:

> Wenn der Nutzer eine Rechnung, Behördenschreiben, PDF, Excel-Tabelle oder Text
> einfügt/hochlädt, der abgelegt werden soll oder offene Aufgaben enthält (Fristen,
> Zahlungen, Antworten), rufe das Tool `run_intake` mit Text und Datei-Metadaten auf.
> Bei Uploads unbedingt `file_id` (Attachment-ID) oder `user_file_id` mitgeben,
> damit die Originaldatei nach Drive kommt — kein `file_base64` erfinden.
> Keine Sonderbefehle vom Nutzer verlangen — aus dem Kontext entscheiden. Bei normalen
> Wissensfragen oder Smalltalk ohne Ablagebedarf normal antworten, ohne Tool.

## 5. Smoke test

**Terminal (memory or Google mode):**

```bash
curl -s -X POST http://127.0.0.1:8091/tools/run_intake \
  -H 'content-type: application/json' \
  -d '{"text":"Invoice Acme GmbH #1042 — amount EUR 1,240.00 — due 2026-09-30","filename":"acme-1042.pdf"}'
```

Expect JSON with `"ok": true`, a `drive_path`, and optionally `tasks_created`.

**Onyx UI:** open **http://127.0.0.1:3000**, select the persona with the tool, and paste:

```text
Invoice Acme GmbH #1042
Amount: EUR 1,240.00
Due date: 2026-09-30
Please pay by end of month.
```

Expected:

1. Onyx calls `run_intake` (no manual “save” command from you)
2. A file appears in Google Drive (or in-memory path in the tool response)
3. A Google Task is created if the extractor finds an open item (e.g. payment due)
4. Chat shows a confirmation with Drive path and task summary

Irrelevant question control: ask something like “What is our refund policy?” — Onyx
should answer from knowledge base **without** calling `run_intake`.

## 6. Google Drive layout

Every intake run stores the document under:

```text
<Type>/YYYY/YYYY-MM-DD-<Issuer>-invoice-<id>.<ext>

Example: `Invoices/2026/2026-12-31-Google-Workspace-invoice-23984u2938429834u283.pdf`

- Year folder only (no `YYYY-MM` month folder)
- Filename date is the **document/invoice date** (fallback: today)
- Issuer = Rechnungssteller / Absender
- For invoices: `…-invoice-<document_id or description>`
```

| Classified type | Folder prefix |
| --- | --- |
| `invoice` | `Invoices/` |
| `bureaucracy` | `Documents/` |
| `other` | `Other/` |

Example:

```text
Invoices/2026-09/2026-09-07_acme_invoice_1042.pdf
```

Pasted text without an upload is saved as `.txt` in the matching folder.

## Witdem audit

Intake runs emit Witdem telemetry (workflow `document-intake`). Open
**http://localhost:8501** to inspect classify → Drive → Tasks spans after a tool call.

See [document-intake-flow-for-diagram.md](document-intake-flow-for-diagram.md) for the
full architecture diagram brief.
