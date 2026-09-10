"""Download original chat uploads from the Onyx API."""

from __future__ import annotations

import json
import unicodedata
import urllib.error
import urllib.request
from typing import Any, Protocol


class OnyxFileError(RuntimeError):
    """Raised when an Onyx chat file cannot be downloaded."""


class OnyxFileFetcher(Protocol):
    def download(self, file_id: str) -> tuple[bytes, str | None]: ...

    def resolve_file_id_by_name(self, filename: str) -> str | None: ...


def _norm_name(value: str) -> str:
    """Casefold + NFC so macOS/NFD upload names match NFC tool args."""
    return unicodedata.normalize("NFC", value).casefold()


class OnyxFileClient:
    """Fetch chat uploads via Onyx REST (Bearer API key)."""

    def __init__(self, *, api_base_url: str, api_key: str, timeout_s: float = 60.0) -> None:
        base = api_base_url.rstrip("/")
        if not base:
            raise ValueError("api_base_url is required")
        if not api_key:
            raise ValueError("api_key is required")
        self._api_base_url = base
        self._api_key = api_key
        self._timeout_s = timeout_s

    def download(self, file_id: str) -> tuple[bytes, str | None]:
        fid = (file_id or "").strip()
        if not fid:
            raise OnyxFileError("file_id is empty")
        url = f"{self._api_base_url}/chat/file/{fid}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type")
                return data, content_type
        except urllib.error.HTTPError as e:
            raise OnyxFileError(f"Onyx file download failed ({e.code}) for {fid}") from e
        except urllib.error.URLError as e:
            raise OnyxFileError(f"Onyx file download failed for {fid}: {e}") from e

    def resolve_file_id_by_name(self, filename: str) -> str | None:
        name = (filename or "").strip()
        if not name:
            return None
        url = f"{self._api_base_url}/user/files/recent"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise OnyxFileError(f"Onyx recent files failed ({e.code})") from e
        except urllib.error.URLError as e:
            raise OnyxFileError(f"Onyx recent files failed: {e}") from e

        try:
            items: list[dict[str, Any]] = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise OnyxFileError("Onyx recent files returned invalid JSON") from e

        needle = _norm_name(name)
        for item in items:
            if _norm_name(str(item.get("name") or "")) != needle:
                continue
            file_id = item.get("file_id") or item.get("id")
            if file_id:
                return str(file_id)
        return None
