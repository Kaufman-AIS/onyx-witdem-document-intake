"""Parse Onyx ChatFullResponse payloads into Witdem contract input."""

from __future__ import annotations

from typing import Any


def _tool_name(tool_call: dict[str, Any]) -> str:
    for key in ("tool_name", "name", "tool_id"):
        value = tool_call.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def normalize_chat_response(
    raw: dict[str, Any],
    *,
    message: str,
    case_id: str,
    expected_grounded: bool,
) -> dict[str, Any]:
    """Map Onyx non-streaming chat JSON to the demo contract result shape."""

    answer = str(raw.get("answer") or "")
    top_documents = raw.get("top_documents") or []
    if not isinstance(top_documents, list):
        top_documents = []

    tool_calls = raw.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        tool_calls = []

    citation_info = raw.get("citation_info") or []
    if not isinstance(citation_info, list):
        citation_info = []

    tools_used = [_tool_name(item) for item in tool_calls if isinstance(item, dict)]
    error_msg = raw.get("error_msg")
    document_count = len(top_documents)
    grounded = document_count > 0

    return {
        "message": message,
        "answer": answer,
        "answer_citationless": str(raw.get("answer_citationless") or answer),
        "grounded": grounded,
        "citation_count": len(citation_info),
        "document_count": document_count,
        "tool_count": len(tool_calls),
        "tools_used": tools_used,
        "has_error": bool(error_msg) or not answer,
        "error_msg": str(error_msg) if error_msg else None,
        "chat_session_id": raw.get("chat_session_id"),
        "message_id": raw.get("message_id"),
        "expected_grounded": expected_grounded,
        "case_id": case_id,
    }
