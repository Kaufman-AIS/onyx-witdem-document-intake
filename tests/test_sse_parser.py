from pathlib import Path

from witdem_onyx_demo.sse_parser import sse_to_chat_response


def test_sse_to_chat_response_extracts_answer_and_documents() -> None:
    fixture = Path(__file__).parent / "fixtures" / "chat_stream.sse"
    raw = fixture.read_text(encoding="utf-8")
    result = sse_to_chat_response(raw)
    assert "30 days" in result["answer"]
    assert len(result["top_documents"]) == 1
    assert result["tool_calls"]
    assert len(result["citation_info"]) == 1
    assert result["llm_provider"] == "openai"
    assert result["llm_model"] == "gpt-4o-mini"
    assert result["usage"] == {"prompt_tokens": 50, "completion_tokens": 10}


def test_sse_to_chat_response_reads_llm_usage_flat() -> None:
    body = (
        'data: {"type":"message_delta","content":"hi"}\n\n'
        'data: {"type":"llm_usage","provider":"openai","model":"gpt-4o-mini",'
        '"prompt_tokens":10,"completion_tokens":3}\n\n'
        'data: {"type":"stop"}\n\n'
    )
    result = sse_to_chat_response(body)
    assert result["answer"] == "hi"
    assert result["llm_provider"] == "openai"
    assert result["llm_model"] == "gpt-4o-mini"
    assert result["usage"] == {"prompt_tokens": 10, "completion_tokens": 3}


def test_sse_to_chat_response_reads_llm_usage_nested_packet() -> None:
    body = (
        'data: {"placement":{"turn_index":0},"obj":{"type":"message_delta","content":"yo"}}\n\n'
        'data: {"placement":{"turn_index":0},"obj":{"type":"llm_usage","provider":"openai",'
        '"model":"gpt-4o-mini","prompt_tokens":100,"completion_tokens":20}}\n\n'
    )
    result = sse_to_chat_response(body)
    assert result["answer"] == "yo"
    assert result["usage"]["prompt_tokens"] == 100
    assert result["llm_model"] == "gpt-4o-mini"
