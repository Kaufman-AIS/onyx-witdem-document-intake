from __future__ import annotations

from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.extract import FakeExtractor
from witdem_onyx_demo.intake.models import IntakeRequest
from witdem_onyx_demo.intake.pipeline import run_intake
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks


class _BoomDrive(InMemoryDrive):
    def upload(self, *, relative_path: str, data: bytes, mime_type: str):
        raise RuntimeError("upload failed")


def test_run_intake_stores_pdf_and_returns_confirmation():
    drive = InMemoryDrive()
    tasks = InMemoryTasks()
    result = run_intake(
        IntakeRequest(
            text="Invoice Acme 1042 due 2026-09-30",
            file_bytes=b"%PDF",
            filename="acme.pdf",
            mime_type="application/pdf",
        ),
        drive=drive,
        tasks=tasks,
        extractor=FakeExtractor(),
    )
    assert result.ok is True
    assert result.drive_path is not None
    assert result.drive_path.startswith("Invoices/")
    assert result.drive_path.count("/") == 2
    assert "2026-" in result.drive_path.split("/")[-1]  # dated filename
    assert result.message
    assert drive.files  # stored
    assert result.drive_url


def test_run_intake_stores_pasted_text_as_txt():
    drive = InMemoryDrive()
    tasks = InMemoryTasks()
    result = run_intake(
        IntakeRequest(text="Invoice Acme 1042 due 2026-09-30"),
        drive=drive,
        tasks=tasks,
        extractor=FakeExtractor(),
    )
    assert result.ok is True
    assert result.drive_path is not None
    assert result.drive_path.endswith(".txt")
    assert drive.files[result.drive_path] == b"Invoice Acme 1042 due 2026-09-30"


def test_run_intake_returns_ok_false_on_exception():
    result = run_intake(
        IntakeRequest(
            text="Invoice Acme 1042 due 2026-09-30",
            file_bytes=b"%PDF",
            filename="acme.pdf",
            mime_type="application/pdf",
        ),
        drive=_BoomDrive(),
        tasks=InMemoryTasks(),
        extractor=FakeExtractor(),
    )
    assert result.ok is False
    assert result.drive_path is None
    assert result.drive_url is None
    assert result.error == "upload failed"
    assert result.message.startswith("Intake failed:")
    assert result.doc_type == "other"
