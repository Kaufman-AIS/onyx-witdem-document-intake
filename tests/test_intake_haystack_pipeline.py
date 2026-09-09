from datetime import date

from haystack import Document

from witdem_onyx_demo.intake.drive import InMemoryDrive
from witdem_onyx_demo.intake.haystack_components import (
    BuildConfirmation,
    CreateTasks,
    DriveUpload,
    FakeExtractFields,
    ReceiveDocument,
)
from witdem_onyx_demo.intake.tasks_client import InMemoryTasks


def test_fake_extract_fields_detects_invoice():
    comp = FakeExtractFields()
    out = comp.run(
        document=Document(
            content="Rechnung von Acme GmbH Nr 1042 Rechnungsdatum 07.09.2026 zahlbar bis 30.09.2026",
            meta={"filename": "scan.pdf"},
        )
    )
    assert out["doc_type"] == "invoice"
    assert out["issuer"] == "Acme GmbH"
    assert out["document_id"] == "1042"
    assert out["ext"] == "pdf"
    assert out["tasks"]


def test_receive_document_builds_haystack_document():
    out = ReceiveDocument().run(
        text="hello",
        filename="a.pdf",
        mime_type="application/pdf",
        has_file_bytes=True,
    )
    doc = out["document"]
    assert doc.content == "hello"
    assert doc.meta["filename"] == "a.pdf"
    assert doc.meta["has_file_bytes"] is True


def test_drive_upload_uses_year_issuer_path():
    drive = InMemoryDrive()
    comp = DriveUpload(drive=drive)
    out = comp.run(
        document=Document(content="x", meta={"filename": "a.pdf", "mime_type": "application/pdf"}),
        file_bytes=b"%PDF-1.4",
        doc_type="invoice",
        description="acme",
        ext="pdf",
        issuer="Google Workspace",
        document_id="23984u2938429834u283",
        document_date=date(2026, 12, 31),
        tasks=[],
    )
    assert out["drive_path"] == (
        "Invoices/2026/2026-12-31-Google-Workspace-invoice-23984u2938429834u283.pdf"
    )
    assert drive.files[out["drive_path"]].startswith(b"%PDF")


def test_create_tasks_and_confirmation():
    client = InMemoryTasks()
    created = CreateTasks(tasks_client=client).run(
        tasks=[{"title": "Pay", "notes": None, "due": "2026-09-30"}]
    )
    assert len(created["tasks_created"]) == 1
    assert created["tasks_created"][0]["task_id"]
    conf = BuildConfirmation().run(
        drive_path="Invoices/2026/x.pdf",
        drive_url="https://drive.example/x",
        doc_type="invoice",
        tasks_created=created["tasks_created"],
    )
    assert conf["ok"] is True
    assert "Saved to Drive" in conf["message"]
    assert "1 Google Task" in conf["message"]


def test_run_intake_via_haystack_pipeline():
    from witdem_onyx_demo.intake.models import IntakeRequest
    from witdem_onyx_demo.intake.pipeline import run_intake

    class _BoomExtractor:
        def extract(self, **kwargs):
            raise RuntimeError("extractor should not be called; Haystack owns extract")

    drive = InMemoryDrive()
    result = run_intake(
        IntakeRequest(
            text="Invoice Acme 1042 due 2026-09-30",
            file_bytes=b"%PDF",
            filename="acme.pdf",
            mime_type="application/pdf",
        ),
        drive=drive,
        tasks=InMemoryTasks(),
        extractor=_BoomExtractor(),  # ignored once Haystack owns extract; keep sig for compat
    )
    assert result.ok is True
    assert result.drive_path.startswith("Invoices/")
    assert result.drive_path.count("/") == 2


def test_build_intake_pipeline_is_haystack_pipeline():
    from haystack import Pipeline

    from witdem_onyx_demo.intake.haystack_pipeline import build_intake_pipeline

    pipe = build_intake_pipeline(drive=InMemoryDrive(), tasks=InMemoryTasks())
    assert isinstance(pipe, Pipeline)
    assert set(pipe.graph.nodes) >= {"receive", "extract", "drive", "create_tasks", "confirm"}


def test_parse_llm_json_from_chat_message():
    from datetime import date

    from haystack.dataclasses import ChatMessage

    from witdem_onyx_demo.intake.haystack_components import ParseLlmJson

    payload = (
        '{"doc_type":"invoice","description":"Acme_invoice","issuer":"Acme GmbH",'
        '"document_id":"1042","document_date":"2026-09-07","ext":"pdf",'
        '"tasks":[{"title":"Pay Acme","due":"2026-09-30"}]}'
    )
    out = ParseLlmJson().run(
        replies=[ChatMessage.from_assistant(payload)],
        filename="scan.pdf",
    )
    assert out["doc_type"] == "invoice"
    assert out["description"] == "acme_invoice"
    assert out["issuer"] == "Acme GmbH"
    assert out["document_id"] == "1042"
    assert out["document_date"] == date(2026, 9, 7)
    assert out["ext"] == "pdf"
    assert out["tasks"][0]["title"] == "Pay Acme"
    assert out["tasks"][0]["due"] == "2026-09-30"


def test_parse_llm_json_from_string_payload():
    from witdem_onyx_demo.intake.haystack_components import ParseLlmJson

    out = ParseLlmJson().run(
        replies='{"doc_type":"bureaucracy","description":"tax_letter","ext":"txt","tasks":[]}',
        filename=None,
    )
    assert out["doc_type"] == "bureaucracy"
    assert out["description"] == "tax_letter"
    assert out["tasks"] == []


def test_build_intake_pipeline_use_llm_false_uses_fake(monkeypatch):
    from witdem_onyx_demo.intake.haystack_components import FakeExtractFields
    from witdem_onyx_demo.intake.haystack_pipeline import build_intake_pipeline

    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-matter")
    pipe = build_intake_pipeline(
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        use_llm=False,
    )
    assert isinstance(pipe.get_component("extract"), FakeExtractFields)


def test_build_intake_pipeline_use_llm_true_with_key_uses_parse(monkeypatch):
    from witdem_onyx_demo.intake.haystack_components import ParseLlmJson
    from witdem_onyx_demo.intake.haystack_pipeline import build_intake_pipeline

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    pipe = build_intake_pipeline(
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        use_llm=True,
    )
    assert isinstance(pipe.get_component("extract"), ParseLlmJson)
    assert "llm" in pipe.graph.nodes
    assert "prompt" in pipe.graph.nodes


def test_build_intake_pipeline_use_llm_true_without_key_uses_fake(monkeypatch):
    from witdem_onyx_demo.intake.haystack_components import FakeExtractFields
    from witdem_onyx_demo.intake.haystack_pipeline import build_intake_pipeline

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pipe = build_intake_pipeline(
        drive=InMemoryDrive(),
        tasks=InMemoryTasks(),
        use_llm=True,
    )
    assert isinstance(pipe.get_component("extract"), FakeExtractFields)
