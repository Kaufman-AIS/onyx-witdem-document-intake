from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.models import TaskItem
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks


def test_drive_stores_bytes_at_relative_path():
    drive = InMemoryDrive()
    meta = drive.upload(
        relative_path="Invoices/2026/2026-09-07-Acme-invoice-1042.pdf",
        data=b"%PDF",
        mime_type="application/pdf",
    )
    assert meta.path == "Invoices/2026/2026-09-07-Acme-invoice-1042.pdf"
    assert meta.url.startswith("memory://")
    assert drive.files[meta.path] == b"%PDF"


def test_tasks_create_returns_ids():
    tasks = InMemoryTasks()
    created = tasks.create_many([TaskItem(title="Pay invoice", due="2026-09-30")])
    assert created[0].task_id == "task-1"
    assert tasks.items[0].title == "Pay invoice"
