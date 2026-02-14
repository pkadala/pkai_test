"""Google OAuth for Drive: token storage and flow helpers."""
from __future__ import annotations

import json
from pathlib import Path

DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILENAME = "gdrive_oauth_tokens.json"


def _token_path() -> Path:
    """Path to stored OAuth tokens (in project secrets/)."""
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "secrets" / TOKEN_FILENAME


def has_drive_oauth_tokens() -> bool:
    """Return True if we have stored refresh token for Drive."""
    path = _token_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text())
        return bool(data.get("refresh_token"))
    except Exception:
        return False


def load_drive_credentials(client_id: str, client_secret: str):
    """
    Load credentials from stored tokens; refresh if needed.
    Raises FileNotFoundError or ValueError if not configured or no refresh_token.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    path = _token_path()
    if not path.is_file():
        raise FileNotFoundError("Google Drive OAuth not connected. Use 'Connect Google Drive' on the Ingest page.")
    data = json.loads(path.read_text())
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise ValueError("No refresh_token in stored tokens. Reconnect via Ingest page.")
    creds = Credentials(
        token=data.get("token"),
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=DRIVE_SCOPE,
    )
    if creds.expiry is None and data.get("expiry"):
        from datetime import datetime
        try:
            creds.expiry = datetime.fromisoformat(data["expiry"].replace("Z", "+00:00"))
        except Exception:
            pass
    creds.refresh(Request())
    # Optionally write back refreshed token
    if creds.token and creds.expiry:
        save_drive_tokens(creds)
    return creds


def save_drive_tokens(credentials) -> None:
    """Persist credentials (refresh_token, token, expiry) to secrets/."""
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "refresh_token": credentials.refresh_token,
        "token": credentials.token,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
    path.write_text(json.dumps(data, indent=2))
