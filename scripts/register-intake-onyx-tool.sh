#!/usr/bin/env bash
# Idempotently register the Document Intake OpenAPI tool in Onyx and attach it
# to persona 0 (Assistant). Also ensures persona system_prompt mentions run_intake.
#
# Intended to run on the VPS after Compose is healthy (see deploy-remote.sh).
# Requires: docker, python3, containers onyx-relational_db-1 + onyx-api_server-1.
set -euo pipefail

DB_CONTAINER="${ONYX_DB_CONTAINER:-onyx-relational_db-1}"
API_CONTAINER="${ONYX_API_CONTAINER:-onyx-api_server-1}"
PERSONA_ID="${ONYX_INTAKE_PERSONA_ID:-0}"

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "register-intake-onyx-tool: missing container $DB_CONTAINER" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$API_CONTAINER"; then
  echo "register-intake-onyx-tool: missing container $API_CONTAINER" >&2
  exit 1
fi

python3 - "$DB_CONTAINER" "$API_CONTAINER" "$PERSONA_ID" <<'PY'
import json
import subprocess
import sys

db, api, persona_id = sys.argv[1], sys.argv[2], int(sys.argv[3])

schema = {
    "openapi": "3.0.0",
    "info": {
        "title": "Document Intake",
        "version": "1.0.0",
        "description": (
            "Files invoices and documents to Google Drive and creates "
            "Google Tasks via run_intake."
        ),
    },
    "servers": [{"url": "http://intake:8091"}],
    "paths": {
        "/tools/run_intake": {
            "post": {
                "operationId": "run_intake",
                "summary": "File document to Drive and create Google Tasks",
                "description": (
                    "Pass OCR/message text for classification. For uploads, "
                    "always pass file_id (or user_file_id) from the chat "
                    "attachment so the original PDF/Excel bytes are stored — "
                    "do not rely on file_base64."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "type": "string",
                                        "description": "Document or message text for classification",
                                    },
                                    "filename": {
                                        "type": "string",
                                        "description": "Original filename if known",
                                    },
                                    "mime_type": {
                                        "type": "string",
                                        "description": "MIME type of the file",
                                    },
                                    "file_id": {
                                        "type": "string",
                                        "description": "Onyx chat file id from the uploaded attachment (preferred for binary files)",
                                    },
                                    "user_file_id": {
                                        "type": "string",
                                        "description": "Onyx user_file_id alternative to file_id",
                                    },
                                    "file_base64": {
                                        "type": "string",
                                        "description": "Optional base64 bytes; prefer file_id for uploads",
                                    },
                                    "chat_session_id": {
                                        "type": "string",
                                        "description": "Optional Onyx chat session id",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Intake result with drive path and created tasks"
                    }
                },
            }
        }
    },
}

SYSTEM_SNIPPET = (
    "When the user pastes or uploads an invoice, bureaucracy letter, PDF, Excel "
    "spreadsheet, or any text that should be filed or contains open tasks (payment "
    "deadlines, responses due, follow-ups), call the `run_intake` tool with the message "
    "text and any uploaded file metadata. For uploaded files, always pass `file_id` "
    "(the attachment id) or `user_file_id` so the original binary is filed — never "
    "invent file_base64. Do not ask the user to type special commands — decide from "
    "context. For normal knowledge questions, smalltalk, or content with nothing to "
    "file, answer in chat without calling the tool."
)


def run(cmd, input_bytes=None, check=True):
    proc = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout.decode(errors="replace") + "\n")
        sys.stderr.write(proc.stderr.decode(errors="replace") + "\n")
        raise SystemExit(proc.returncode)
    return proc


def psql(sql: str, tuples_only: bool = False) -> str:
    cmd = [
        "docker",
        "exec",
        "-i",
        db,
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    if tuples_only:
        cmd.extend(["-t", "-A"])
    proc = run(cmd, input_bytes=sql.encode())
    return proc.stdout.decode()


# Validate OpenAPI with Onyx parser
val_code = (
    "import json,sys\n"
    "from onyx.tools.tool_implementations.custom.openapi_parsing import "
    "validate_openapi_schema, openapi_to_method_specs\n"
    "d=json.load(sys.stdin)\n"
    "validate_openapi_schema(d)\n"
    "print([m.name for m in openapi_to_method_specs(d)])\n"
)
val = run(
    ["docker", "exec", "-i", api, "python", "-c", val_code],
    input_bytes=json.dumps(schema).encode(),
)
print("openapi_ops:", val.stdout.decode().strip())

schema_json = json.dumps(schema)
# Upsert custom tool by name
existing = psql(
    "SELECT id FROM tool WHERE name = 'run_intake' AND in_code_tool_id IS NULL "
    "ORDER BY id DESC LIMIT 1;",
    tuples_only=True,
).strip()

if existing:
    tool_id = existing
    psql(
        f"UPDATE tool SET "
        f"description = 'Files invoices and documents to Google Drive and creates Google Tasks.', "
        f"display_name = 'Document Intake', "
        f"openapi_schema = $json${schema_json}$json$::jsonb, "
        f"custom_headers = '[]'::jsonb, "
        f"passthrough_auth = false, "
        f"enabled = true "
        f"WHERE id = {tool_id};"
    )
    print(f"updated tool_id={tool_id}")
else:
    tool_id = psql(
        f"INSERT INTO tool ("
        f"name, description, in_code_tool_id, openapi_schema, "
        f"display_name, custom_headers, passthrough_auth, enabled"
        f") VALUES ("
        f"'run_intake', "
        f"'Files invoices and documents to Google Drive and creates Google Tasks.', "
        f"NULL, "
        f"$json${schema_json}$json$::jsonb, "
        f"'Document Intake', "
        f"'[]'::jsonb, "
        f"false, "
        f"true"
        f") RETURNING id;",
        tuples_only=True,
    ).strip()
    print(f"created tool_id={tool_id}")

psql(
    f"INSERT INTO persona__tool (persona_id, tool_id) "
    f"SELECT {persona_id}, {tool_id} "
    f"WHERE NOT EXISTS ("
    f"  SELECT 1 FROM persona__tool "
    f"  WHERE persona_id = {persona_id} AND tool_id = {tool_id}"
    f");"
)

# Ensure persona system prompt mentions run_intake (append once)
prompt_row = psql(
    f"SELECT coalesce(system_prompt, '') FROM persona WHERE id = {persona_id};",
    tuples_only=True,
)
# psql -t -A may leave trailing newline only
current = prompt_row
if "run_intake" not in current:
    # Escape single quotes for SQL string literal
    addition = ("\n\n" + SYSTEM_SNIPPET) if current.strip() else SYSTEM_SNIPPET
    new_prompt = current.rstrip("\n") + addition
    escaped = new_prompt.replace("'", "''")
    psql(f"UPDATE persona SET system_prompt = '{escaped}' WHERE id = {persona_id};")
    print(f"appended run_intake instructions to persona {persona_id}")
else:
    print(f"persona {persona_id} already mentions run_intake")

print(
    psql(
        "SELECT t.id, t.name, t.display_name, t.enabled, "
        "t.openapi_schema->'servers'->0->>'url' AS server, p.persona_id "
        "FROM tool t JOIN persona__tool p ON p.tool_id = t.id "
        f"WHERE t.id = {tool_id};"
    )
)
print("register-intake-onyx-tool: OK")
PY
