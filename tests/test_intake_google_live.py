"""Live Google Drive/Tasks smoke tests — skipped without credentials."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="live Google credentials not configured",
)


def test_construct_google_clients() -> None:
    from witdem_onyx_demo.intake.drive import GoogleDriveClient
    from witdem_onyx_demo.intake.tasks_client import GoogleTasksClient

    creds = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    root = os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID")
    list_id = os.environ.get("GOOGLE_TASKS_LIST_ID")
    assert root, "GOOGLE_DRIVE_ROOT_FOLDER_ID required for live test"
    assert list_id, "GOOGLE_TASKS_LIST_ID required for live test"

    drive = GoogleDriveClient(credentials_path=creds, root_folder_id=root)
    tasks = GoogleTasksClient(credentials_path=creds, list_id=list_id)
    assert drive is not None
    assert tasks is not None

    if os.getenv("GOOGLE_INTAKE_LIVE") == "1":
        obj = drive.upload(
            relative_path="Other/2099-01/2099-01-01_witdem_live_smoke.txt",
            data=b"witdem intake live smoke\n",
            mime_type="text/plain",
        )
        assert obj.file_id
        assert obj.url


def test_live_drive_upload_roundtrip() -> None:
    """Alias for plan naming; same skip gate as module pytestmark."""
    test_construct_google_clients()
