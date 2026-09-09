from __future__ import annotations

import io
import mimetypes
from dataclasses import dataclass
from typing import Any, Protocol

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Root folder must be shared with the service account email
# (client_email in the JSON key), or uploads will fail with 404/403.
DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)


@dataclass
class DriveObject:
    path: str
    url: str
    file_id: str


class DriveClient(Protocol):
    def upload(self, *, relative_path: str, data: bytes, mime_type: str) -> DriveObject: ...


class InMemoryDrive:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self._n = 0

    def upload(self, *, relative_path: str, data: bytes, mime_type: str) -> DriveObject:
        self._n += 1
        self.files[relative_path] = data
        return DriveObject(
            path=relative_path,
            url=f"memory://{relative_path}",
            file_id=f"file-{self._n}",
        )


class GoogleDriveClient:
    """Upload files under GOOGLE_DRIVE_ROOT_FOLDER_ID as Type/YYYY/filename.

    The root folder must be shared with the service account email from
    GOOGLE_APPLICATION_CREDENTIALS so the SA can create nested folders/files.
    """

    def __init__(self, *, credentials_path: str, root_folder_id: str) -> None:
        if not root_folder_id:
            raise ValueError("GOOGLE_DRIVE_ROOT_FOLDER_ID is required for GoogleDriveClient")
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=list(DRIVE_SCOPES)
        )
        self._root_folder_id = root_folder_id
        self._service: Any = build("drive", "v3", credentials=creds, cache_discovery=False)

    def upload(self, *, relative_path: str, data: bytes, mime_type: str) -> DriveObject:
        parts = [p for p in relative_path.strip("/").split("/") if p]
        if len(parts) < 3:
            raise ValueError(f"relative_path must be Type/YYYY/filename, got {relative_path!r}")
        *folder_parts, filename = parts
        parent_id = self._ensure_folder_chain(folder_parts)

        resolved_mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=resolved_mime, resumable=False)
        body = {"name": filename, "parents": [parent_id]}
        created = (
            self._service.files()
            .create(body=body, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
            .execute()
        )
        return DriveObject(
            path=relative_path,
            url=str(created.get("webViewLink") or f"https://drive.google.com/file/d/{created['id']}/view"),
            file_id=str(created["id"]),
        )

    def _ensure_folder_chain(self, folder_parts: list[str]) -> str:
        parent_id = self._root_folder_id
        for name in folder_parts:
            parent_id = self._get_or_create_folder(name=name, parent_id=parent_id)
        return parent_id

    def _get_or_create_folder(self, *, name: str, parent_id: str) -> str:
        safe_name = name.replace("'", "\\'")
        query = (
            f"name = '{safe_name}' and '{parent_id}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        listed = (
            self._service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = listed.get("files") or []
        if files:
            return str(files[0]["id"])

        created = (
            self._service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        return str(created["id"])
