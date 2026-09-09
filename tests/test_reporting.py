from witdem_onyx_demo.contracts import (
    CASE_CONTRACT,
    INTAKE_CONTRACT,
    UI_CHAT_CONTRACT,
    UPLOAD_CONTRACT,
)
from witdem_onyx_demo.reporting import report_kwargs_for_contract


def test_knowledge_answer_success_kwargs() -> None:
    kwargs = report_kwargs_for_contract(
        CASE_CONTRACT,
        {
            "answer": "SLA is 24h",
            "grounded": True,
            "expected_grounded": True,
            "has_error": False,
            "document_count": 2,
            "citation_count": 1,
            "case_id": "support-sla",
        },
    )
    assert kwargs["contract"] == CASE_CONTRACT
    assert kwargs["result"] == "answered"
    assert kwargs["result_valid"] is True
    assert kwargs["decision"] == "grounded"
    assert kwargs["expected_decision"] == "grounded"
    assert kwargs["decision_correct"] is True
    assert kwargs["requirements"] == {"useful_grounded_answer": True}
    assert kwargs["metrics"] == {"retrieved_documents": 2, "citations": 1}
    assert kwargs["dimensions"] == {"case_id": "support-sla"}


def test_knowledge_answer_mismatch_fails_goal() -> None:
    kwargs = report_kwargs_for_contract(
        CASE_CONTRACT,
        {
            "answer": "guess",
            "grounded": False,
            "expected_grounded": True,
            "has_error": False,
            "document_count": 0,
            "citation_count": 0,
            "case_id": "no-evidence",
        },
    )
    assert kwargs["decision_correct"] is False
    assert kwargs["requirements"] == {"useful_grounded_answer": False}


def test_ui_knowledge_answer_kwargs() -> None:
    kwargs = report_kwargs_for_contract(
        UI_CHAT_CONTRACT,
        {
            "answer": "hi",
            "grounded": True,
            "has_error": False,
            "document_count": 1,
            "citation_count": 0,
        },
    )
    assert kwargs["contract"] == UI_CHAT_CONTRACT
    assert kwargs["result"] == "answered"
    assert kwargs["decision"] == "grounded"
    assert "expected_decision" not in kwargs
    assert kwargs["requirements"] == {"useful_answer": True}
    assert kwargs["evidence_sufficient"] is True
    assert kwargs["dimensions"] == {"source": "ui"}


def test_upload_kwargs() -> None:
    kwargs = report_kwargs_for_contract(
        UPLOAD_CONTRACT,
        {"file_count": 2, "file_types": ["pdf"], "case_id": "ui-upload"},
    )
    assert kwargs["result"] == "uploaded"
    assert kwargs["requirements"] == {"files_accepted": True}
    assert kwargs["metrics"] == {"uploaded_files": 2}
    assert kwargs["dimensions"] == {"case_id": "ui-upload"}


def test_intake_success_with_tasks() -> None:
    kwargs = report_kwargs_for_contract(
        INTAKE_CONTRACT,
        {
            "ok": True,
            "drive_path": "Invoices/2026/x.pdf",
            "tasks_created": [{"title": "Pay"}],
            "doc_type": "invoice",
            "source": "onyx",
        },
    )
    assert kwargs["result"] == "stored_with_tasks"
    assert kwargs["requirements"] == {"document_filed": True}
    assert kwargs["decision"] == "success"
    assert kwargs["metrics"] == {"tasks_created": 1}
    assert kwargs["dimensions"] == {"doc_type": "invoice", "source": "onyx"}


def test_intake_failure() -> None:
    kwargs = report_kwargs_for_contract(
        INTAKE_CONTRACT,
        {
            "ok": False,
            "drive_path": None,
            "tasks_created": [],
            "doc_type": "other",
            "source": "onyx",
        },
    )
    assert kwargs["result"] == "failed"
    assert kwargs["requirements"] == {"document_filed": False}
    assert kwargs["decision"] == "failure"
