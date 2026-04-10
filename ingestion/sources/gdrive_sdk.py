"""Google Drive ingestion via official Drive API (SDK)."""
from __future__ import annotations

import io
import json
import logging
import os
import tempfile
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)


def _ensure_dotenv_loaded() -> None:
    """Load project .env so GOOGLE_DRIVE_CREDENTIALS_PATH is set when this module runs outside app startup."""
    root = Path(__file__).resolve().parent.parent.parent
    env_path = root / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        pass


from langchain_core.documents import Document
from langchain_community.document_loaders import (
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

_FOLDER_MIME = "application/vnd.google-apps.folder"

_MIME_Q = (
    "(mimeType = 'application/vnd.google-apps.document' or "
    "mimeType = 'application/vnd.google-apps.spreadsheet' or "
    "mimeType = 'application/vnd.google-apps.presentation' or "
    "mimeType = 'text/plain' or mimeType = 'text/markdown' or mimeType = 'text/csv' or "
    "mimeType = 'application/pdf' or "
    "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')"
)


def _mime_type_supported(mime: str) -> bool:
    if not mime or mime == _FOLDER_MIME:
        return False
    return mime in DRIVE_EXPORT_MIMES or mime in DRIVE_DOWNLOAD_MIMES


def _list_files_recursive(
    service,
    root_folder_id: str,
    max_files: int,
) -> list[dict]:
    """Breadth-first walk: collect supported files under root_folder_id (including nested folders)."""
    qfolders: deque[str] = deque([root_folder_id])
    visited: set[str] = set()
    out: list[dict] = []
    while qfolders and len(out) < max_files:
        parent = qfolders.popleft()
        if parent in visited:
            continue
        visited.add(parent)
        page_token: str | None = None
        while True:
            kwargs: dict = {
                "q": f"'{parent}' in parents and trashed = false",
                "pageSize": 100,
                "fields": "nextPageToken, files(id, name, mimeType)",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = service.files().list(**kwargs).execute()
            for item in resp.get("files", []):
                mid = item.get("mimeType", "")
                if mid == _FOLDER_MIME:
                    qfolders.append(item["id"])
                elif _mime_type_supported(mid):
                    out.append(item)
                    if len(out) >= max_files:
                        return out
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return out


def _resolve_credentials_path(path: str | None) -> str | None:
    """Resolve relative paths against project root so they work from any cwd."""
    if not path or not path.strip():
        return None
    path = path.strip()
    if os.path.isabs(path):
        return path
    project_root = Path(__file__).resolve().parent.parent.parent
    return str((project_root / path).resolve())


# Raw JSON string (e.g. Railway secret) — avoids committing secrets/ to the image.
_GOOGLE_DRIVE_SA_JSON_ENV = "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"


def _service_account_info_from_env() -> dict | None:
    """Parse service account JSON from GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON if set."""
    raw = (os.environ.get(_GOOGLE_DRIVE_SA_JSON_ENV) or "").strip()
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{_GOOGLE_DRIVE_SA_JSON_ENV} must be valid JSON (single-line or paste the full key). {e}"
        ) from e
    if info.get("type") != "service_account":
        raise ValueError(
            f"{_GOOGLE_DRIVE_SA_JSON_ENV} must be a Google service account key (type: service_account)."
        )
    return info


def _get_drive_service(credentials_path: str | None = None):
    """Build Drive API v3 service using service account JSON or Application Default Credentials."""
    _ensure_dotenv_loaded()
    try:
        import google.auth
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            "Google Drive SDK requires: pip install google-api-python-client google-auth google-auth-httplib2"
        ) from e

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    info = _service_account_info_from_env()
    if info is not None:
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        return build("drive", "v3", credentials=creds)

    tried: list[str] = []
    for raw in (
        credentials_path,
        os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    ):
        path = _resolve_credentials_path(raw)
        if not path:
            continue
        tried.append(path)
        if os.path.isfile(path):
            try:
                creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
                return build("drive", "v3", credentials=creds)
            except Exception as e:
                raise ValueError(
                    f"Could not load Google service account credentials from {path}: {e}"
                ) from e

    if tried:
        raise ValueError(
            "Google Drive SDK: credentials path(s) set but no valid JSON file found. "
            f"Checked: {tried}. On Railway/cloud, commit no secrets: set "
            f"{_GOOGLE_DRIVE_SA_JSON_ENV} to the full service account JSON string, or mount the key file and set "
            "GOOGLE_APPLICATION_CREDENTIALS. Locally you can use GOOGLE_DRIVE_CREDENTIALS_PATH=secrets/your-key.json."
        )

    try:
        creds, _ = google.auth.default(scopes=scopes)
    except Exception as e:
        raise ValueError(
            "Google Drive SDK: no service account JSON found. Set GOOGLE_DRIVE_CREDENTIALS_PATH in .env "
            "to your Google Cloud service account key file (e.g. secrets/your-key.json), share Drive folders "
            "with that service account's client_email, enable the Drive API for the project, then restart the app. "
            f"Alternatively configure Application Default Credentials. Details: {e}"
        ) from e
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
    except Exception as e:
        logger.warning("gdrive_sdk: failed to load file %s (%s): %s", name, mime_type, e)
        return None
    return None


