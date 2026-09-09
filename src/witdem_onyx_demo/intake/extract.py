from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx

from witdem_onyx_demo.intake.models import DocType, TaskItem
from witdem_onyx_demo.intake.paths import slugify


@dataclass
class ExtractedDoc:
    doc_type: DocType
    description: str
    tasks: list[TaskItem]
    ext: str
    issuer: str | None = None
    document_id: str | None = None
    document_date: date | None = None


class Extractor(Protocol):
    def extract(self, *, text: str, filename: str | None = None) -> ExtractedDoc: ...


_INVOICE_KW = ("rechnung", "invoice")
_BUREAUCRACY_KW = ("finanzamt", "behörde", "behorde", "frist")

_DUE_PATTERNS = [
    re.compile(r"zahlbar\s+bis\s+(\d{2}\.\d{2}\.\d{4})", re.I),
    re.compile(r"due\s+(?:date[:\s]+)?(\d{4}-\d{2}-\d{2})", re.I),
    re.compile(r"due\s+(\d{2}\.\d{2}\.\d{4})", re.I),
    re.compile(r"frist\s+(\d{2}\.\d{2}\.\d{4})", re.I),
]

_DOC_DATE_PATTERNS = [
    re.compile(r"rechnungsdatum\s*[:\s]+(\d{2}\.\d{2}\.\d{4})", re.I),
    re.compile(r"invoice\s+date\s*[:\s]+(\d{4}-\d{2}-\d{2})", re.I),
    re.compile(r"invoice\s+date\s*[:\s]+([A-Za-z]+\s+\d{1,2},\s*\d{4})", re.I),
    re.compile(r"rechnungsdatum\s*[:\s]+(\d{4}-\d{2}-\d{2})", re.I),
]

_ISSUER_PATTERNS = [
    re.compile(r"rechnung\s+von\s+([^\n,]+)", re.I),
    re.compile(r"provided\s+by\s*:\s*([^\n]+)", re.I),
    re.compile(r"schreiben\s+vom\s+([^\n,]+)", re.I),
]

_DOC_ID_PATTERNS = [
    re.compile(r"rechnungsnummer\s*[:\s#]*([A-Za-z0-9._-]+)", re.I),
    re.compile(r"invoice\s*#\s*[:\s]*([A-Za-z0-9._-]+)", re.I),
    re.compile(r"\bnr\.?\s*([A-Za-z0-9._-]+)", re.I),
]

_LLM_SYSTEM = """You extract structured fields from an incoming document for filing.
Return ONLY a JSON object with keys:
- doc_type: one of "invoice", "bureaucracy", "other"
- description: short slug-friendly label (ascii, underscores ok), max 40 chars
- issuer: vendor / Rechnungssteller / Absender as plain text (null if unknown)
- document_id: invoice or reference number as plain text (null if unknown)
- document_date: document/invoice date as YYYY-MM-DD (not payment due date; null if unknown)
- tasks: array of {title, notes?, due?} where due is YYYY-MM-DD if known
- ext: file extension without dot (default "txt")
"""


def _ext_from_filename(filename: str | None) -> str:
    if not filename or "." not in filename:
        return "txt"
    return filename.rsplit(".", 1)[-1].lower()


def _classify_doc_type(text: str, filename: str | None) -> DocType:
    hay = f"{text} {filename or ''}".lower()
    if any(kw in hay for kw in _INVOICE_KW):
        return "invoice"
    if any(kw in hay for kw in _BUREAUCRACY_KW):
        return "bureaucracy"
    return "other"


def _parse_de_or_iso_date(raw: str) -> date | None:
    raw = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        y, m, d = raw.split("-")
        return date(int(y), int(m), int(d))
    dm = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if dm:
        return date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
    return None


def _parse_due_date(text: str) -> str | None:
    for pat in _DUE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_de_or_iso_date(m.group(1))
        if parsed:
            return parsed.isoformat()
    return None


def _parse_document_date(text: str) -> date | None:
    for pat in _DOC_DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_de_or_iso_date(m.group(1))
        if parsed:
            return parsed
    return None


def _parse_issuer(text: str) -> str | None:
    for pat in _ISSUER_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        value = m.group(1).strip(" \t.,;")
        value = re.split(r"[\n|]", value)[0].strip()
        # Stop before common trailing fields on the same line.
        value = re.split(
            r"\s+(?:Nr\.?|Rechnungs(?:nummer|datum)|Invoice|zahlbar|due)\b",
            value,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        if value:
            return value[:80]
    return None


def _parse_document_id(text: str) -> str | None:
    for pat in _DOC_ID_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        value = m.group(1).strip()
        if value:
            return value[:80]
    return None


def _make_description(text: str, filename: str | None) -> str:
    if filename:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        if stem.strip():
            return slugify(stem, max_len=40)
    words = text.split()[:6]
    return slugify(" ".join(words), max_len=40)


def _task_title(doc_type: DocType, description: str) -> str:
    label = description.replace("_", " ")
    if doc_type == "invoice":
        return f"Pay {label}"
    if doc_type == "bureaucracy":
        return f"Respond to {label}"
    return f"Follow up: {label}"


class FakeExtractor:
    def extract(self, *, text: str, filename: str | None = None) -> ExtractedDoc:
        doc_type = _classify_doc_type(text, filename)
        description = _make_description(text, filename)
        ext = _ext_from_filename(filename)
        issuer = _parse_issuer(text)
        document_id = _parse_document_id(text)
        document_date = _parse_document_date(text)
        tasks: list[TaskItem] = []
        due = _parse_due_date(text)
        if due:
            tasks.append(TaskItem(title=_task_title(doc_type, description), due=due))
        return ExtractedDoc(
            doc_type=doc_type,
            description=description,
            tasks=tasks,
            ext=ext,
            issuer=issuer,
            document_id=document_id,
            document_date=document_date,
        )


def _parse_llm_payload(payload: dict[str, Any], *, filename: str | None) -> ExtractedDoc:
    doc_type_raw = str(payload.get("doc_type") or "other").lower()
    doc_type: DocType = (
        doc_type_raw if doc_type_raw in {"invoice", "bureaucracy", "other"} else "other"  # type: ignore[assignment]
    )
    description = slugify(str(payload.get("description") or "document"), max_len=40)
    ext = str(payload.get("ext") or _ext_from_filename(filename)).lstrip(".").lower() or "txt"
    issuer_raw = payload.get("issuer")
    issuer = str(issuer_raw).strip() if issuer_raw else None
    id_raw = payload.get("document_id")
    document_id = str(id_raw).strip() if id_raw else None
    date_raw = payload.get("document_date")
    document_date = _parse_de_or_iso_date(str(date_raw)) if date_raw else None
    tasks: list[TaskItem] = []
    for raw in payload.get("tasks") or []:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        due = raw.get("due")
        tasks.append(
            TaskItem(
                title=title,
                notes=(str(raw["notes"]) if raw.get("notes") is not None else None),
                due=(str(due) if due else None),
            )
        )
    return ExtractedDoc(
        doc_type=doc_type,
        description=description,
        tasks=tasks,
        ext=ext,
        issuer=issuer or None,
        document_id=document_id or None,
        document_date=document_date,
    )


class LlmExtractor:
    """OpenAI JSON extract via Chat Completions. Requires OPENAI_API_KEY."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def extract(self, *, text: str, filename: str | None = None) -> ExtractedDoc:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LlmExtractor")

        user_content = f"filename: {filename or ''}\n\n---\n{text[:12000]}"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError("LlmExtractor expected a JSON object from the model")
        return _parse_llm_payload(payload, filename=filename)
