"""Proxy configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProxySettings:
    upstream: str
    witdem_endpoint: str
    config_path: Path
    host: str = "0.0.0.0"
    port: int = 8080


def load_settings() -> ProxySettings:
    demo_root = Path(__file__).resolve().parents[2]
    upstream = os.environ.get("ONYX_UPSTREAM", "http://nginx:80").rstrip("/")
    witdem_endpoint = os.environ.get("WITDEM_ENDPOINT", "http://host.docker.internal:4318")
    config_path = Path(os.environ.get("WITDEM_CONFIG", demo_root / "witdem.yml"))
    host = os.environ.get("PROXY_HOST", "0.0.0.0")
    port = int(os.environ.get("PROXY_PORT", "8080"))
    return ProxySettings(
        upstream=upstream,
        witdem_endpoint=witdem_endpoint,
        config_path=config_path,
        host=host,
        port=port,
    )
