#!/usr/bin/env python3
"""Minimal Google Drive API connectivity test (no LangChain). Run from project root."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env", override=False)
except ImportError:
    print("Install: pip install python-dotenv google-api-python-client google-auth google-auth-httplib2")
    sys.exit(1)

FOLDER_ID = os.environ.get("TEST_GDRIVE_FOLDER_ID", "1Dr48ha9e5aBbgnGLuhmwhLNhGHT89Ih6")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def resolve_key_path() -> Path | None:
    raw = (os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() and p.is_file():
        return p
    cand = (project_root / raw).resolve()
    return cand if cand.is_file() else None


def main() -> None:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_path = resolve_key_path()
    if not key_path:
        print("ERROR: Set GOOGLE_DRIVE_CREDENTIALS_PATH in .env to your service account JSON (e.g. secrets/file.json)")
        sys.exit(1)

    with open(key_path) as f:
        meta = json.load(f)
    email = meta.get("client_email", "?")
    key_id = meta.get("private_key_id", "?")
    print(f"Key file: {key_path.name}")
    print(f"Service account: {email}")
    print(f"private_key_id (metadata only): {key_id[:8]}...")
    print()

    try:
        creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        print(f"FAILED to build credentials or service: {e}")
        sys.exit(2)

    # 1) Cheap API call — proves JWT + API enabled
    try:
        service.files().list(pageSize=1, fields="files(id,name)").execute()
        print("OK: Drive API responded to files.list (credentials work).")
    except Exception as e:
        print(f"FAILED: files.list: {e}")
        print("Check: Google Drive API enabled for the GCP project; key not disabled in IAM → Service account → Keys.")
        sys.exit(3)

    # 2) Folder access (optional)
    if FOLDER_ID:
        try:
            folder = service.files().get(
                fileId=FOLDER_ID,
                fields="id,name,mimeType",
                supportsAllDrives=True,
            ).execute()
            print(f"OK: Can read folder: {folder.get('name', '?')} ({folder.get('id')})")
        except Exception as e:
            print(f"FAILED: Cannot read folder {FOLDER_ID}: {e}")
            print("Share that folder (or Shared drive) with the service account email above (Viewer is enough).")
            sys.exit(4)

        try:
            children = (
                service.files()
                .list(
                    q=f"'{FOLDER_ID}' in parents and trashed = false",
                    pageSize=10,
                    fields="files(id,name,mimeType)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            n = len(children.get("files", []))
            print(f"OK: Listed {n} direct child item(s) in folder (max 10 shown).")
        except Exception as e:
            print(f"FAILED: list children: {e}")
            sys.exit(5)

    print("\nConnectivity test finished successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
