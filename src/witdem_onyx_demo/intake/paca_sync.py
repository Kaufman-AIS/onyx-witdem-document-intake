"""Optional Paca board sync after successful document intake.

Enabled when ``PACA_API_URL``, ``PACA_API_KEY``, and ``PACA_PROJECT_ID`` are set.
Uses the same REST shape as ``@paca-ai/paca-mcp`` / ticket-workflow-system client.
Google Tasks remain unchanged (parallel).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from witdem_onyx_demo.intake.models import IntakeResult


def _markdown_to_blocknote(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines()]
    paragraphs = [ln for ln in lines if ln] or [text.strip() or ""]
    blocks: list[dict] = []
    for i, paragraph in enumerate(paragraphs, start=1):
        blocks.append(
            {
                "id": str(i),
                "type": "paragraph",
                "props": {
                    "textColor": "default",
                    "backgroundColor": "default",
                    "textAlignment": "left",
                },
                "content": [{"type": "text", "text": paragraph, "styles": {}}],
                "children": [],
            }
        )
    return blocks


def paca_env_configured() -> bool:
    return bool(
        os.environ.get("PACA_API_URL", "").strip()
        and os.environ.get("PACA_API_KEY", "").strip()
        and os.environ.get("PACA_PROJECT_ID", "").strip()
    )


def _unwrap(payload: dict) -> dict:
    if isinstance(payload, dict) and "success" in payload:
        if not payload.get("success", True):
            raise RuntimeError(payload.get("error") or "Paca API error")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    return payload


def sync_intake_to_paca(result: IntakeResult) -> dict[str, Any]:
    """Create a Paca task (+ doc) for a successful intake. Raises on HTTP/API errors."""
    base = os.environ["PACA_API_URL"].rstrip("/")
    key = os.environ["PACA_API_KEY"]
    project_id = os.environ["PACA_PROJECT_ID"]

    title = f"[{result.doc_type}] {result.message.splitlines()[0][:120] or 'intake'}"
    description_parts = [result.message or "Document intake"]
    if result.drive_url:
        description_parts.append(f"Drive: {result.drive_url}")
    if result.drive_path:
        description_parts.append(f"Path: {result.drive_path}")
    description = "\n".join(description_parts)

    headers = {
        "X-API-Key": key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=30.0) as client:
        task_resp = client.post(
            f"/api/v1/projects/{project_id}/tasks",
            json={
                "title": title,
                "description": _markdown_to_blocknote(description),
            },
        )
        if task_resp.status_code >= 400:
            raise RuntimeError(f"Paca task create {task_resp.status_code}: {task_resp.text[:300]}")
        task = _unwrap(task_resp.json())

        doc_md = (
            f"# Intake\n\n{result.message}\n\n"
            f"- doc_type: `{result.doc_type}`\n"
            f"- drive_path: `{result.drive_path or ''}`\n"
            f"- drive_url: {result.drive_url or ''}\n"
        )
        doc_resp = client.post(
            f"/api/v1/projects/{project_id}/docs",
            json={
                "title": f"Intake — {result.doc_type}",
                "content": _markdown_to_blocknote(doc_md),
            },
        )
        if doc_resp.status_code >= 400:
            raise RuntimeError(f"Paca doc create {doc_resp.status_code}: {doc_resp.text[:300]}")
        doc = _unwrap(doc_resp.json())

    return {"task_id": task.get("id"), "document_id": doc.get("id")}


def maybe_sync_intake_to_paca(result: IntakeResult) -> IntakeResult:
    """No-op unless configured. On failure, mark result not ok and set error (loud)."""
    if not result.ok or not paca_env_configured():
        return result
    try:
        created = sync_intake_to_paca(result)
        extra = f" Paca task={created.get('task_id')} doc={created.get('document_id')}."
        result.message = (result.message or "") + extra
        return result
    except Exception as e:  # noqa: BLE001 — surface any sync failure to caller/Witdem
        result.ok = False
        result.error = f"Paca sync failed: {e}"
        result.message = f"{result.message} | {result.error}".strip(" |")
        return result
