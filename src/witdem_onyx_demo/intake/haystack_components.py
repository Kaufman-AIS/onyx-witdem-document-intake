from __future__ import annotations

import json
from datetime import date
from typing import Any

from haystack import Document, component
from haystack.dataclasses import ChatMessage

from witdem_onyx_demo.intake.drive import DriveClient
from witdem_onyx_demo.intake.extract import FakeExtractor, _parse_llm_payload
from witdem_onyx_demo.intake.models import TaskItem
from witdem_onyx_demo.intake.paths import build_drive_relative_path
from witdem_onyx_demo.intake.tasks_client import TasksClient


@component
class ReceiveDocument:
    @component.output_types(document=Document)
    def run(
        self,
        text: str,
        filename: str | None = None,
        mime_type: str | None = None,
        has_file_bytes: bool = False,
    ) -> dict[str, Any]:
        return {
            "document": Document(
                content=text,
                meta={
                    "filename": filename,
                    "mime_type": mime_type,
                    "has_file_bytes": has_file_bytes,
                },
            )
        }


def _extracted_to_outputs(extracted) -> dict[str, Any]:
    return {
        "doc_type": extracted.doc_type,
        "description": extracted.description,
        "ext": extracted.ext,
        "issuer": extracted.issuer,
        "document_id": extracted.document_id,
        "document_date": extracted.document_date,
        "tasks": [
            {"title": t.title, "notes": t.notes, "due": t.due} for t in extracted.tasks
        ],
    }


@component
class FakeExtractFields:
    def __init__(self) -> None:
        self._extractor = FakeExtractor()

    @component.output_types(
        doc_type=str,
        description=str,
        ext=str,
        issuer=str | None,
        document_id=str | None,
        document_date=date | None,
        tasks=list,
    )
    def run(self, document: Document) -> dict[str, Any]:
        filename = None
        if document.meta:
            filename = document.meta.get("filename")
        extracted = self._extractor.extract(text=document.content or "", filename=filename)
        return _extracted_to_outputs(extracted)


@component
class DocumentToExtractVars:
    """Unpack Haystack Document into prompt template variables."""

    @component.output_types(text=str, filename=str)
    def run(self, document: Document) -> dict[str, Any]:
        filename = ""
        if document.meta and document.meta.get("filename") is not None:
            filename = str(document.meta.get("filename") or "")
        return {"text": document.content or "", "filename": filename}


def _reply_text(replies: list | str | ChatMessage) -> str:
    if isinstance(replies, str):
        return replies
    if isinstance(replies, ChatMessage):
        return replies.text or ""
    if not replies:
        return ""
    first = replies[0]
    if isinstance(first, ChatMessage):
        return first.text or ""
    return str(first)


@component
class ParseLlmJson:
    """Parse OpenAIChatGenerator replies into the same flat fields as FakeExtractFields."""

    @component.output_types(
        doc_type=str,
        description=str,
        ext=str,
        issuer=str | None,
        document_id=str | None,
        document_date=date | None,
        tasks=list,
    )
    def run(
        self,
        replies: list | str | ChatMessage,
        filename: str | None = None,
    ) -> dict[str, Any]:
        raw = _reply_text(replies).strip()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("ParseLlmJson expected a JSON object from the model")
        fname = filename or None
        if fname == "":
            fname = None
        extracted = _parse_llm_payload(payload, filename=fname)
        return _extracted_to_outputs(extracted)


@component
class DriveUpload:
    def __init__(self, drive: DriveClient) -> None:
        self._drive = drive

    @component.output_types(
        drive_path=str,
        drive_url=str,
        file_bytes=bytes | None,
        tasks=list,
        doc_type=str,
    )
    def run(
        self,
        document: Document,
        file_bytes: bytes | None = None,
        doc_type: str = "other",
        description: str = "document",
        ext: str = "txt",
        issuer: str | None = None,
        document_id: str | None = None,
        document_date: date | None = None,
        tasks: list | None = None,
    ) -> dict[str, Any]:
        relative_path = build_drive_relative_path(
            doc_type,
            description,
            ext,
            issuer=issuer,
            document_id=document_id,
            document_date=document_date,
        )
        data = file_bytes if file_bytes is not None else (document.content or "").encode("utf-8")
        mime_type = "application/octet-stream"
        if document.meta:
            mime_type = document.meta.get("mime_type") or mime_type
        uploaded = self._drive.upload(
            relative_path=relative_path,
            data=data,
            mime_type=mime_type,
        )
        return {
            "drive_path": uploaded.path,
            "drive_url": uploaded.url,
            "file_bytes": file_bytes,
            "tasks": tasks or [],
            "doc_type": doc_type,
        }


@component
class CreateTasks:
    def __init__(self, tasks_client: TasksClient) -> None:
        self._tasks_client = tasks_client

    @component.output_types(tasks_created=list)
    def run(self, tasks: list | None = None) -> dict[str, Any]:
        items = [
            TaskItem(
                title=t["title"],
                notes=t.get("notes"),
                due=t.get("due"),
            )
            for t in (tasks or [])
        ]
        created = self._tasks_client.create_many(items) if items else []
        return {
            "tasks_created": [
                {
                    "title": t.title,
                    "notes": t.notes,
                    "due": t.due,
                    "task_id": t.task_id,
                }
                for t in created
            ]
        }


@component
class BuildConfirmation:
    @component.output_types(
        ok=bool,
        message=str,
        drive_path=str,
        drive_url=str,
        doc_type=str,
        tasks_created=list,
    )
    def run(
        self,
        drive_path: str,
        drive_url: str,
        doc_type: str,
        tasks_created: list | None = None,
    ) -> dict[str, Any]:
        created = tasks_created or []
        n = len(created)
        message = f"Saved to Drive at {drive_path}. Created {n} Google Task(s)."
        return {
            "ok": True,
            "message": message,
            "drive_path": drive_path,
            "drive_url": drive_url,
            "doc_type": doc_type,
            "tasks_created": created,
        }
