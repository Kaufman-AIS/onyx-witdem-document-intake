"""Load environment from demo-local and witdem-oss root .env files."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

DEMO_ROOT = Path(__file__).resolve().parents[2]
if DEMO_ROOT.name == "onyx-demo":
    EXAMPLES_ROOT = DEMO_ROOT.parent
    REPO_ROOT = EXAMPLES_ROOT.parent
else:
    EXAMPLES_ROOT = DEMO_ROOT
    REPO_ROOT = DEMO_ROOT


def load_demo_env() -> Path | None:
    """Load env files; demo-local overrides repo root."""

    loaded: Path | None = None
    for path in (REPO_ROOT / ".env", EXAMPLES_ROOT / ".env", DEMO_ROOT / ".env"):
        if path.is_file():
            load_dotenv(path, override=loaded is not None)
            loaded = path
    return loaded
