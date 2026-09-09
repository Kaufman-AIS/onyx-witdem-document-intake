"""Intake tool server configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeSettings:
    google_application_credentials: str | None
    google_drive_root_folder_id: str | None
    google_tasks_list_id: str | None
    intake_tool_url: str
    intake_use_memory: bool
    openai_api_key: str | None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_refresh_token: str | None = None
    onyx_api_base_url: str | None = None
    onyx_api_key: str | None = None

    @property
    def has_tasks_oauth(self) -> bool:
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_secret
            and self.google_oauth_refresh_token
        )

    @property
    def has_onyx_file_api(self) -> bool:
        return bool(self.onyx_api_base_url and self.onyx_api_key)


def load_settings() -> IntakeSettings:
    use_memory_raw = os.environ.get("INTAKE_USE_MEMORY", "").strip().lower()
    if use_memory_raw in {"1", "true", "yes", "on"}:
        intake_use_memory = True
    elif use_memory_raw in {"0", "false", "no", "off"}:
        intake_use_memory = False
    else:
        # Default: memory when Google credentials are missing.
        intake_use_memory = not bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip())

    return IntakeSettings(
        google_application_credentials=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or None,
        google_drive_root_folder_id=os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID") or None,
        google_tasks_list_id=os.environ.get("GOOGLE_TASKS_LIST_ID") or None,
        intake_tool_url=os.environ.get(
            "INTAKE_TOOL_URL", "http://127.0.0.1:8091/tools/run_intake"
        ),
        intake_use_memory=intake_use_memory,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        google_oauth_client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or None,
        google_oauth_client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or None,
        google_oauth_refresh_token=os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN") or None,
        onyx_api_base_url=os.environ.get("ONYX_API_BASE_URL") or None,
        onyx_api_key=os.environ.get("ONYX_API_KEY") or None,
    )
