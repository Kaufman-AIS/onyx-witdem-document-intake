"""Transparent reverse proxy for Onyx UI with Witdem instrumentation."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse

from witdem_onyx_demo.contracts import UI_CHAT_CONTRACT, UPLOAD_CONTRACT
from witdem_onyx_demo.proxy.recording import (
    input_modalities_from_request,
    record_chat_execution,
    record_upload_execution,
)
from witdem_onyx_demo.proxy.settings import load_settings
from witdem_onyx_demo.sse_parser import sse_to_chat_response

logger = logging.getLogger(__name__)
settings = load_settings()

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

# Upstream Onyx sends HSTS even over plain HTTP; browsers may then try HTTPS on
# localhost:3000 and hang waiting for TLS on an HTTP-only port.
LOCAL_DEV_STRIP_HEADERS = {
    "strict-transport-security",
}

# httpx auto-decompresses gzip/brotli but leaves Content-Encoding set — browsers
# then try to decode already-plain bodies and the page stays blank/gray.
RESPONSE_STRIP_HEADERS = LOCAL_DEV_STRIP_HEADERS | {
    "content-encoding",
}

REQUEST_STRIP_HEADERS = {
    "accept-encoding",
}


def _request_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
        and key.lower() not in REQUEST_STRIP_HEADERS
    }


def _response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
        and key.lower() not in RESPONSE_STRIP_HEADERS
    }


def _should_redirect_root_to_login(request: Request) -> bool:
    if request.method not in {"GET", "HEAD"}:
        return False
    if request.url.path != "/":
        return False
    # Next.js RSC fetches must pass through unchanged.
    return "_rsc" not in request.query_params


def _execution_name(raw: dict[str, Any]) -> str:
    session_id = raw.get("chat_session_id")
    if session_id:
        return f"Onyx UI chat: {session_id}"
    return "Onyx UI chat: new"


def _parse_request_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    parsed = json.loads(body.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _record_chat_from_body(
    *,
    request_body: dict[str, Any],
    response_bytes: bytes,
    content_type: str,
) -> None:
    message = str(request_body.get("message") or "")
    modalities = input_modalities_from_request(request_body)
    if "text/event-stream" in content_type or response_bytes.startswith(b"data:"):
        raw = sse_to_chat_response(response_bytes.decode("utf-8", errors="replace"))
    else:
        parsed = json.loads(response_bytes.decode("utf-8"))
        raw = parsed if isinstance(parsed, dict) else {}
    record_chat_execution(
        config_path=settings.config_path,
        raw=raw,
        message=message,
        input_modalities=modalities,
        execution_name=_execution_name(raw),
        contract=UI_CHAT_CONTRACT,
        attributes={"source": "onyx_ui"},
    )


async def _build_upstream_request(request: Request, body: bytes) -> tuple[httpx.AsyncClient, httpx.Request]:
    url = f"{settings.upstream}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    upstream_request = client.build_request(
        request.method,
        url,
        headers=_request_headers(request.headers),
        content=body,
    )
    return client, upstream_request


async def _handle_chat_message(request: Request) -> Response:
    body = await request.body()
    request_body = _parse_request_body(body)
    client, upstream_request = await _build_upstream_request(request, body)
    upstream = await client.send(upstream_request, stream=True)
    content_type = upstream.headers.get("content-type", "")

    if "text/event-stream" in content_type:
        chunks: list[bytes] = []

        async def streamer() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.aiter_bytes():
                    chunks.append(chunk)
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()
                try:
                    _record_chat_from_body(
                        request_body=request_body,
                        response_bytes=b"".join(chunks),
                        content_type=content_type,
                    )
                except Exception:
                    logger.exception("Chat telemetry recording failed")

        return StreamingResponse(
            streamer(),
            status_code=upstream.status_code,
            headers=_response_headers(upstream.headers),
            media_type=content_type,
        )

    response_body = await upstream.aread()
    await upstream.aclose()
    await client.aclose()
    try:
        _record_chat_from_body(
            request_body=request_body,
            response_bytes=response_body,
            content_type=content_type,
        )
    except Exception:
        logger.exception("Chat telemetry recording failed")

    return Response(
        content=response_body,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers),
        media_type=content_type or None,
    )


async def _handle_chat_file(request: Request) -> Response:
    body = await request.body()
    client, upstream_request = await _build_upstream_request(request, body)
    upstream = await client.send(upstream_request, stream=False)
    try:
        if upstream.status_code < 400:
            payload = upstream.json()
            files = payload.get("files") if isinstance(payload, dict) else None
            if isinstance(files, list):
                file_types = [
                    str(item.get("type"))
                    for item in files
                    if isinstance(item, dict) and item.get("type")
                ]
                record_upload_execution(
                    config_path=settings.config_path,
                    file_types=file_types,
                    file_count=len(files),
                    contract=UPLOAD_CONTRACT,
                )
    except Exception:
        logger.exception("Upload telemetry recording failed")
    finally:
        await client.aclose()

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


async def _handle_request(request: Request) -> Response:
    if _should_redirect_root_to_login(request):
        return RedirectResponse(url="/auth/login", status_code=307)

    if request.method == "POST" and request.url.path == "/api/chat/send-chat-message":
        return await _handle_chat_message(request)
    if request.method == "POST" and request.url.path == "/api/chat/file":
        return await _handle_chat_file(request)

    body = await request.body()
    client, upstream_request = await _build_upstream_request(request, body)
    upstream = await client.send(upstream_request, stream=True)
    content_type = upstream.headers.get("content-type", "")

    async def passthrough() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    if "text/event-stream" in content_type:
        return StreamingResponse(
            passthrough(),
            status_code=upstream.status_code,
            headers=_response_headers(upstream.headers),
            media_type=content_type,
        )

    response_body = await upstream.aread()
    await upstream.aclose()
    await client.aclose()
    return Response(
        content=response_body,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers),
        media_type=content_type or None,
    )


app = Starlette()
app.add_route("/{path:path}", _handle_request, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
