"""HTTP tool server tests for run_intake."""

from __future__ import annotations

import base64

from starlette.testclient import TestClient

from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.extract import FakeExtractor
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks
from witdem_onyx_demo.intake.tool_server import create_app


def test_post_run_intake_json() -> None:
    app = create_app(drive=InMemoryDrive(), tasks=InMemoryTasks(), extractor=FakeExtractor())
    client = TestClient(app)
    r = client.post("/tools/run_intake", json={"text": "Invoice Acme 1", "filename": "a.txt"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["drive_path"]


def test_health() -> None:
    app = create_app(drive=InMemoryDrive(), tasks=InMemoryTasks(), extractor=FakeExtractor())
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_post_run_intake_file_base64() -> None:
    drive = InMemoryDrive()
    app = create_app(drive=drive, tasks=InMemoryTasks(), extractor=FakeExtractor())
    client = TestClient(app)
    payload = b"%PDF-1.4 fake"
    r = client.post(
        "/tools/run_intake",
        json={
            "text": "Invoice Acme 1",
            "filename": "a.pdf",
            "file_base64": base64.b64encode(payload).decode("ascii"),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["drive_path"]
    assert list(drive.files.values()) == [payload]
