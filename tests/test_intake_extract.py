import json
import os
from datetime import date
from unittest.mock import MagicMock

import pytest

from witdem_onyx_demo.intake.extract import ExtractedDoc, FakeExtractor, LlmExtractor


def test_fake_extractor_detects_invoice_keyword():
    ex = FakeExtractor()
    got = ex.extract(
        text="Rechnung von Acme GmbH Nr 1042 Rechnungsdatum 07.09.2026 zahlbar bis 30.09.2026",
        filename="scan.pdf",
    )
    assert got.doc_type == "invoice"
    assert got.description
    assert isinstance(got, ExtractedDoc)
    assert got.ext == "pdf"
    assert got.issuer == "Acme GmbH"
    assert got.document_id == "1042"
    assert got.document_date == date(2026, 9, 7)
    assert len(got.tasks) == 1
    assert got.tasks[0].due == "2026-09-30"
    assert "Pay" in got.tasks[0].title


def test_fake_extractor_defaults_other():
    got = FakeExtractor().extract(text="hello world", filename="notes.xlsx")
    assert got.doc_type == "other"
    assert got.ext == "xlsx"


def test_fake_extractor_detects_bureaucracy_keyword():
    got = FakeExtractor().extract(text="Schreiben vom Finanzamt zur Frist 15.10.2026", filename="letter.pdf")
    assert got.doc_type == "bureaucracy"
    assert got.ext == "pdf"
    assert len(got.tasks) == 1
    assert got.tasks[0].due == "2026-10-15"
    assert "Respond to" in got.tasks[0].title


def test_llm_extractor_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ex = LlmExtractor()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ex.extract(text="hello", filename="doc.txt")


def test_llm_extractor_parses_openai_json(monkeypatch):
    payload = {
        "doc_type": "invoice",
        "description": "acme_1042",
        "issuer": "Google Workspace",
        "document_id": "23984u2938429834u283",
        "document_date": "2026-12-31",
        "ext": "pdf",
        "tasks": [{"title": "Pay acme 1042", "due": "2026-09-30"}],
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload)}}],
    }
    monkeypatch.setattr("witdem_onyx_demo.intake.extract.httpx.post", lambda *a, **k: resp)

    got = LlmExtractor(api_key="sk-test").extract(text="Rechnung Acme", filename="a.pdf")
    assert got.doc_type == "invoice"
    assert got.description == "acme_1042"
    assert got.issuer == "Google Workspace"
    assert got.document_id == "23984u2938429834u283"
    assert got.document_date == date(2026, 12, 31)
    assert got.ext == "pdf"
    assert got.tasks[0].title == "Pay acme 1042"
    assert got.tasks[0].due == "2026-09-30"
