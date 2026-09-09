"""Record Witdem telemetry from proxy-observed Onyx traffic."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from witdem_sdk import configure

from witdem_onyx_demo.contracts import require_contract
from witdem_onyx_demo.reporting import report_contract
from witdem_onyx_demo.response import normalize_chat_response
from witdem_onyx_demo.telemetry import emit_observed_operations, emit_upload_telemetry

logger = logging.getLogger(__name__)


def input_modalities_from_request(body: dict[str, Any]) -> list[str]:
    modalities: list[str] = []
    if body.get("message"):
        modalities.append("text")
    descriptors = body.get("file_descriptors") or []
    if isinstance(descriptors, list):
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                continue
            file_type = descriptor.get("type")
            if file_type == "image" and "image" not in modalities:
                modalities.append("image")
            elif file_type in {"document", "plain_text", "csv"} and "document" not in modalities:
                modalities.append("document")
    return modalities or ["text"]


def record_chat_execution(
    *,
    config_path: Path,
    raw: dict[str, Any],
    message: str,
    input_modalities: list[str],
    execution_name: str,
    contract: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    contract_name = require_contract(contract, context="record_chat_execution")
    try:
        normalized = normalize_chat_response(
            raw,
            message=message,
            case_id="ui",
            expected_grounded=False,
        )
        with configure(runtime="onyx", config_path=str(config_path)) as witdem:
            with witdem.execution(execution_name, attributes=attributes or {}):
                with witdem.operation(
                    "onyx.chat",
                    kind="workflow",
                    type="workflow",
                    interface="external_api",
                    input_modalities=input_modalities,
                ):
                    pass
                emit_observed_operations(
                    witdem,
                    raw=raw,
                    normalized=normalized,
                    input_modalities=input_modalities,
                )
                report_contract(witdem, contract_name, normalized)
    except Exception:
        logger.exception("Failed to record Witdem chat telemetry")


def record_upload_execution(
    *,
    config_path: Path,
    file_types: list[str],
    file_count: int,
    contract: str,
) -> None:
    contract_name = require_contract(contract, context="record_upload_execution")
    try:
        with configure(runtime="onyx", config_path=str(config_path)) as witdem:
            with witdem.execution("Onyx UI upload", attributes={"source": "onyx_ui"}):
                emit_upload_telemetry(witdem, file_types=file_types, file_count=file_count)
                report_contract(
                    witdem,
                    contract_name,
                    {
                        "file_count": file_count,
                        "file_types": file_types,
                        "case_id": "ui-upload",
                    },
                )
    except Exception:
        logger.exception("Failed to record Witdem upload telemetry")
