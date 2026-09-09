from __future__ import annotations

from typing import Any, Protocol

from google.oauth2 import service_account
from googleapiclient.discovery import build

from witdem_onyx_demo.intake.models import TaskItem

# Service account needs Tasks API enabled; user OAuth is preferred for personal lists.
TASKS_SCOPES = ("https://www.googleapis.com/auth/tasks",)


class TasksClient(Protocol):
    def create_many(self, items: list[TaskItem]) -> list[TaskItem]: ...


class InMemoryTasks:
    def __init__(self) -> None:
        self.items: list[TaskItem] = []
        self._n = 0

    def create_many(self, items: list[TaskItem]) -> list[TaskItem]:
        out: list[TaskItem] = []
        for item in items:
            self._n += 1
            created = TaskItem(
                title=item.title,
                notes=item.notes,
                due=item.due,
                task_id=f"task-{self._n}",
            )
            self.items.append(created)
            out.append(created)
        return out


def _due_to_rfc3339(due: str) -> str:
    """Map ISO date (YYYY-MM-DD) or already-RFC3339 to Tasks API due format."""
    raw = due.strip()
    if "T" in raw:
        return raw if raw.endswith("Z") or "+" in raw[10:] else f"{raw}Z"
    return f"{raw}T00:00:00.000Z"


class GoogleTasksClient:
    """Create tasks in GOOGLE_TASKS_LIST_ID via the Google Tasks API."""

    def __init__(
        self,
        *,
        list_id: str,
        credentials: Any | None = None,
        credentials_path: str | None = None,
    ) -> None:
        if not list_id:
            raise ValueError("GOOGLE_TASKS_LIST_ID is required for GoogleTasksClient")
        if credentials is None:
            if not credentials_path:
                raise ValueError(
                    "GoogleTasksClient requires credentials= or credentials_path="
                )
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=list(TASKS_SCOPES)
            )
        self._list_id = list_id
        self._credentials = credentials
        self._service: Any = build(
            "tasks", "v1", credentials=credentials, cache_discovery=False
        )

    def create_many(self, items: list[TaskItem]) -> list[TaskItem]:
        out: list[TaskItem] = []
        for item in items:
            body: dict[str, Any] = {"title": item.title}
            if item.notes:
                body["notes"] = item.notes
            if item.due:
                body["due"] = _due_to_rfc3339(item.due)
            created = (
                self._service.tasks()
                .insert(tasklist=self._list_id, body=body)
                .execute()
            )
            out.append(
                TaskItem(
                    title=item.title,
                    notes=item.notes,
                    due=item.due,
                    task_id=str(created["id"]),
                )
            )
        return out
