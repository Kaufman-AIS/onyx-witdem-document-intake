from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from witdem_onyx_demo.telemetry import emit_observed_operations, emit_upload_telemetry


class _RecordingOperation:
    def __init__(self, recorded: list[tuple[str, str, dict[str, Any]]], name: str, kwargs: dict[str, Any]) -> None:
        self._recorded = recorded
        self._name = name
        self._kwargs = kwargs

    def usage(self, **kwargs: Any) -> None:
        self._recorded.append(("usage", self._name, kwargs))

    def measure(self, name: str, value: Any, **kwargs: Any) -> None:
        self._recorded.append(("measure", self._name, {"name": name, "value": value, **kwargs}))

    def __enter__(self) -> _RecordingOperation:
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False


class FakeWitdem:
    def __init__(self) -> None:
        self.recorded: list[tuple[str, Any]] = []

    @contextmanager
    def operation(self, name: str, **kwargs: Any):
        self.recorded.append(("operation", name, kwargs))
        yield _RecordingOperation(self.recorded, name, kwargs)

    def complete(self, payload: dict[str, Any], contract: str | None = None) -> None:
        self.recorded.append(("complete", payload, contract))


def test_emit_observed_operations_records_search_when_documents_present() -> None:
    witdem = FakeWitdem()
    raw = {"top_documents": [{}, {}], "tool_calls": [], "answer": "world"}
    normalized = {
        "answer": "world",
        "document_count": 2,
        "citation_count": 0,
    }

    emit_observed_operations(witdem, raw=raw, normalized=normalized, input_modalities=["text"])

    op_names = [entry[1] for entry in witdem.recorded if entry[0] == "operation"]
    assert "onyx.search" in op_names
    assert "onyx.generate" in op_names


def test_emit_observed_operations_reports_llm_usage_on_generate() -> None:
    witdem = FakeWitdem()
    raw = {
        "answer": "world",
        "top_documents": [{}],
        "tool_calls": [],
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }
    normalized = {"answer": "world", "document_count": 1, "citation_count": 0}

    emit_observed_operations(witdem, raw=raw, normalized=normalized, input_modalities=["text"])

    gen_ops = [e for e in witdem.recorded if e[0] == "operation" and e[1] == "onyx.generate"]
    assert gen_ops
    assert gen_ops[0][2].get("provider") == "openai"
    assert gen_ops[0][2].get("model") == "gpt-4o-mini"
    usages = [e for e in witdem.recorded if e[0] == "usage" and e[1] == "onyx.generate"]
    assert usages == [
        ("usage", "onyx.generate", {"input_tokens": 12, "output_tokens": 4})
    ]


def test_emit_observed_operations_skips_usage_when_absent() -> None:
    witdem = FakeWitdem()
    raw = {"answer": "world", "top_documents": [], "tool_calls": []}
    normalized = {"answer": "world", "document_count": 0, "citation_count": 0}
    emit_observed_operations(witdem, raw=raw, normalized=normalized, input_modalities=["text"])
    assert not any(e[0] == "usage" for e in witdem.recorded)


def test_emit_upload_telemetry_records_upload_span() -> None:
    witdem = FakeWitdem()

    emit_upload_telemetry(witdem, file_types=["image", "document"], file_count=2)

    op_names = [entry[1] for entry in witdem.recorded if entry[0] == "operation"]
    assert op_names == ["onyx.upload"]
