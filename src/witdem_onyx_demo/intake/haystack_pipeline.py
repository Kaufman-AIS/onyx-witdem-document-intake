from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage

from witdem_onyx_demo.intake.drive import DriveClient
from witdem_onyx_demo.intake.extract import _LLM_SYSTEM
from witdem_onyx_demo.intake.haystack_components import (
    BuildConfirmation,
    CreateTasks,
    DocumentToExtractVars,
    DriveUpload,
    FakeExtractFields,
    ParseLlmJson,
    ReceiveDocument,
)
from witdem_onyx_demo.intake.models import IntakeRequest, IntakeResult, TaskItem
from witdem_onyx_demo.intake.tasks_client import TasksClient

_EXTRACT_FIELDS = (
    "doc_type",
    "description",
    "ext",
    "issuer",
    "document_id",
    "document_date",
    "tasks",
)


def _openai_api_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _connect_extract_to_drive(pipe: Pipeline) -> None:
    for field in _EXTRACT_FIELDS:
        pipe.connect(f"extract.{field}", f"drive.{field}")


def _add_llm_extract(pipe: Pipeline) -> None:
    prompt = ChatPromptBuilder(
        template=[
            ChatMessage.from_system(_LLM_SYSTEM),
            ChatMessage.from_user("filename: {{ filename }}\n\n---\n{{ text }}"),
        ],
        required_variables=["text", "filename"],
    )
    llm = OpenAIChatGenerator(
        model="gpt-4o-mini",
        generation_kwargs={
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
    )
    pipe.add_component("doc_vars", DocumentToExtractVars())
    pipe.add_component("prompt", prompt)
    pipe.add_component("llm", llm)
    pipe.add_component("extract", ParseLlmJson())

    pipe.connect("receive.document", "doc_vars.document")
    pipe.connect("doc_vars.text", "prompt.text")
    pipe.connect("doc_vars.filename", "prompt.filename")
    pipe.connect("prompt.prompt", "llm.messages")
    pipe.connect("llm.replies", "extract.replies")
    pipe.connect("doc_vars.filename", "extract.filename")


def build_intake_pipeline(
    *,
    drive: DriveClient,
    tasks: TasksClient,
    use_llm: bool = False,
) -> Pipeline:
    pipe = Pipeline()
    pipe.add_component("receive", ReceiveDocument())
    pipe.add_component("drive", DriveUpload(drive=drive))
    pipe.add_component("create_tasks", CreateTasks(tasks_client=tasks))
    pipe.add_component("confirm", BuildConfirmation())

    if use_llm and _openai_api_key_present():
        _add_llm_extract(pipe)
    else:
        pipe.add_component("extract", FakeExtractFields())
        pipe.connect("receive.document", "extract.document")

    pipe.connect("receive.document", "drive.document")
    _connect_extract_to_drive(pipe)
    pipe.connect("drive.tasks", "create_tasks.tasks")
    pipe.connect("drive.drive_path", "confirm.drive_path")
    pipe.connect("drive.drive_url", "confirm.drive_url")
    pipe.connect("drive.doc_type", "confirm.doc_type")
    pipe.connect("create_tasks.tasks_created", "confirm.tasks_created")
    return pipe


def _operation(witdem: Any | None, name: str, **kwargs: Any):
    if witdem is None:
        return nullcontext()
    return witdem.operation(name, **kwargs)


def usage_from_openai_replies(replies: list) -> dict[str, Any] | None:
    """Return provider/model/token counts from Haystack ChatMessage meta when present."""

    if not replies:
        return None
    first = replies[0]
    meta = first.meta if isinstance(first, ChatMessage) else None
    if not isinstance(meta, dict):
        return None
    usage = meta.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    model = meta.get("model")
    return {
        "provider": "openai",
        "model": model if isinstance(model, str) else None,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
    }


def _maybe_report_classify_usage(
    operation: Any,
    outputs: dict[str, Any],
    *,
    use_llm: bool,
    default_model: str = "gpt-4o-mini",
) -> None:
    if not use_llm or operation is None:
        return
    llm_out = outputs.get("llm")
    if not isinstance(llm_out, dict):
        return
    replies = llm_out.get("replies")
    if not isinstance(replies, list):
        return
    info = usage_from_openai_replies(replies)
    if info is None:
        return
    provider = info.get("provider")
    model = info.get("model") or default_model
    if isinstance(provider, str):
        operation.span.set_attribute("gen_ai.provider.name", provider)
    if isinstance(model, str):
        operation.span.set_attribute("gen_ai.request.model", model)
        operation.response_model(model)
    operation.usage(
        input_tokens=info["prompt_tokens"],
        output_tokens=info["completion_tokens"],
    )


def _tasks_from_confirm(raw: list | None) -> list[TaskItem]:
    return [
        TaskItem(
            title=t["title"],
            notes=t.get("notes"),
            due=t.get("due"),
            task_id=t.get("task_id"),
        )
        for t in (raw or [])
    ]


def run_haystack_intake(
    request: IntakeRequest,
    *,
    drive: DriveClient,
    tasks: TasksClient,
    witdem: Any | None = None,
) -> IntakeResult:
    use_llm = _openai_api_key_present()
    pipe = build_intake_pipeline(drive=drive, tasks=tasks, use_llm=use_llm)
    try:
        # Nested spans preserve call order for Witdem workflow matching while a
        # single Pipeline.run owns the real component graph. CreateTasks always
        # runs in the graph, so intake.tasks is always emitted.
        with _operation(witdem, "intake.receive", kind="workflow", type="workflow"):
            inputs = {
                "receive": {
                    "text": request.text or "",
                    "filename": request.filename,
                    "mime_type": request.mime_type,
                    "has_file_bytes": request.file_bytes is not None,
                },
                "drive": {
                    "file_bytes": request.file_bytes,
                },
            }
            with _operation(
                witdem,
                "intake.classify",
                kind="component",
                type="text_generation",
                interface="model_api",
            ) as classify_op:
                with _operation(
                    witdem,
                    "intake.drive",
                    kind="component",
                    type="tool",
                    interface="tool",
                ):
                    with _operation(
                        witdem,
                        "intake.tasks",
                        kind="component",
                        type="tool",
                        interface="tool",
                    ):
                        with _operation(
                            witdem,
                            "intake.confirm",
                            kind="component",
                            type="tool",
                            interface="tool",
                        ):
                            # Intermediate "llm" outputs are omitted unless requested;
                            # usage telemetry needs ChatMessage.meta from that step.
                            run_kwargs: dict[str, Any] = {"data": inputs}
                            if use_llm:
                                run_kwargs["include_outputs_from"] = {"llm"}
                            outputs = pipe.run(**run_kwargs)
                            _maybe_report_classify_usage(
                                classify_op,
                                outputs,
                                use_llm=use_llm,
                            )

        confirm = outputs.get("confirm") or {}
        return IntakeResult(
            ok=bool(confirm.get("ok")),
            doc_type=confirm.get("doc_type") or "other",
            drive_path=confirm.get("drive_path"),
            drive_url=confirm.get("drive_url"),
            tasks_created=_tasks_from_confirm(confirm.get("tasks_created")),
            message=confirm.get("message") or "",
        )
    except Exception as e:
        root = e.__cause__ if e.__cause__ is not None else e
        return IntakeResult(
            ok=False,
            doc_type="other",
            drive_path=None,
            drive_url=None,
            error=str(root),
            message=f"Intake failed: {root}",
        )
