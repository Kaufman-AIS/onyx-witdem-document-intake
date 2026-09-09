"""Map demo payloads to Witdem.report(...) keyword arguments (config v2)."""

from __future__ import annotations

from typing import Any

from witdem_onyx_demo.contracts import (
    CASE_CONTRACT,
    INTAKE_CONTRACT,
    UI_CHAT_CONTRACT,
    UPLOAD_CONTRACT,
)


def report_kwargs_for_contract(contract: str, payload: dict[str, Any]) -> dict[str, Any]:
    if contract == CASE_CONTRACT:
        return _knowledge_answer(payload)
    if contract == UI_CHAT_CONTRACT:
        return _ui_knowledge_answer(payload)
    if contract == UPLOAD_CONTRACT:
        return _document_upload(payload)
    if contract == INTAKE_CONTRACT:
        return _document_intake(payload)
    raise ValueError(f"unsupported contract for report mapping: {contract}")


def report_contract(witdem: Any, contract: str, payload: dict[str, Any]) -> None:
    witdem.report(**report_kwargs_for_contract(contract, payload))


def _knowledge_answer(payload: dict[str, Any]) -> dict[str, Any]:
    answer = str(payload.get("answer") or "").strip()
    has_error = bool(payload.get("has_error"))
    grounded = bool(payload.get("grounded"))
    expected_grounded = bool(payload.get("expected_grounded"))
    decision = "grounded" if grounded else "ungrounded"
    expected_decision = "grounded" if expected_grounded else "ungrounded"
    decision_correct = decision == expected_decision
    result_valid = bool(answer)
    return {
        "contract": CASE_CONTRACT,
        "result": "failed" if has_error else "answered",
        "result_valid": result_valid,
        "decision": decision,
        "expected_decision": expected_decision,
        "decision_correct": decision_correct,
        "requirements": {"useful_grounded_answer": result_valid and decision_correct},
        "metrics": {
            "retrieved_documents": int(payload.get("document_count") or 0),
            "citations": int(payload.get("citation_count") or 0),
        },
        "dimensions": {"case_id": str(payload.get("case_id") or "")},
    }


def _ui_knowledge_answer(payload: dict[str, Any]) -> dict[str, Any]:
    answer = str(payload.get("answer") or "").strip()
    has_error = bool(payload.get("has_error"))
    grounded = bool(payload.get("grounded"))
    result_valid = bool(answer)
    return {
        "contract": UI_CHAT_CONTRACT,
        "result": "failed" if has_error else "answered",
        "result_valid": result_valid,
        "decision": "grounded" if grounded else "ungrounded",
        "requirements": {"useful_answer": result_valid},
        "evidence_sufficient": grounded,
        "metrics": {
            "retrieved_documents": int(payload.get("document_count") or 0),
            "citations": int(payload.get("citation_count") or 0),
        },
        "dimensions": {"source": "ui"},
    }


def _document_upload(payload: dict[str, Any]) -> dict[str, Any]:
    file_count = int(payload.get("file_count") or 0)
    accepted = file_count > 0
    return {
        "contract": UPLOAD_CONTRACT,
        "result": "uploaded",
        "result_valid": accepted,
        "decision": "accepted" if accepted else "rejected",
        "requirements": {"files_accepted": accepted},
        "metrics": {"uploaded_files": file_count},
        "dimensions": {"case_id": str(payload.get("case_id") or "ui-upload")},
    }


def _document_intake(payload: dict[str, Any]) -> dict[str, Any]:
    ok = bool(payload.get("ok"))
    drive_path = str(payload.get("drive_path") or "").strip()
    tasks = payload.get("tasks_created") or []
    if not isinstance(tasks, list):
        tasks = []
    filed = ok and bool(drive_path)
    if not ok:
        result = "failed"
    elif tasks:
        result = "stored_with_tasks"
    else:
        result = "stored"
    return {
        "contract": INTAKE_CONTRACT,
        "result": result,
        "result_valid": filed,
        "decision": "success" if ok else "failure",
        "requirements": {"document_filed": filed},
        "metrics": {"tasks_created": len(tasks)},
        "dimensions": {
            "doc_type": str(payload.get("doc_type") or "other"),
            "source": str(payload.get("source") or "onyx"),
        },
    }
