"""Load YAML demo cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from witdem_onyx_demo.contracts import CASE_CONTRACT


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    message: str
    expected_grounded: bool
    contract: str
    expectations: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


def load_cases(cases_dir: Path | None = None) -> list[DemoCase]:
    root = cases_dir or Path(__file__).resolve().parents[2] / "cases"
    cases: list[DemoCase] = []
    for path in sorted(root.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"invalid case file: {path}")
        contract = str(raw.get("contract") or CASE_CONTRACT)
        cases.append(
            DemoCase(
                case_id=str(raw["case_id"]),
                message=str(raw["message"]),
                expected_grounded=bool(raw.get("expected_grounded", False)),
                contract=contract,
                expectations=dict(raw.get("expectations") or {}),
                tags=[str(tag) for tag in raw.get("tags") or []],
            )
        )
    if not cases:
        raise ValueError(f"no cases found in {root}")
    return cases
