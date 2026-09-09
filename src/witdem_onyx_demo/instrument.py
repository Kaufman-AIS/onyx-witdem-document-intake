"""Witdem instrumentation for Onyx chat responses."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from witdem_sdk import configure

from witdem_onyx_demo.cases import DemoCase
from witdem_onyx_demo.client import OnyxClient
from witdem_onyx_demo.contracts import require_contract
from witdem_onyx_demo.env import DEMO_ROOT, load_demo_env
from witdem_onyx_demo.reporting import report_contract
from witdem_onyx_demo.response import normalize_chat_response
from witdem_onyx_demo.telemetry import emit_observed_operations


class InstrumentedOnyxClient:
    def __init__(self, *, config_path: Path, client: OnyxClient) -> None:
        self._config_path = config_path
        self._client = client

    def run_case(self, case: DemoCase) -> dict[str, Any]:
        contract = require_contract(case.contract, context=f"case {case.case_id}")
        execution_name = f"Onyx chat: {case.case_id}"
        with configure(runtime="onyx", config_path=str(self._config_path)) as witdem:
            with witdem.execution(execution_name, attributes={"case_id": case.case_id}):
                with witdem.operation(
                    "onyx.chat",
                    kind="workflow",
                    type="workflow",
                    interface="external_api",
                    input_modalities=["text"],
                ):
                    raw = self._client.send_message(case.message)

                normalized = normalize_chat_response(
                    raw,
                    message=case.message,
                    case_id=case.case_id,
                    expected_grounded=case.expected_grounded,
                )
                emit_observed_operations(
                    witdem,
                    raw=raw,
                    normalized=normalized,
                    input_modalities=["text"],
                )
                report_contract(witdem, contract, normalized)
                return normalized


def create_client(*, config_path: Path | None = None) -> InstrumentedOnyxClient:
    loaded = load_demo_env()
    os.chdir(DEMO_ROOT)
    resolved_config = config_path or (DEMO_ROOT / "witdem.yml")
    http_client = OnyxClient.from_env()
    if loaded:
        print(f"Using env from {loaded}")
    return InstrumentedOnyxClient(config_path=resolved_config, client=http_client)
