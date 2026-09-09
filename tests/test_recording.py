from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from witdem_onyx_demo.contracts import UI_CHAT_CONTRACT, UPLOAD_CONTRACT
from witdem_onyx_demo.proxy.recording import record_chat_execution, record_upload_execution


def test_record_chat_execution_requires_contract(tmp_path: Path) -> None:
    config_path = tmp_path / "witdem.yml"
    config_path.write_text("version: 1\nservice:\n  name: test\n  runtime: onyx\n", encoding="utf-8")

    with pytest.raises(ValueError, match="workflow contract is required"):
        record_chat_execution(
            config_path=config_path,
            raw={"answer": "hello"},
            message="hello",
            input_modalities=["text"],
            execution_name="Onyx UI chat: new",
            contract=None,
        )


@patch("witdem_onyx_demo.proxy.recording.configure")
def test_record_chat_execution_passes_explicit_contract(mock_configure, tmp_path: Path) -> None:
    config_path = tmp_path / "witdem.yml"
    config_path.write_text("version: 1\nservice:\n  name: test\n  runtime: onyx\n", encoding="utf-8")

    witdem = mock_configure.return_value.__enter__.return_value
    record_chat_execution(
        config_path=config_path,
        raw={"answer": "hello", "top_documents": [{}]},
        message="hello",
        input_modalities=["text"],
        execution_name="Onyx UI chat: session-1",
        contract=UI_CHAT_CONTRACT,
        attributes={"source": "onyx_ui"},
    )

    witdem.report.assert_called_once()
    kwargs = witdem.report.call_args.kwargs
    assert kwargs["contract"] == UI_CHAT_CONTRACT


@patch("witdem_onyx_demo.proxy.recording.configure")
def test_record_upload_execution_passes_upload_contract(mock_configure, tmp_path: Path) -> None:
    config_path = tmp_path / "witdem.yml"
    config_path.write_text("version: 1\nservice:\n  name: test\n  runtime: onyx\n", encoding="utf-8")

    witdem = mock_configure.return_value.__enter__.return_value
    record_upload_execution(
        config_path=config_path,
        file_types=["image"],
        file_count=1,
        contract=UPLOAD_CONTRACT,
    )

    witdem.report.assert_called_once()
    kwargs = witdem.report.call_args.kwargs
    assert kwargs["contract"] == UPLOAD_CONTRACT
