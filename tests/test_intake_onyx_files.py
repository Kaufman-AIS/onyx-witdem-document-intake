"""Onyx chat-file download for real PDF bytes in intake."""

from __future__ import annotations

import base64
import json
import urllib.error
from typing import Any

import pytest
from starlette.testclient import TestClient

from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.extract import FakeExtractor
from witdem_onyx_demo.intake.onyx_files import OnyxFileClient, OnyxFileError
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks
from witdem_onyx_demo.intake.tool_server import create_app


class _FakeResponse:
    def __init__(self, *, status: int, data: bytes, content_type: str) -> None:
        self.status = status
        self._data = data
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_onyx_file_client_downloads_pdf_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_urlopen(req: Any, timeout: float = 0) -> _FakeResponse:  # noqa: ARG001
        calls.append(req.full_url)
        assert req.get_header("Authorization") == "Bearer test-key"
        return _FakeResponse(status=200, data=b"%PDF-1.4 real", content_type="application/pdf")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OnyxFileClient(api_base_url="http://onyx.example/api", api_key="test-key")
    data, content_type = client.download("file-123")
    assert data == b"%PDF-1.4 real"
    assert content_type == "application/pdf"
    assert calls == ["http://onyx.example/api/chat/file/file-123"]


def test_onyx_file_client_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: Any, timeout: float = 0) -> _FakeResponse:  # noqa: ARG001
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OnyxFileClient(api_base_url="http://onyx.example/api", api_key="k")
    with pytest.raises(OnyxFileError, match="404"):
        client.download("missing")


def test_run_intake_fetches_onyx_file_id_when_no_base64() -> None:
    drive = InMemoryDrive()
    pdf = b"%PDF-1.4 from-onyx"

    class StubFiles:
        def download(self, file_id: str) -> tuple[bytes, str | None]:
            assert file_id == "a64fc167-7613-46b6-a255-9fed40cb691d"
            return pdf, "application/pdf"

        def resolve_file_id_by_name(self, filename: str) -> str | None:
            raise AssertionError("should not resolve when file_id present")

    app = create_app(
        drive=drive,
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
        onyx_files=StubFiles(),
    )
    client = TestClient(app)
    r = client.post(
        "/tools/run_intake",
        json={
            "text": "Invoice text for classification",
            "filename": "REDE25121205.pdf",
            "mime_type": "application/pdf",
            "file_id": "a64fc167-7613-46b6-a255-9fed40cb691d",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert list(drive.files.values()) == [pdf]


def test_run_intake_prefers_file_base64_over_file_id() -> None:
    drive = InMemoryDrive()
    inline = b"%PDF-1.4 inline"

    class StubFiles:
        def download(self, file_id: str) -> tuple[bytes, str | None]:
            raise AssertionError("should not download when base64 present")

        def resolve_file_id_by_name(self, filename: str) -> str | None:
            raise AssertionError("should not resolve when base64 present")

    app = create_app(
        drive=drive,
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
        onyx_files=StubFiles(),
    )
    r = TestClient(app).post(
        "/tools/run_intake",
        json={
            "text": "Invoice",
            "filename": "a.pdf",
            "file_base64": base64.b64encode(inline).decode("ascii"),
            "file_id": "should-ignore",
        },
    )
    assert r.status_code == 200
    assert list(drive.files.values()) == [inline]


def test_onyx_file_client_resolves_file_id_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        [
            {
                "id": "uf-old",
                "name": "other.pdf",
                "file_id": "file-old",
            },
            {
                "id": "uf-new",
                "name": "invoice-04566-38661219.pdf",
                "file_id": "55178939-c58c-4fa0-a115-1129460035cf",
            },
        ]
    ).encode("utf-8")

    def fake_urlopen(req: Any, timeout: float = 0) -> _FakeResponse:  # noqa: ARG001
        assert req.full_url.endswith("/user/files/recent")
        return _FakeResponse(status=200, data=payload, content_type="application/json")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OnyxFileClient(api_base_url="http://onyx.example/api", api_key="test-key")
    assert (
        client.resolve_file_id_by_name("invoice-04566-38661219.pdf")
        == "55178939-c58c-4fa0-a115-1129460035cf"
    )


def test_run_intake_resolves_filename_when_file_id_missing() -> None:
    drive = InMemoryDrive()
    pdf = b"%PDF-1.4 canva-invoice"

    class StubFiles:
        def download(self, file_id: str) -> tuple[bytes, str | None]:
            assert file_id == "55178939-c58c-4fa0-a115-1129460035cf"
            return pdf, "application/pdf"

        def resolve_file_id_by_name(self, filename: str) -> str | None:
            assert filename == "invoice-04566-38661219.pdf"
            return "55178939-c58c-4fa0-a115-1129460035cf"

    app = create_app(
        drive=drive,
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
        onyx_files=StubFiles(),
    )
    r = TestClient(app).post(
        "/tools/run_intake",
        json={
            "requestBody": {
                "text": "INVOICE total 12 EUR",
                "filename": "invoice-04566-38661219.pdf",
                "mime_type": "application/pdf",
            }
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert list(drive.files.values()) == [pdf]


def test_run_intake_rejects_pdf_without_binary_bytes() -> None:
    drive = InMemoryDrive()

    class StubFiles:
        def download(self, file_id: str) -> tuple[bytes, str | None]:
            raise AssertionError("no id")

        def resolve_file_id_by_name(self, filename: str) -> str | None:
            return None

    app = create_app(
        drive=drive,
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
        onyx_files=StubFiles(),
    )
    r = TestClient(app).post(
        "/tools/run_intake",
        json={
            "text": "INVOICE text only",
            "filename": "invoice.pdf",
            "mime_type": "application/pdf",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert drive.files == {}
