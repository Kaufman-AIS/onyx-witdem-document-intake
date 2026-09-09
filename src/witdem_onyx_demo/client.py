"""HTTP client for the Onyx chat API."""

from __future__ import annotations

import os
from typing import Any

import httpx


from urllib.parse import urlparse


def _tls_verify(base_url: str) -> bool:
    explicit = os.environ.get("ONYX_TLS_VERIFY", "").lower()
    if explicit in {"0", "false", "no"}:
        return False
    if explicit in {"1", "true", "yes"}:
        return True
    host = urlparse(base_url).hostname or ""
    return host not in {"localhost", "127.0.0.1", "::1"}


class OnyxClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        persona_id: str | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.persona_id = persona_id
        self._client = httpx.Client(
            timeout=timeout,
            verify=_tls_verify(base_url),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @classmethod
    def from_env(cls) -> OnyxClient:
        base_url = os.environ.get("ONYX_API_BASE_URL", "http://127.0.0.1:3001/api")
        api_key = os.environ.get("ONYX_API_KEY")
        if not api_key:
            raise ValueError("ONYX_API_KEY is required")
        persona_id = os.environ.get("ONYX_PERSONA_ID") or None
        return cls(base_url=base_url, api_key=api_key, persona_id=persona_id)

    def send_message(
        self,
        message: str,
        *,
        include_citations: bool = True,
        persona_id: str | None = None,
        deep_research: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "stream": False,
            "include_citations": include_citations,
            "deep_research": deep_research,
        }
        resolved_persona = persona_id or self.persona_id
        if resolved_persona:
            payload["chat_session_info"] = {"persona_id": resolved_persona}

        response = self._client.post(f"{self.base_url}/chat/send-chat-message", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("unexpected Onyx response shape")
        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OnyxClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
