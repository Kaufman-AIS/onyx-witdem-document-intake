from witdem_onyx_demo.response import normalize_chat_response


def test_normalize_grounded_response(load_fixture):
    raw = load_fixture("chat_full_response.json")
    result = normalize_chat_response(
        raw,
        message="What is the refund policy?",
        case_id="grounded-answer",
        expected_grounded=True,
    )
    assert "30 days" in result["answer"]
    assert result["grounded"] is True
    assert result["document_count"] == 1
    assert result["citation_count"] == 1
    assert result["tool_count"] == 1
    assert result["case_id"] == "grounded-answer"


def test_normalize_empty_documents_not_grounded(load_fixture):
    raw = load_fixture("chat_full_response.json")
    raw = {**raw, "top_documents": [], "citation_info": []}
    result = normalize_chat_response(
        raw,
        message="Unknown topic",
        case_id="no-evidence",
        expected_grounded=False,
    )
    assert result["grounded"] is False
    assert result["document_count"] == 0
