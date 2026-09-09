"""Shared Witdem span emission for Onyx chat and upload responses."""

from __future__ import annotations

from typing import Any


def _tool_label(tool_call: dict[str, Any]) -> str:
    for key in ("tool_name", "name", "tool_id"):
        value = tool_call.get(key)
        if isinstance(value, str) and value:
            return value.replace(" ", "_")
    return "unknown"


def emit_observed_operations(
    witdem: Any,
    *,
    raw: dict[str, Any],
    normalized: dict[str, Any],
    input_modalities: list[str],
) -> None:
    top_documents = raw.get("top_documents") or []
    if isinstance(top_documents, list) and top_documents:
        with witdem.operation(
            "onyx.search",
            kind="component",
            type="retrieval",
            interface="search_service",
            input_modalities=list(input_modalities),
            output_modalities=["document"],
        ) as operation:
            operation.measure(
                "documents.output",
                len(top_documents),
                unit="document",
                provenance="runtime_reported",
            )

    tool_calls = raw.get("tool_calls") or []
    if isinstance(tool_calls, list):
        for index, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                continue
            label = _tool_label(tool_call)
            with witdem.operation(
                f"onyx.tool.{label}",
                kind="component",
                type="tool",
                interface="tool",
                attributes={"onyx.tool.index": index},
            ):
                pass

    reasoning = raw.get("pre_answer_reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        with witdem.operation(
            "onyx.reasoning",
            kind="component",
            type="x.onyx.reasoning",
            interface="model_api",
        ):
            pass

    if normalized.get("answer"):
        generate_kwargs: dict[str, Any] = {
            "kind": "component",
            "type": "text_generation",
            "interface": "model_api",
            "input_modalities": list(input_modalities),
            "output_modalities": ["text"],
        }
        llm_provider = raw.get("llm_provider")
        if isinstance(llm_provider, str):
            generate_kwargs["provider"] = llm_provider
        llm_model = raw.get("llm_model")
        if isinstance(llm_model, str):
            generate_kwargs["model"] = llm_model

        with witdem.operation("onyx.generate", **generate_kwargs) as operation:
            operation.measure(
                "documents.output",
                normalized.get("document_count", 0),
                unit="document",
                provenance="runtime_reported",
            )
            usage = raw.get("usage")
            if isinstance(usage, dict):
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    operation.usage(input_tokens=input_tokens, output_tokens=output_tokens)


def emit_upload_telemetry(
    witdem: Any,
    *,
    file_types: list[str],
    file_count: int,
) -> None:
    with witdem.operation(
        "onyx.upload",
        kind="component",
        type="document",
        interface="external_api",
        input_modalities=file_types or ["document"],
        output_modalities=["document"],
        attributes={"onyx.upload.file_count": file_count},
    ) as operation:
        operation.measure(
            "files.uploaded",
            file_count,
            unit="file",
            provenance="runtime_reported",
        )
