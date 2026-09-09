"""OAuth user credentials for Google APIs (Tasks on company accounts)."""

from __future__ import annotations

from typing import Sequence

from google.oauth2.credentials import Credentials

TASKS_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/tasks",)


def user_credentials_from_refresh_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: Sequence[str] = TASKS_SCOPES,
) -> Credentials:
    """Build user credentials that refresh access tokens via the OAuth client."""
    if not client_id or not client_secret or not refresh_token:
        raise ValueError(
            "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and "
            "GOOGLE_OAUTH_REFRESH_TOKEN are required for Tasks OAuth"
        )
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )
