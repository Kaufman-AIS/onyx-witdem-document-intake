from pathlib import Path

from witdem_sdk._contract import load_project_config

from witdem_onyx_demo.contracts import INTAKE_CONTRACT


def test_witdem_config_declares_document_intake_contract_and_workflow() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(root / "witdem.yml")

    assert INTAKE_CONTRACT == "document_intake"
    assert "document_intake" in config.contracts
    assert "workflows/document-intake.yml" in config.workflows
    assert (root / "workflows" / "document-intake.yml").is_file()
    assert "document-intake" in config.workflow_definitions
    assert set(config.contracts[INTAKE_CONTRACT].result.values) == {
        "failed",
        "stored",
        "stored_with_tasks",
    }
