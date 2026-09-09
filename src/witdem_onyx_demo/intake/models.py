from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DocType = Literal["invoice", "bureaucracy", "other"]


@dataclass
class IntakeRequest:
    text: str = ""
    file_bytes: bytes | None = None
    filename: str | None = None
    mime_type: str | None = None
    chat_session_id: str | None = None
    source: str = "onyx"


@dataclass
class TaskItem:
    title: str
    notes: str | None = None
    due: str | None = None  # ISO date if known
    task_id: str | None = None


@dataclass
class IntakeResult:
    ok: bool
    doc_type: DocType
    drive_path: str | None
    drive_url: str | None
    tasks_created: list[TaskItem] = field(default_factory=list)
    message: str = ""
    error: str | None = None

    def as_tool_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "doc_type": self.doc_type,
            "drive_path": self.drive_path,
            "drive_url": self.drive_url,
            "tasks_created": [
                {"title": t.title, "task_id": t.task_id, "due": t.due, "notes": t.notes}
                for t in self.tasks_created
            ],
            "message": self.message,
            "error": self.error,
        }
