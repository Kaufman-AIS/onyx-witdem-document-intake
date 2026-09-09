"""Workflow contract names and enforcement for the Onyx demo."""

from __future__ import annotations

CASE_CONTRACT = "knowledge_answer"
UI_CHAT_CONTRACT = "ui_knowledge_answer"
UPLOAD_CONTRACT = "document_upload"
INTAKE_CONTRACT = "document_intake"


def require_contract(contract: str | None, *, context: str) -> str:
    """Return a non-empty workflow contract name or raise."""

    if contract is None or not str(contract).strip():
        raise ValueError(f"{context}: workflow contract is required")
    return str(contract).strip()
