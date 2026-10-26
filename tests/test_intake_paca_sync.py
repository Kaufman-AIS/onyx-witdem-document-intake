"""Tests for optional Paca board sync after intake."""

from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from witdem_onyx_demo.intake.models import IntakeResult
from witdem_onyx_demo.intake.paca_sync import maybe_sync_intake_to_paca, paca_env_configured


def test_paca_env_configured_false_by_default(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("PACA_API_URL", raising=False)
    monkeypatch.delenv("PACA_API_KEY", raising=False)
    monkeypatch.delenv("PACA_PROJECT_ID", raising=False)
    assert paca_env_configured() is False


def test_maybe_sync_noop_when_unconfigured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("PACA_API_URL", raising=False)
    result = IntakeResult(
        ok=True,
        doc_type="invoice",
        drive_path="a/b",
        drive_url="https://drive.example/x",
        message="stored",
    )
    out = maybe_sync_intake_to_paca(result)
    assert out.ok is True
    assert out.message == "stored"
    assert out.error is None


def test_maybe_sync_marks_failure_loudly(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("PACA_API_URL", "https://paca.example")
    monkeypatch.setenv("PACA_API_KEY", "k")
    monkeypatch.setenv("PACA_PROJECT_ID", "p")

    def boom(_result: IntakeResult) -> dict:
        raise RuntimeError("down")

    monkeypatch.setattr(
        "witdem_onyx_demo.intake.paca_sync.sync_intake_to_paca",
        boom,
    )
    result = IntakeResult(
        ok=True,
        doc_type="invoice",
        drive_path="a/b",
        drive_url="https://drive.example/x",
        message="stored",
    )
    out = maybe_sync_intake_to_paca(result)
    assert out.ok is False
    assert out.error and "Paca sync failed" in out.error
