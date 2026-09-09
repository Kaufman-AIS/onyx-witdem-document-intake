"""Interactive OAuth login for Google Tasks — prints refresh_token for .env."""

from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from witdem_onyx_demo.intake.oauth import TASKS_SCOPES


def main() -> int:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env first.\n"
            "Create an OAuth Desktop client in Google Cloud Console "
            "(APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop).",
            file=sys.stderr,
        )
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=list(TASKS_SCOPES))
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        print(
            "No refresh_token returned. Revoke prior access at "
            "https://myaccount.google.com/permissions and re-run with prompt=consent.",
            file=sys.stderr,
        )
        return 1

    print("\nAdd this to examples/onyx-demo/.env:\n")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print("\nThen restart ./scripts/run-intake-tool.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
