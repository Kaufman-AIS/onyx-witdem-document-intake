from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from witdem_sdk._contract import load_project_config

from witdem_onyx_demo.contracts import INTAKE_CONTRACT
from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.extract import FakeExtractor
from witdem_onyx_demo.intake.models import IntakeRequest
from witdem_onyx_demo.intake.pipeline import run_intake
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks


def _operation_names(witdem: MagicMock) -> list[str]:
    return [call.args[0] for call in witdem.operation.call_args_list]


@patch("witdem_onyx_demo.intake.pipeline.configure")
def test_run_intake_emits_operation_spans_when_witdem_endpoint_set(
    mock_configure: MagicMock,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WITDEM_ENDPOINT", "http://127.0.0.1:4318")

    witdem = mock_configure.return_value.__enter__.return_value
    witdem.operation.return_value.__enter__.return_value = MagicMock()

    result = run_intake(
        IntakeRequest(
            text="Invoice Acme 1042 due 2026-09-30",
            file_bytes=b"%PDF",
            filename="acme.pdf",
            mime_type="application/pdf",
        ),
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
    )

    assert result.ok is True
    mock_configure.assert_called_once()
    assert mock_configure.call_args.kwargs["runtime"] == "haystack"

    names = _operation_names(witdem)
    assert names == [
        "intake.receive",
        "intake.classify",
        "intake.drive",
        "intake.tasks",
        "intake.confirm",
    ]

    confirm_kwargs = next(
        call.kwargs
        for call in witdem.operation.call_args_list
        if call.args[0] == "intake.confirm"
    )
    assert confirm_kwargs["type"] == "tool"
    assert confirm_kwargs["interface"] == "tool"
    assert confirm_kwargs["type"] != "text_generation"

    witdem.report.assert_called_once()
    kwargs = witdem.report.call_args.kwargs
    assert kwargs["contract"] == INTAKE_CONTRACT
    assert kwargs["result"] == "stored_with_tasks"
    assert kwargs["requirements"]["document_filed"] is True


@patch("witdem_onyx_demo.intake.pipeline.configure")
def test_run_intake_still_emits_tasks_span_when_no_open_items(
    mock_configure: MagicMock,
    monkeypatch,
) -> None:
    monkeypatch.setenv("WITDEM_ENDPOINT", "http://127.0.0.1:4318")

    witdem = mock_configure.return_value.__enter__.return_value
    witdem.operation.return_value.__enter__.return_value = MagicMock()

    result = run_intake(
        IntakeRequest(text="Just a note with no due date"),
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
    )

    assert result.ok is True
    assert _operation_names(witdem) == [
        "intake.receive",
        "intake.classify",
        "intake.drive",
        "intake.tasks",
        "intake.confirm",
    ]
    # CreateTasks always runs in the Haystack graph (often with an empty list).
    assert result.tasks_created == []


def test_document_intake_report_kwargs_match_contract_catalog() -> None:
    from witdem_onyx_demo.reporting import report_kwargs_for_contract

    config = load_project_config(Path(__file__).resolve().parents[1] / "witdem.yml")
    spec = config.contracts[INTAKE_CONTRACT]

    success = report_kwargs_for_contract(
        INTAKE_CONTRACT,
        {
            "ok": True,
            "doc_type": "invoice",
            "drive_path": "Invoices/2026/2026-09-07-Unknown-invoice-Acme.pdf",
            "tasks_created": [{"title": "Pay acme"}],
            "source": "onyx",
        },
    )
    assert success["result"] in spec.result.values
    assert success["requirements"]["document_filed"] is True
    assert set(success["requirements"]) == set(spec.goal.requirements)
    assert set(success["metrics"]) <= set(spec.metrics)
    assert set(success["dimensions"]) <= set(spec.dimensions)

    failure = report_kwargs_for_contract(
        INTAKE_CONTRACT,
        {
            "ok": False,
            "doc_type": "other",
            "drive_path": None,
            "tasks_created": [],
            "source": "onyx",
        },
    )
    assert failure["result"] == "failed"
    assert failure["requirements"]["document_filed"] is False
