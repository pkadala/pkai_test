"""Google Drive ingestion via official Drive API (SDK)."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    PyPDFLoader,
    Docx2txtLoader,
)

# MIME types we can export or download
DRIVE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
DRIVE_DOWNLOAD_MIMES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _resolve_credentials_path(path: str | None) -> str | None:
    """Resolve relative paths against project root so they work from any cwd."""
    if not path or not path.strip():
        return None
    path = path.strip()
    if os.path.isabs(path) and os.path.isfile(path):
        return path
    # Project root = parent of ingestion package
    project_root = Path(__file__).resolve().parent.parent.parent
    resolved = (project_root / path).resolve()
    return str(resolved) if resolved.is_file() else path


def _get_drive_service(credentials_path: str | None = None):
    """Build Drive API v3 service using service account or default credentials."""
    try:
        import google.auth
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            "Google Drive SDK requires: pip install google-api-python-client google-auth google-auth-httplib2"
        ) from e

    raw_path = credentials_path or os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH")
    path = _resolve_credentials_path(raw_path)
    if path and os.path.isfile(path):
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    else:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds)


def _load_file_content(service, file_id: str, mime_type: str, name: str) -> str | None:
    """Download or export file content and return as text where possible."""
    try:
        if mime_type in DRIVE_EXPORT_MIMES:
            export_mime = DRIVE_EXPORT_MIMES[mime_type]
            result = service.files().export_media(fileId=file_id, mimeType=export_mime).execute()
            if isinstance(result, bytes):
                return result.decode("utf-8", errors="replace")
            return str(result) if result else None
        if mime_type in ("text/plain", "text/markdown", "text/csv"):
            result = service.files().get_media(fileId=file_id).execute()
            if isinstance(result, bytes):
                return result.decode("utf-8", errors="replace")
            return str(result) if result else None
        if mime_type == "application/pdf":
            result = service.files().get_media(fileId=file_id).execute()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(result)
                f.flush()
            try:
                loader = PyPDFLoader(f.name)
                docs = loader.load()
                return "\n\n".join(d.page_content for d in docs) if docs else None
            finally:
                os.unlink(f.name)
        if "wordprocessingml" in mime_type or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            result = service.files().get_media(fileId=file_id).execute()
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(result)
                f.flush()
            try:
                loader = Docx2txtLoader(f.name)
                docs = loader.load()
                return docs[0].page_content if docs else None
            finally:
                os.unlink(f.name)
    except Exception:
        return None
    return None


def _looks_like_drive_id(s: str) -> bool:
    """Heuristic: Drive file IDs are long alphanumeric (and sometimes - _)."""
    if len(s) < 20 or len(s) > 100:
        return False
    return all(c.isalnum() or c in "-_" for c in s)


def _resolve_folder_id(service, folder_name_or_id: str) -> str | None:
    """Return folder ID. If input looks like an ID, return as-is; else search for folder by name."""
    folder_name_or_id = (folder_name_or_id or "").strip()
    if not folder_name_or_id:
        return None
    if _looks_like_drive_id(folder_name_or_id):
        return folder_name_or_id
    # Search for a folder with this name (first match)
    escaped = folder_name_or_id.replace("'", "''")
    q = f"trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = '{escaped}'"
    try:
        results = (
            service.files()
            .list(q=q, pageSize=5, fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        if files:
            return files[0]["id"]
        raise ValueError(f"Google Drive folder not found: '{folder_name_or_id}'")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not resolve Drive folder '{folder_name_or_id}': {e}") from e


def load_documents_gdrive_sdk(
    folder_id: str | None = None,
    credentials_path: str | None = None,
    max_files: int = 100,
) -> list[Document]:
    """
    List files from Google Drive (optionally under folder_id or folder name) and load supported documents.
    folder_id can be a Drive folder ID or a folder name (searched in Drive).
    Uses GOOGLE_DRIVE_CREDENTIALS_PATH or GOOGLE_APPLICATION_CREDENTIALS for auth.
    """
    service = _get_drive_service(credentials_path)
    resolved_folder_id = _resolve_folder_id(service, folder_id) if folder_id else None
    query = "trashed = false and (mimeType = 'application/vnd.google-apps.document' or mimeType = 'application/vnd.google-apps.spreadsheet' or mimeType = 'application/vnd.google-apps.presentation' or mimeType = 'text/plain' or mimeType = 'text/markdown' or mimeType = 'application/pdf' or mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')"
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
            docs.append(Document(page_content=content, metadata={"source": f"gdrive://{name}", "file_id": fid}))
    return docs
