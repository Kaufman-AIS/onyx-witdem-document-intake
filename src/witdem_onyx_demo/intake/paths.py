from __future__ import annotations

import re
from datetime import date

_FOLDER = {"invoice": "Invoices", "bureaucracy": "Documents", "other": "Other"}


def slugify(text: str, *, max_len: int = 60) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s or "document")[:max_len]


def slugify_name(text: str, *, max_len: int = 60) -> str:
    """Title-Case hyphenated label for Drive filenames (e.g. Google-Workspace)."""
    parts = re.findall(r"[A-Za-z0-9]+", text or "")
    if not parts:
        return "Unknown"
    label = "-".join(p[:1].upper() + p[1:].lower() if len(p) > 1 else p.upper() for p in parts)
    return label[:max_len]


def _sanitize_id(document_id: str, *, max_len: int = 80) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "", (document_id or "").strip())
    return (s or "unknown")[:max_len]


def build_drive_relative_path(
    doc_type: str,
    description: str = "document",
    ext: str = "txt",
    *,
    issuer: str | None = None,
    document_id: str | None = None,
    document_date: date | None = None,
    today: date | None = None,
) -> str:
    """Build Type/YYYY/YYYY-MM-DD-Issuer-… filename (no month folder)."""
    when = document_date or today or date.today()
    folder = _FOLDER[doc_type]
    year = when.strftime("%Y")
    day = when.strftime("%Y-%m-%d")
    ext = ext.lstrip(".") or "txt"
    issuer_part = slugify_name(issuer or "Unknown")

    if doc_type == "invoice":
        tail = _sanitize_id(document_id) if document_id else slugify_name(description)
        name = f"{day}-{issuer_part}-invoice-{tail}.{ext}"
    else:
        name = f"{day}-{issuer_part}-{slugify_name(description)}.{ext}"
    return f"{folder}/{year}/{name}"
