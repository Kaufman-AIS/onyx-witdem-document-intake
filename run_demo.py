#!/usr/bin/env python3
"""Run all Onyx demo cases and send Witdem audit telemetry."""

from __future__ import annotations

import sys

from witdem_onyx_demo.cases import load_cases
from witdem_onyx_demo.instrument import create_client


def main() -> int:
    cases = load_cases()
    client = create_client()
    try:
        for case in cases:
            print(f"Running case {case.case_id}...")
            result = client.run_case(case)
            status = "grounded" if result["grounded"] else "not grounded"
            print(f"  answer length={len(result['answer'])}, {status}, docs={result['document_count']}")
    finally:
        client._client.close()

    print("\nDone. Open http://localhost:8501 for Runs and Workflow replay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
