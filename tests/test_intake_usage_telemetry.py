from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

from haystack.dataclasses import ChatMessage

from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.haystack_pipeline import (
    _maybe_report_classify_usage,
    run_haystack_intake,
    usage_from_openai_replies,
)
from witdem_onyx_demo.intake.models import IntakeRequest
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks


class _RecordingSpan:
    def __init__(self, recorded: list[tuple[str, Any]], name: str) -> None:
        self._recorded = recorded
        self._name = name

    def set_attribute(self, key: str, value: Any) -> None:
        self._recorded.append(("attribute", self._name, {key: value}))


class _RecordingOperation:
    def __init__(
        self,
        recorded: list[tuple[str, Any]],
        name: str,
        kwargs: dict[str, Any],
    ) -> None:
        self._recorded = recorded
        self._name = name
        self._kwargs = kwargs
        self.span = _RecordingSpan(recorded, name)

    def usage(self, **kwargs: Any) -> None:
        self._recorded.append(("usage", self._name, kwargs))

    def response_model(self, model: str | None) -> _RecordingOperation:
        if model:
            self._recorded.append(("response_model", self._name, model))
        return self

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


def test_usage_from_openai_replies_extracts_meta() -> None:
    replies = [
        ChatMessage.from_assistant(
            '{"doc_type":"invoice"}',
            meta={
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 42, "completion_tokens": 7},
            },
        )
    ]
    info = usage_from_openai_replies(replies)
    assert info == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "prompt_tokens": 42,
        "completion_tokens": 7,
    }


def test_usage_from_openai_replies_returns_none_without_usage() -> None:
    replies = [ChatMessage.from_assistant("hi", meta={"model": "gpt-4o-mini"})]
    assert usage_from_openai_replies(replies) is None
    assert usage_from_openai_replies([]) is None


def test_maybe_report_classify_usage_reports_provider_model_and_tokens() -> None:
    witdem = FakeWitdem()
    with witdem.operation(
        "intake.classify",
        kind="component",
        type="text_generation",
        interface="model_api",
    ) as classify_op:
        _maybe_report_classify_usage(
            classify_op,
            {
                "llm": {
                    "replies": [
                        ChatMessage.from_assistant(
                            "{}",
                            meta={
                                "model": "gpt-4o-mini",
                                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                            },
                        )
                    ]
                }
            },
            use_llm=True,
        )

    usages = [e for e in witdem.recorded if e[0] == "usage" and e[1] == "intake.classify"]
    assert usages == [
        ("usage", "intake.classify", {"input_tokens": 10, "output_tokens": 3})
    ]
    attrs = [e[2] for e in witdem.recorded if e[0] == "attribute" and e[1] == "intake.classify"]
    assert {"gen_ai.provider.name": "openai"} in attrs
    assert {"gen_ai.request.model": "gpt-4o-mini"} in attrs
    models = [e[2] for e in witdem.recorded if e[0] == "response_model" and e[1] == "intake.classify"]
    assert models == ["gpt-4o-mini"]


def test_maybe_report_classify_usage_noops_for_fake_extract() -> None:
    witdem = FakeWitdem()
    with witdem.operation("intake.classify") as classify_op:
        _maybe_report_classify_usage(
            classify_op,
            {"extract": {"doc_type": "invoice"}},
            use_llm=False,
        )
    assert not any(e[0] == "usage" for e in witdem.recorded)


@patch("witdem_onyx_demo.intake.haystack_pipeline.build_intake_pipeline")
def test_run_haystack_intake_reports_classify_usage(mock_build: MagicMock, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    pipe = MagicMock()
    mock_build.return_value = pipe
    pipe.run.return_value = {
        "llm": {
            "replies": [
                ChatMessage.from_assistant(
                    '{"doc_type":"invoice","description":"x","ext":"pdf","tasks":[]}',
                    meta={
                        "model": "gpt-4o-mini",
                        "usage": {"prompt_tokens": 55, "completion_tokens": 12},
                    },
                )
            ]
        },
        "confirm": {
            "ok": True,
            "doc_type": "invoice",
            "drive_path": "Invoices/2026/x.pdf",
            "drive_url": "https://drive.example/x",
            "tasks_created": [],
            "message": "Saved",
        },
    }

    witdem = FakeWitdem()
    result = run_haystack_intake(
        IntakeRequest(text="Invoice Acme"),
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        witdem=witdem,
    )
    assert result.ok is True

    classify_ops = [e for e in witdem.recorded if e[0] == "operation" and e[1] == "intake.classify"]
    assert classify_ops
    usages = [e for e in witdem.recorded if e[0] == "usage" and e[1] == "intake.classify"]
    assert usages == [
        ("usage", "intake.classify", {"input_tokens": 55, "output_tokens": 12})
    ]
    # Haystack omits intermediate component outputs unless requested.
    run_kwargs = pipe.run.call_args.kwargs
    include = run_kwargs.get("include_outputs_from") or set()
    assert "llm" in set(include)
