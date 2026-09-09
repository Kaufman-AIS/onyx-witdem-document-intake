"""Unit tests for witdem-proxy response shaping."""

from __future__ import annotations

import httpx
from starlette.requests import Request

from witdem_onyx_demo.proxy.app import (
    LOCAL_DEV_STRIP_HEADERS,
    REQUEST_STRIP_HEADERS,
    RESPONSE_STRIP_HEADERS,
    _request_headers,
    _response_headers,
    _should_redirect_root_to_login,
)


def _request(method: str, path: str, query: str = "") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query.encode(),
        "headers": [],
    }
    return Request(scope)


def test_response_headers_strips_hsts() -> None:
    headers = httpx.Headers(
        {
            "content-type": "text/html",
            "strict-transport-security": "max-age=63072000",
            "transfer-encoding": "chunked",
        }
    )
    filtered = _response_headers(headers)
    assert filtered == {"content-type": "text/html"}
    assert "strict-transport-security" in LOCAL_DEV_STRIP_HEADERS


def test_response_headers_strips_content_encoding() -> None:
    headers = httpx.Headers(
        {
            "content-type": "text/html",
            "content-encoding": "gzip",
            "strict-transport-security": "max-age=63072000",
        }
    )
    filtered = _response_headers(headers)
    assert filtered == {"content-type": "text/html"}
    assert "content-encoding" in RESPONSE_STRIP_HEADERS


def test_request_headers_strips_accept_encoding() -> None:
    headers = httpx.Headers(
        {
            "accept": "text/html",
            "accept-encoding": "gzip, deflate, br",
            "cookie": "session=abc",
        }
    )
    filtered = _request_headers(headers)
    assert filtered == {"accept": "text/html", "cookie": "session=abc"}
    assert "accept-encoding" in REQUEST_STRIP_HEADERS


def test_should_redirect_root_to_login_for_browser_navigation() -> None:
    assert _should_redirect_root_to_login(_request("GET", "/"))
    assert _should_redirect_root_to_login(_request("HEAD", "/"))


def test_should_not_redirect_root_for_rsc_or_non_root() -> None:
    assert not _should_redirect_root_to_login(_request("GET", "/", "_rsc=abc"))
    assert not _should_redirect_root_to_login(_request("GET", "/auth/login"))
    assert not _should_redirect_root_to_login(_request("POST", "/"))
