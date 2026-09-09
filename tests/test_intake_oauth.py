"""OAuth user credentials for Google Tasks (company accounts)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from witdem_onyx_demo.intake.drive import GoogleDriveClient
from witdem_onyx_demo.intake.models import TaskItem
from witdem_onyx_demo.intake.settings import IntakeSettings
from witdem_onyx_demo.intake.tasks_client import GoogleTasksClient
from witdem_onyx_demo.intake.tool_server import _default_clients


def _write_sa_json(path: Path) -> Path:
    import json

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


def test_oauth_user_credentials_builds_from_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from witdem_onyx_demo.intake import oauth as oauth_mod

    fake_creds = MagicMock(name="oauth-creds")
    captured: dict[str, object] = {}

    def _creds(**kwargs: object) -> MagicMock:
        captured.update(kwargs)
        return fake_creds

    monkeypatch.setattr(oauth_mod, "Credentials", _creds)

    got = oauth_mod.user_credentials_from_refresh_token(
        client_id="cid",
        client_secret="sec",
        refresh_token="rtok",
        scopes=["https://www.googleapis.com/auth/tasks"],
    )

    assert got is fake_creds
    assert captured["client_id"] == "cid"
    assert captured["client_secret"] == "sec"
    assert captured["refresh_token"] == "rtok"
    assert captured["token"] is None
    assert "tasks" in str(captured["scopes"][0])


def test_google_tasks_client_accepts_oauth_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted: list[dict[str, object]] = []

    class _Tasks:
        def insert(self, **kwargs: object) -> MagicMock:
            inserted.append(kwargs)
            resp = MagicMock()
            resp.execute.return_value = {"id": "oauth-task-1"}
            return resp

    service = MagicMock()
    service.tasks.return_value = _Tasks()
    monkeypatch.setattr("witdem_onyx_demo.intake.tasks_client.build", lambda *a, **k: service)

    client = GoogleTasksClient(list_id="list-1", credentials=MagicMock(name="user-oauth"))
    out = client.create_many([TaskItem(title="Pay via oauth", due="2026-10-01")])

    assert out[0].task_id == "oauth-task-1"
    assert inserted[0]["tasklist"] == "list-1"


def test_default_clients_prefer_oauth_for_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sa = _write_sa_json(tmp_path / "sa.json")
    oauth_creds = MagicMock(name="oauth-user")

    monkeypatch.setattr(
        "witdem_onyx_demo.intake.drive.service_account.Credentials.from_service_account_file",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.drive.build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        "witdem_onyx_demo.intake.tool_server.user_credentials_from_refresh_token",
        lambda **k: oauth_creds,
    )
    monkeypatch.setattr("witdem_onyx_demo.intake.tasks_client.build", lambda *a, **k: MagicMock())

    settings = IntakeSettings(
        google_application_credentials=str(sa),
        google_drive_root_folder_id="root",
        google_tasks_list_id="list",
        intake_tool_url="http://127.0.0.1:8091/tools/run_intake",
        intake_use_memory=False,
        openai_api_key=None,
        google_oauth_client_id="cid",
        google_oauth_client_secret="sec",
        google_oauth_refresh_token="rtok",
    )
    drive, tasks, _ = _default_clients(settings)
    assert isinstance(drive, GoogleDriveClient)
    assert isinstance(tasks, GoogleTasksClient)
    assert tasks._credentials is oauth_creds  # type: ignore[attr-defined]
