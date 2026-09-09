from datetime import date

from witdem_onyx_demo.intake.paths import build_drive_relative_path, slugify, slugify_name


def test_slugify_strips_and_lowers():
    assert slugify("Acme Invoice #1042!") == "acme_invoice_1042"


def test_slugify_name_title_hyphenates():
    assert slugify_name("Google Workspace") == "Google-Workspace"
    assert slugify_name("corporate benefits Germany GmbH") == "Corporate-Benefits-Germany-Gmbh"


def test_invoice_path_year_folder_and_issuer_filename():
    path = build_drive_relative_path(
        doc_type="invoice",
        issuer="Google Workspace",
        document_id="23984u2938429834u283",
        description="unused when id present",
        ext="pdf",
        document_date=date(2026, 12, 31),
    )
    assert path == (
        "Invoices/2026/2026-12-31-Google-Workspace-invoice-23984u2938429834u283.pdf"
    )


def test_invoice_path_falls_back_to_today_and_description():
    path = build_drive_relative_path(
        doc_type="invoice",
        issuer="Acme GmbH",
        document_id=None,
        description="acme 1042",
        ext="pdf",
        document_date=None,
        today=date(2026, 9, 7),
    )
    assert path == "Invoices/2026/2026-09-07-Acme-Gmbh-invoice-Acme-1042.pdf"


def test_bureaucracy_and_other_year_folders():
    assert build_drive_relative_path(
        "bureaucracy",
        issuer="Finanzamt Berlin",
        description="tax notice",
        ext="pdf",
        document_date=date(2026, 9, 7),
    ).startswith("Documents/2026/")
    assert build_drive_relative_path(
        "other",
        issuer=None,
        description="overview",
        ext="xlsx",
        document_date=date(2026, 9, 7),
    ).startswith("Other/2026/")
