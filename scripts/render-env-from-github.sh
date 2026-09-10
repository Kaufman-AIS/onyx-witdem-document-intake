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
# Write via Python so keys with /, &, $, etc. do not break shell/sed.
python3 - "$OUT" "$ROOT" <<'PY'
import os
import sys
from pathlib import Path

out = Path(sys.argv[1])
root = Path(sys.argv[2])
vals = {
    "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
    "ONYX_API_BASE_URL": os.environ.get("ONYX_API_BASE_URL", "http://api_server:8080"),
    "ONYX_API_KEY": os.environ.get("ONYX_API_KEY", ""),
    "ONYX_PERSONA_ID": os.environ.get("ONYX_PERSONA_ID", ""),
    "WITDEM_ENDPOINT": os.environ.get("WITDEM_ENDPOINT", "http://witdem:4318"),
    "WITDEM_API_KEY": os.environ.get("WITDEM_API_KEY", ""),
    "INTAKE_USE_MEMORY": os.environ.get("INTAKE_USE_MEMORY", "0"),
    "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", "/run/secrets/google-sa.json"
    ),
    "GOOGLE_DRIVE_ROOT_FOLDER_ID": os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID", ""),
    "GOOGLE_TASKS_LIST_ID": os.environ.get("GOOGLE_TASKS_LIST_ID", ""),
    "GOOGLE_OAUTH_CLIENT_ID": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
    "GOOGLE_OAUTH_CLIENT_SECRET": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
    "GOOGLE_OAUTH_REFRESH_TOKEN": os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", ""),
}

# Prefer non-empty GitHub/env value; else secrets/onyx-api-key; else previous .env.
if not vals["ONYX_API_KEY"]:
    secret_file = root / "secrets" / "onyx-api-key"
    if secret_file.is_file():
        vals["ONYX_API_KEY"] = secret_file.read_text(encoding="utf-8").strip()
    elif out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.startswith("ONYX_API_KEY="):
                vals["ONYX_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
                break

def escape(value: str) -> str:
    # Keep Compose/dotenv single-line; never wrap in quotes (keys may contain ").
    return value.replace("\r", "").replace("\n", "")

out.write_text("".join(f"{k}={escape(v)}\n" for k, v in vals.items()), encoding="utf-8")
out.chmod(0o600)
print(f"wrote {out}")

compose_env = root / ".onyx-upstream/deployment/docker_compose/.env"
if compose_env.parent.is_dir():
    lines = compose_env.read_text(encoding="utf-8").splitlines() if compose_env.exists() else []
    key = "OPENAI_API_KEY"
    val = escape(os.environ["OPENAI_API_KEY"])
    found = False
    out_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            out_lines.append(f"{key}={val}")
            found = True
        else:
            out_lines.append(line)
    if not found:
        out_lines.append(f"{key}={val}")
    if not any(line.startswith("HOST_PORT=") for line in out_lines):
        out_lines.append("HOST_PORT=13000")
    compose_env.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    compose_env.chmod(0o600)
    print(f"updated {compose_env}")
PY
