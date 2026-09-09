from __future__ import annotations

import pytest

from witdem_onyx_demo.contracts import (
    CASE_CONTRACT,
    INTAKE_CONTRACT,
    UI_CHAT_CONTRACT,
    UPLOAD_CONTRACT,
    require_contract,
)


def test_require_contract_rejects_missing() -> None:
    with pytest.raises(ValueError, match="workflow contract is required"):
        require_contract(None, context="record_chat_execution")

    with pytest.raises(ValueError, match="workflow contract is required"):
        require_contract("", context="record_chat_execution")

    with pytest.raises(ValueError, match="workflow contract is required"):
        require_contract("   ", context="record_chat_execution")


def test_require_contract_returns_stripped_name() -> None:
    assert require_contract("  knowledge_answer  ", context="run_case") == "knowledge_answer"


def test_contract_constants_are_distinct() -> None:
    names = {CASE_CONTRACT, UI_CHAT_CONTRACT, UPLOAD_CONTRACT, INTAKE_CONTRACT}
    assert len(names) == 4
