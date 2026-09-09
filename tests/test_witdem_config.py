from pathlib import Path

from witdem_sdk._contract import load_project_config

from witdem_onyx_demo.contracts import CASE_CONTRACT, UI_CHAT_CONTRACT, UPLOAD_CONTRACT


def test_witdem_config_declares_workflow_contracts() -> None:
    config_path = Path(__file__).resolve().parents[1] / "witdem.yml"
    config = load_project_config(config_path)

    assert config.version == 2
    assert config.default_workflow == "onyx-agent"
    assert config.default_contract == CASE_CONTRACT
    assert {CASE_CONTRACT, UI_CHAT_CONTRACT, UPLOAD_CONTRACT}.issubset(config.contracts)
    assert config.workflows == [
        "workflows/onyx-agent.yml",
        "workflows/document-intake.yml",
    ]
    assert set(config.workflow_definitions) == {"onyx-agent", "document-intake"}