def _looks_like_drive_id(s: str) -> bool:
    """Heuristic: Drive file IDs are long alphanumeric (and sometimes - _)."""
    if len(s) < 20 or len(s) > 100:
        return False
    return all(c.isalnum() or c in "-_" for c in s)


def _client_email_hint(credentials_path: str | None) -> str:
    """Read client_email from the service account JSON for error messages."""
    info = _service_account_info_from_env()
    if info and info.get("client_email"):
        return str(info["client_email"])
    for raw in (
        credentials_path,
        os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    ):
        path = _resolve_credentials_path(raw)
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    em = json.load(f).get("client_email")
                    if em:
                        return em
            except Exception:
                continue
    return "the address in client_email inside your service account JSON key"


def _assert_folder_readable(service, folder_id: str, sa_email: str) -> None:
    """Ensure the folder exists and is visible to the service account (clearer than empty list)."""
    from googleapiclient.errors import HttpError

    try:
        meta = service.files().get(
            fileId=folder_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(
                f"Google Drive: folder ID {folder_id!r} was not found or is not visible to the service account "
                f"({sa_email}). Open the folder in Drive → Share → add {sa_email} with Viewer (or add it to the "
                "Shared drive as a member). A 404 here usually means no access, not a wrong ID."
            ) from e
        raise ValueError(f"Google Drive API error reading folder metadata: {e}") from e

    if meta.get("mimeType") != _FOLDER_MIME:
        raise ValueError(
            f"The ID {folder_id!r} is not a folder (it is {meta.get('mimeType', 'unknown')!r}). "
            "Use the folder ID from the URL: https://drive.google.com/drive/folders/FOLDER_ID"
        ) from None


def _resolve_folder_id(service, folder_name_or_id: str) -> str | None:
    """Return folder ID. If input looks like an ID, return as-is; else search for folder by name."""
    folder_name_or_id = (folder_name_or_id or "").strip()
    if not folder_name_or_id:
        return None
    if _looks_like_drive_id(folder_name_or_id):
        return folder_name_or_id
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
    *,
    recursive: bool = True,
) -> list[Document]:
    """
    List files from Google Drive (optionally under folder_id or folder name) and load supported documents.
    folder_id can be a Drive folder ID or a folder name (searched in Drive).
    When recursive is True (default), includes supported files in subfolders (breadth-first, up to max_files).
    Uses GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON (raw JSON), or GOOGLE_DRIVE_CREDENTIALS_PATH /
    GOOGLE_APPLICATION_CREDENTIALS (file paths), for auth.
    """
    service = _get_drive_service(credentials_path)
    sa_email = _client_email_hint(credentials_path)
    resolved_folder_id = _resolve_folder_id(service, folder_id) if folder_id else None

    if resolved_folder_id:
        _assert_folder_readable(service, resolved_folder_id, sa_email)

    if resolved_folder_id and recursive:
        files = _list_files_recursive(service, resolved_folder_id, max_files)
    elif resolved_folder_id:
        query = f"trashed = false and {_MIME_Q} and '{resolved_folder_id}' in parents"
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
    else:
        query = f"trashed = false and {_MIME_Q}"
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

    logger.info("gdrive_sdk: listed %s candidate file(s) for folder=%s recursive=%s", len(files), folder_id, recursive)

    docs: list[Document] = []
    for f in files:
        fid = f["id"]
        name = f.get("name", "unknown")
        mime = f.get("mimeType", "")
        content = _load_file_content(service, fid, mime, name)
        if content:
            docs.append(Document(page_content=content, metadata={"source": f"gdrive://{name}", "file_id": fid}))

    if docs:
        return docs

    if not files:
        if resolved_folder_id:
            raise ValueError(
                f"Google Drive (service account {sa_email}): folder is reachable but contains no supported files "
                f"(recursive={recursive}). Add Google Docs, Sheets, Slides, PDF, TXT, Markdown, CSV, or DOCX — or put "
                f"them in subfolders with 'Include subfolders' enabled. "
                f"Note: uploaded Excel .xlsx / native Google Drive shortcuts-only folders may list 0 matching files."
            )
        raise ValueError(
            f"Google Drive (service account {sa_email}): no supported files found in Drive scope (try a folder ID to narrow)."
        )

    names_preview = ", ".join(f"{f.get('name', '?')} ({f.get('mimeType', '?')})" for f in files[:8])
    if len(files) > 8:
        names_preview += f", … (+{len(files) - 8} more)"
    raise ValueError(
        f"Google Drive (service account {sa_email}): found {len(files)} matching file(s) but failed to load text from all of them: "
        f"{names_preview}. Check server logs for export/download errors (permissions, file size, or MIME handling)."
    )
