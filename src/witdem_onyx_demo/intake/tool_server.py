"""HTTP tool server exposing run_intake for Onyx custom tools."""

from __future__ import annotations

import base64
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from witdem_onyx_demo.intake.drive import DriveClient, GoogleDriveClient, InMemoryDrive
from witdem_onyx_demo.intake.extract import Extractor, FakeExtractor, LlmExtractor
from witdem_onyx_demo.intake.models import IntakeRequest, IntakeResult
from witdem_onyx_demo.intake.oauth import user_credentials_from_refresh_token
from witdem_onyx_demo.intake.onyx_files import OnyxFileError, OnyxFileFetcher, OnyxFileClient
from witdem_onyx_demo.intake.pipeline import run_intake
from witdem_onyx_demo.intake.settings import IntakeSettings, load_settings
from witdem_onyx_demo.intake.tasks_client import GoogleTasksClient, InMemoryTasks, TasksClient


def _default_clients(
    settings: IntakeSettings,
) -> tuple[DriveClient, TasksClient, Extractor]:
    if settings.intake_use_memory or not settings.google_application_credentials:
        return InMemoryDrive(), InMemoryTasks(), FakeExtractor()

    if not settings.google_drive_root_folder_id:
        raise ValueError("GOOGLE_DRIVE_ROOT_FOLDER_ID is required when not using memory clients")
    if not settings.google_tasks_list_id:
        raise ValueError("GOOGLE_TASKS_LIST_ID is required when not using memory clients")

    drive: DriveClient = GoogleDriveClient(
        credentials_path=settings.google_application_credentials,
        root_folder_id=settings.google_drive_root_folder_id,
    )
    if settings.has_tasks_oauth:
        tasks: TasksClient = GoogleTasksClient(
            list_id=settings.google_tasks_list_id,
            credentials=user_credentials_from_refresh_token(
                client_id=settings.google_oauth_client_id or "",
                client_secret=settings.google_oauth_client_secret or "",
                refresh_token=settings.google_oauth_refresh_token or "",
            ),
        )
    else:
        tasks = GoogleTasksClient(
            credentials_path=settings.google_application_credentials,
            list_id=settings.google_tasks_list_id,
        )
    extractor: Extractor = (
        LlmExtractor(api_key=settings.openai_api_key)
        if settings.openai_api_key
        else FakeExtractor()
    )
    return drive, tasks, extractor


def _default_onyx_files(settings: IntakeSettings) -> OnyxFileFetcher | None:
    if not settings.has_onyx_file_api:
        return None
    return OnyxFileClient(
        api_base_url=settings.onyx_api_base_url or "",
        api_key=settings.onyx_api_key or "",
    )


def _expects_binary_upload(*, filename: str | None, mime_type: str | None) -> bool:
    name = (filename or "").casefold()
    mime = (mime_type or "").casefold()
    if mime.startswith("application/pdf") or mime in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "image/png",
        "image/jpeg",
    }:
        return True
    return name.endswith((".pdf", ".xlsx", ".xls", ".docx", ".png", ".jpg", ".jpeg"))


def create_app(
    *,
    drive: DriveClient | None = None,
    tasks: TasksClient | None = None,
    extractor: Extractor | None = None,
    settings: IntakeSettings | None = None,
    onyx_files: OnyxFileFetcher | None = None,
) -> Starlette:
    cfg = settings or load_settings()
    if drive is None or tasks is None or extractor is None:
        default_drive, default_tasks, default_extractor = _default_clients(cfg)
        drive = drive or default_drive
        tasks = tasks or default_tasks
        extractor = extractor or default_extractor
    file_fetcher = onyx_files if onyx_files is not None else _default_onyx_files(cfg)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def run_intake_tool(request: Request) -> JSONResponse:
        body: dict[str, Any] = await request.json()
        # Onyx OpenAPI tools often nest JSON args under requestBody.
        if isinstance(body.get("requestBody"), dict) and not body.get("text"):
            body = {**body["requestBody"]}

        file_bytes: bytes | None = None
        raw_b64 = body.get("file_base64")
        if raw_b64:
            file_bytes = base64.b64decode(raw_b64)

        mime_type = body.get("mime_type")
        filename = body.get("filename")
        file_ref = body.get("file_id") or body.get("user_file_id")

        if file_bytes is None and not file_ref and filename and file_fetcher is not None:
            try:
                file_ref = file_fetcher.resolve_file_id_by_name(str(filename))
            except OnyxFileError as e:
                result = IntakeResult(
                    ok=False,
                    doc_type="other",
                    drive_path=None,
                    drive_url=None,
                    error=str(e),
                    message=f"Intake failed: {e}",
                )
                return JSONResponse(result.as_tool_dict())

        if file_bytes is None and file_ref:
            if file_fetcher is None:
                result = IntakeResult(
                    ok=False,
                    doc_type="other",
                    drive_path=None,
                    drive_url=None,
                    error="ONYX_API_BASE_URL/ONYX_API_KEY required to fetch file_id",
                    message="Intake failed: Onyx file API not configured",
                )
                return JSONResponse(result.as_tool_dict())
            try:
                file_bytes, content_type = file_fetcher.download(str(file_ref))
            except OnyxFileError as e:
                result = IntakeResult(
                    ok=False,
                    doc_type="other",
                    drive_path=None,
                    drive_url=None,
                    error=str(e),
                    message=f"Intake failed: {e}",
                )
                return JSONResponse(result.as_tool_dict())
            if not mime_type and content_type:
                mime_type = content_type.split(";")[0].strip()

        if file_bytes is None and _expects_binary_upload(
            filename=str(filename) if filename else None,
            mime_type=str(mime_type) if mime_type else None,
        ):
            result = IntakeResult(
                ok=False,
                doc_type="other",
                drive_path=None,
                drive_url=None,
                error="missing original file bytes (pass file_id or ensure filename matches an Onyx upload)",
                message=(
                    "Intake failed: original file not found in Onyx. "
                    "Re-upload the PDF and retry, or pass file_id."
                ),
            )
            return JSONResponse(result.as_tool_dict())

        intake_request = IntakeRequest(
            text=str(body.get("text") or ""),
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            chat_session_id=body.get("chat_session_id"),
            source=str(body.get("source") or "onyx"),
        )
        result = run_intake(
            intake_request,
            drive=drive,
            tasks=tasks,
            extractor=extractor,
        )
        return JSONResponse(result.as_tool_dict())

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/tools/run_intake", run_intake_tool, methods=["POST"]),
        ]
    )


app = create_app()
