import json
from pathlib import Path

import pytest


@pytest.fixture
def load_fixture():
    root = Path(__file__).parent / "fixtures"

    def _load(name: str) -> dict:
        return json.loads((root / name).read_text(encoding="utf-8"))

    return _load
