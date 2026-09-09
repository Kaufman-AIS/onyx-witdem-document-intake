"""Parse Onyx chat SSE streams into ChatFullResponse-shaped dicts."""

from __future__ import annotations

import json
from typing import Any


def _append_tool(tools: list[dict[str, Any]], *, tool_name: str, tool_id: str | None = None) -> None:
    entry = {"tool_name": tool_name}
    if tool_id:
        entry["tool_id"] = tool_id
    if entry not in tools:
        tools.append(entry)


def sse_to_chat_response(body: str) -> dict[str, Any]:
    """Merge SSE packets into a dict compatible with normalize_chat_response()."""

    answer_parts: list[str] = []
    top_documents: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    citation_info: list[dict[str, Any]] = []
    reasoning_parts: list[str] = []
    error_msg: str | None = None
    chat_session_id: str | None = None
    message_id: int | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    usage: dict[str, int] | None = None

    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload:
            continue
        try:
            packet = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(packet, dict):
            continue

        inner = packet.get("obj") if isinstance(packet.get("obj"), dict) else packet
        if not isinstance(inner, dict):
            continue
        packet_type = inner.get("type")
        if packet_type == "message_start":
            if isinstance(inner.get("content"), str):
                answer_parts.append(inner["content"])
            final_documents = inner.get("final_documents")
            if isinstance(final_documents, list):
                top_documents.extend(doc for doc in final_documents if isinstance(doc, dict))
            if inner.get("chat_session_id"):
                chat_session_id = str(inner["chat_session_id"])
            if inner.get("message_id") is not None:
                message_id = int(inner["message_id"])
        elif packet_type == "message_delta":
            content = inner.get("content")
            if isinstance(content, str):
                answer_parts.append(content)
        elif packet_type == "search_tool_start":
            _append_tool(tool_calls, tool_name="internal_search")
        elif packet_type == "search_tool_documents_delta":
            documents = inner.get("documents")
            if isinstance(documents, list):
                top_documents.extend(doc for doc in documents if isinstance(doc, dict))
        elif packet_type == "custom_tool_start":
            tool_name = inner.get("tool_name")
            if isinstance(tool_name, str):
                tool_id = inner.get("tool_id")
                _append_tool(
                    tool_calls,
                    tool_name=tool_name,
                    tool_id=str(tool_id) if tool_id is not None else None,
                )
        elif packet_type == "citation_info":
            citation_info.append(
                {
                    "citation_num": inner.get("citation_number"),
                    "document_id": inner.get("document_id"),
                }
            )
        elif packet_type == "reasoning_delta":
            reasoning = inner.get("reasoning")
            if isinstance(reasoning, str):
                reasoning_parts.append(reasoning)
        elif packet_type == "error":
            detail = inner.get("error") or inner.get("detail")
            if isinstance(detail, str):
                error_msg = detail
        elif packet_type == "llm_usage":
            if isinstance(inner.get("provider"), str):
                llm_provider = inner["provider"]
            if isinstance(inner.get("model"), str):
                llm_model = inner["model"]
            prompt = inner.get("prompt_tokens")
            completion = inner.get("completion_tokens")
            if isinstance(prompt, int) and isinstance(completion, int):
                usage = {"prompt_tokens": prompt, "completion_tokens": completion}

    answer = "".join(answer_parts)
    return {
        "answer": answer,
        "answer_citationless": answer,
        "pre_answer_reasoning": "".join(reasoning_parts) or None,
        "tool_calls": tool_calls,
        "top_documents": top_documents,
        "citation_info": citation_info,
        "message_id": message_id,
        "chat_session_id": chat_session_id,
        "error_msg": error_msg,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "usage": usage,
    }
