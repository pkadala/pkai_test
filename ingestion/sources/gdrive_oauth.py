"""Google Drive ingestion via user OAuth (full Drive access for the signed-in user)."""
from __future__ import annotations

from langchain_core.documents import Document

from ingestion.sources.gdrive_sdk import (
    _load_file_content,
    _resolve_folder_id,
)


def _get_drive_service_oauth(client_id: str, client_secret: str):
    """Build Drive API v3 service using stored user OAuth tokens."""
    from googleapiclient.discovery import build

    from app.google_oauth import load_drive_credentials

    creds = load_drive_credentials(client_id, client_secret)
    return build("drive", "v3", credentials=creds)


def load_documents_gdrive_oauth(
    folder_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    max_files: int = 100,
) -> list[Document]:
    """
    List files from the user's Google Drive (OAuth) and load supported documents.
    Uses stored tokens from /auth/google/drive flow. folder_id is optional (name or ID); blank = whole Drive.
    """
    from app import env as env_loader

    cid = client_id or env_loader.google_oauth_client_id()
    csecret = client_secret or env_loader.google_oauth_client_secret()
    if not cid or not csecret:
        raise ValueError(
            "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET, "
            "then connect via the Ingest page (Connect Google Drive)."
        )
    service = _get_drive_service_oauth(cid, csecret)
    resolved_folder_id = _resolve_folder_id(service, folder_id) if folder_id else None
    query = (
        "trashed = false and (mimeType = 'application/vnd.google-apps.document' or "
        "mimeType = 'application/vnd.google-apps.spreadsheet' or "
        "mimeType = 'application/vnd.google-apps.presentation' or "
        "mimeType = 'text/plain' or mimeType = 'text/markdown' or "
        "mimeType = 'application/pdf' or "
        "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')"
    )
    if resolved_folder_id:
        query += f" and '{resolved_folder_id}' in parents"
    results = (
        service.files()
        .list(
            q=query,
            pageSize=min(max_files, 100),
            fields="nextPageToken, files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = results.get("files", [])
    docs = []
    for f in files:
        fid = f["id"]
        name = f.get("name", "unknown")
        mime = f.get("mimeType", "")
        content = _load_file_content(service, fid, mime, name)
        if content:
            docs.append(
                Document(page_content=content, metadata={"source": f"gdrive_oauth://{name}", "file_id": fid})
            )
    return docs
