#!/usr/bin/env python3
"""Test Google Drive connectivity with the service account and list files in a folder."""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root so we can import app and ingestion
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

FOLDER_ID = "1Dr48ha9e5aBbgnGLuhmwhLNhGHT89Ih6"


def main() -> None:
    import json
    from app import env as env_loader
    from ingestion.sources.gdrive_sdk import _get_drive_service, _resolve_credentials_path

    creds_path = env_loader.google_drive_credentials_path() or _resolve_credentials_path(None)
    if not creds_path:
        print("ERROR: No credentials. Set GOOGLE_DRIVE_CREDENTIALS_PATH in .env")
        sys.exit(1)

    # Resolve path for reading JSON (same logic as gdrive_sdk)
    resolved = _resolve_credentials_path(creds_path)
    if resolved and Path(resolved).is_file():
        with open(resolved) as f:
            sa = json.load(f)
            client_email = sa.get("client_email", "")
            print(f"Service account: {client_email}")
            print("(Share the folder with this email as Viewer if you see no files.)")
    print(f"Using credentials: {creds_path}")
    print(f"Listing files in folder ID: {FOLDER_ID}\n")

    service = _get_drive_service(credentials_path=env_loader.google_drive_credentials_path())

    # Check if we can see the folder at all
    try:
        folder = service.files().get(fileId=FOLDER_ID, fields="id, name, mimeType", supportsAllDrives=True).execute()
        print(f"Folder: {folder.get('name', '?')} (mime: {folder.get('mimeType', '?')})\n")
    except Exception as e:
        print(f"Cannot access folder: {e}")
        print("Share the folder with the service account email above (Viewer access).")
        return

    # List children (include Shared Drive items)
    results = (
        service.files()
        .list(
            q=f"'{FOLDER_ID}' in parents and trashed = false",
            pageSize=100,
            fields="files(id, name, mimeType, size, modifiedTime)",
            orderBy="name",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = results.get("files", [])
    if not files:
        print("(No files listed in this folder. Share the folder with the service account email above.)")
        return
    for f in files:
        name = f.get("name", "")
        mime = f.get("mimeType", "")
        size = f.get("size")
        modified = f.get("modifiedTime", "")
        size_str = f" {size} bytes" if size else ""
        print(f"  {name}  [{mime}]{size_str}  modified: {modified}")
    print(f"\nTotal: {len(files)} item(s)")


if __name__ == "__main__":
    main()
