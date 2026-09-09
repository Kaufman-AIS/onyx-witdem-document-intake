#!/usr/bin/env python3
"""Index seed-data markdown into Onyx via the Ingestion API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

from witdem_onyx_demo.env import load_demo_env

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed-data"
load_demo_env()


def main() -> int:
    base = os.environ.get("ONYX_API_BASE_URL", "http://127.0.0.1:3001/api").rstrip("/")
    key = os.environ.get("ONYX_API_KEY")
    if not key:
        print(
            "Set ONYX_API_KEY in .env (Admin Panel → API key with ingestion permissions).",
            file=sys.stderr,
        )
        return 1

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    url = f"{base}/onyx-api/ingestion"

    if not SEED.exists():
        print(f"No seed-data directory at {SEED}", file=sys.stderr)
        return 1

    paths = sorted(SEED.glob("*.md"))
    if not paths:
        print("No markdown files in seed-data/", file=sys.stderr)
        return 1

    with httpx.Client(timeout=120.0) as client:
        for path in paths:
            document_id = f"witdem-seed-{path.stem}"
            body = {
                "document": {
                    "document_id": document_id,
                    "semantic_identifier": path.stem.replace("-", " ").title(),
                    "title": path.stem.replace("-", " ").title(),
                    "from_ingestion_api": True,
                    "sections": [
                        {
                            "text": path.read_text(encoding="utf-8"),
                            "link": f"seed://{path.name}",
                        }
                    ],
                    "metadata": {},
                    "source": "ingestion_api",
                }
            }
            response = client.post(url, headers=headers, json=body)
            if response.status_code >= 400:
                print(f"Failed to index {path.name}: {response.status_code} {response.text}", file=sys.stderr)
                return 1
            print(f"Indexed {path.name}")

    print("Seed ingestion complete. Allow a minute for indexing before run_demo.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
