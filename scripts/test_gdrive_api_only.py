#!/usr/bin/env python3
"""Minimal Google Drive API connectivity test (no LangChain). Run from project root.

Auth order (same as ingestion/gdrive_sdk):
  1) GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64
  2) GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON
  3) GOOGLE_DRIVE_CREDENTIALS_PATH (file under project root)

Quick local test for B64 (matches Railway):

  export GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64="$(base64 < secrets/your-key.json | tr -d '\n')"
  env -u GOOGLE_DRIVE_CREDENTIALS_PATH python scripts/test_gdrive_api_only.py
"""
from __future__ import annotations

import base64
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


def load_sa_meta_and_creds():
    """Return (meta dict, google.oauth2.service_account.Credentials)."""
    from google.oauth2 import service_account

    b64 = (os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64") or "").strip()
    raw_json = (os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON") or "").strip()
    if b64:
        try:
            raw_json = base64.standard_b64decode(b64).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            print(f"ERROR: GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64 is not valid base64/UTF-8: {e}")
            sys.exit(1)
    if raw_json:
        if (raw_json.startswith('"') and raw_json.endswith('"')) or (
            raw_json.startswith("'") and raw_json.endswith("'")
        ):
            raw_json = raw_json[1:-1]
        try:
            meta = json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON env is not valid JSON: {e}")
            sys.exit(1)
        pk = meta.get("private_key")
        if isinstance(pk, str) and "\\n" in pk and pk.count("\n") < 2:
            meta = dict(meta)
            meta["private_key"] = pk.replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(meta, scopes=SCOPES)
        return meta, creds

    key_path = resolve_key_path()
    if not key_path:
        print(
            "ERROR: Set one of:\n"
            "  GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64 (base64 of the whole JSON file), or\n"
            "  GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON (raw JSON string), or\n"
            "  GOOGLE_DRIVE_CREDENTIALS_PATH=secrets/your-key.json in .env"
        )
        sys.exit(1)

    with open(key_path) as f:
        meta = json.load(f)
    creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
    return meta, creds


def main() -> None:
    from googleapiclient.discovery import build

    meta, creds = load_sa_meta_and_creds()
    email = meta.get("client_email", "?")
    key_id = meta.get("private_key_id", "?")
    src = "env (B64 or JSON)" if os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64") or os.environ.get(
        "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"
    ) else resolve_key_path()
    print(f"Key source: {src}")
    print(f"Service account: {email}")
    print(f"private_key_id (metadata only): {key_id[:8]}...")
    print()

    try:
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
