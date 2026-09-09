"""Unit tests for Google Drive/Tasks clients (mocked Google APIs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from witdem_onyx_demo.intake.drive import GoogleDriveClient
from witdem_onyx_demo.intake.extract import FakeExtractor, LlmExtractor
from witdem_onyx_demo.intake.models import TaskItem
from witdem_onyx_demo.intake.settings import IntakeSettings
from witdem_onyx_demo.intake.tasks_client import GoogleTasksClient
from witdem_onyx_demo.intake.tool_server import _default_clients


def _write_sa_json(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "demo",
                "private_key_id": "x",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n",
                "client_email": "sa@demo.iam.gserviceaccount.com",
                "client_id": "1",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_google_drive_upload_creates_folder_chain_and_returns_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds = _write_sa_json(tmp_path / "sa.json")
    folders: dict[tuple[str, str], str] = {}
    files_created: list[dict[str, Any]] = []

    class _Files:
        def list(self, **kwargs: Any) -> MagicMock:
            q = kwargs["q"]
            parent = kwargs["q"].split("' in parents")[0].split("'")[-1] if "in parents" in q else ""
            name = ""
            if "name = '" in q:
                name = q.split("name = '")[1].split("'")[0]
            resp = MagicMock()
            existing = folders.get((parent, name))
            resp.execute.return_value = {"files": [{"id": existing}] if existing else []}
            return resp

        def create(self, **kwargs: Any) -> MagicMock:
            body = kwargs["body"]
            mime = body.get("mimeType", "")
            parents = body.get("parents", [])
            parent = parents[0] if parents else ""
            name = body["name"]
            resp = MagicMock()
            if mime == "application/vnd.google-apps.folder":
                fid = f"folder-{len(folders)+1}"
                folders[(parent, name)] = fid
                resp.execute.return_value = {"id": fid}
            else:
                fid = f"file-{len(files_created)+1}"
                files_created.append({"id": fid, "body": body, "media": kwargs.get("media_body")})
                resp.execute.return_value = {
                    "id": fid,
                    "webViewLink": f"https://drive.google.com/file/d/{fid}/view",
                }
            return resp

    service = MagicMock()
    service.files.return_value = _Files()

    monkeypatch.setattr(
        "witdem_onyx_demo.intake.drive.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.drive.build", lambda *a, **k: service)

    client = GoogleDriveClient(credentials_path=str(creds), root_folder_id="root-1")
    obj = client.upload(
        relative_path="Invoices/2026/2026-09-07-Acme-invoice-1042.pdf",
        data=b"%PDF-1.4",
        mime_type="application/pdf",
    )

    assert obj.file_id == "file-1"
    assert obj.path == "Invoices/2026/2026-09-07-Acme-invoice-1042.pdf"
    assert "file-1" in obj.url
    assert ("root-1", "Invoices") in folders
    invoice_id = folders[("root-1", "Invoices")]
    assert (invoice_id, "2026") in folders


def test_google_tasks_create_many_maps_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds = _write_sa_json(tmp_path / "sa.json")
    inserted: list[dict[str, Any]] = []

    class _Tasks:
        def insert(self, **kwargs: Any) -> MagicMock:
            inserted.append(kwargs)
            resp = MagicMock()
            resp.execute.return_value = {"id": f"gt-{len(inserted)}"}
            return resp

    service = MagicMock()
    service.tasks.return_value = _Tasks()

    monkeypatch.setattr(
        "witdem_onyx_demo.intake.tasks_client.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.tasks_client.build", lambda *a, **k: service)

    client = GoogleTasksClient(credentials_path=str(creds), list_id="list-1")
    out = client.create_many(
        [
            TaskItem(title="Pay acme", due="2026-09-15", notes="invoice"),
            TaskItem(title="No due"),
        ]
    )

    assert [t.task_id for t in out] == ["gt-1", "gt-2"]
    assert inserted[0]["tasklist"] == "list-1"
    assert inserted[0]["body"]["title"] == "Pay acme"
    assert inserted[0]["body"]["due"] == "2026-09-15T00:00:00.000Z"
    assert "due" not in inserted[1]["body"]


def test_default_clients_use_google_when_creds_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds = _write_sa_json(tmp_path / "sa.json")
    monkeypatch.setattr(
        "witdem_onyx_demo.intake.drive.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.drive.build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        "witdem_onyx_demo.intake.tasks_client.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.tasks_client.build", lambda *a, **k: MagicMock())

    settings = IntakeSettings(
        google_application_credentials=str(creds),
        google_drive_root_folder_id="root",
        google_tasks_list_id="list",
        intake_tool_url="http://127.0.0.1:8091/tools/run_intake",
        intake_use_memory=False,
        openai_api_key=None,
    )
    drive, tasks, extractor = _default_clients(settings)
    assert isinstance(drive, GoogleDriveClient)
    assert isinstance(tasks, GoogleTasksClient)
    assert isinstance(extractor, FakeExtractor)


def test_default_clients_prefer_memory_when_flag_set(tmp_path: Path) -> None:
    creds = _write_sa_json(tmp_path / "sa.json")
    settings = IntakeSettings(
        google_application_credentials=str(creds),
        google_drive_root_folder_id="root",
        google_tasks_list_id="list",
        intake_tool_url="http://127.0.0.1:8091/tools/run_intake",
        intake_use_memory=True,
        openai_api_key="sk-test",
    )
    drive, tasks, extractor = _default_clients(settings)
    from witdem_onyx_demo.intake.drive import InMemoryDrive
    from witdem_onyx_demo.intake.tasks_client import InMemoryTasks

    assert isinstance(drive, InMemoryDrive)
    assert isinstance(tasks, InMemoryTasks)
    assert isinstance(extractor, FakeExtractor)


def test_default_clients_use_llm_extractor_when_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds = _write_sa_json(tmp_path / "sa.json")
    monkeypatch.setattr(
        "witdem_onyx_demo.intake.drive.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.drive.build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        "witdem_onyx_demo.intake.tasks_client.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.tasks_client.build", lambda *a, **k: MagicMock())

    settings = IntakeSettings(
        google_application_credentials=str(creds),
        google_drive_root_folder_id="root",
        google_tasks_list_id="list",
        intake_tool_url="http://127.0.0.1:8091/tools/run_intake",
        intake_use_memory=False,
        openai_api_key="sk-test",
    )
    _, _, extractor = _default_clients(settings)
    assert isinstance(extractor, LlmExtractor)
