from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from witdem_sdk import configure

from witdem_onyx_demo.contracts import INTAKE_CONTRACT, require_contract
from witdem_onyx_demo.env import DEMO_ROOT
from witdem_onyx_demo.intake.drive import DriveClient
from witdem_onyx_demo.reporting import report_contract
from witdem_onyx_demo.intake.extract import Extractor
from witdem_onyx_demo.intake.haystack_pipeline import run_haystack_intake
from witdem_onyx_demo.intake.models import IntakeRequest, IntakeResult
from witdem_onyx_demo.intake.tasks_client import TasksClient


def _contract_payload(request: IntakeRequest, result: IntakeResult) -> dict[str, Any]:
    payload = result.as_tool_dict()
    payload["source"] = request.source
    return payload


def run_intake(
    request: IntakeRequest,
    *,
    drive: DriveClient,
    tasks: TasksClient,
    extractor: Extractor,
) -> IntakeResult:
    # extractor kept for API compatibility; Haystack FakeExtractFields owns extract (Task 4).
    _ = extractor
    if not os.environ.get("WITDEM_ENDPOINT"):
        return run_haystack_intake(request, drive=drive, tasks=tasks)

    contract = require_contract(INTAKE_CONTRACT, context="run_intake")
    config_path = Path(os.environ.get("WITDEM_CONFIG_PATH") or (DEMO_ROOT / "witdem.yml"))
    with configure(runtime="haystack", config_path=str(config_path)) as witdem:
        with witdem.execution("Document intake", attributes={"source": request.source}):
            result = run_haystack_intake(
                request,
                drive=drive,
                tasks=tasks,
                witdem=witdem,
            )
            report_contract(witdem, contract, _contract_payload(request, result))
            return result
