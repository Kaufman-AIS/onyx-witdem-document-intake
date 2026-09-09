from pathlib import Path

from witdem_onyx_demo.cases import load_cases


def test_load_cases():
    cases = load_cases(Path(__file__).resolve().parents[1] / "cases")
    ids = {case.case_id for case in cases}
    assert ids == {"grounded-answer", "support-sla", "no-evidence"}
    assert all(case.contract == "knowledge_answer" for case in cases)
