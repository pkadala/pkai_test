#!/usr/bin/env python3
"""
One-time OAuth for workspace-mcp (Drive/Tasks tools).

workspace-mcp must receive the Google redirect at http://localhost:8765. When the app
calls a tool it spawns workspace-mcp briefly, so the process often exits before you
finish signing in and the redirect hits nothing (ERR_CONNECTION_REFUSED).

Run this script once: it keeps one workspace-mcp process running, triggers the
OAuth flow, and waits for you to complete sign-in in the browser. After that,
workspace-mcp has saved tokens and the app will work without this step.

  From project root:
    python scripts/auth_workspace_mcp.py
  or:
    .venv/bin/python scripts/auth_workspace_mcp.py

Ensure .env has GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, USER_GOOGLE_EMAIL,
and WORKSPACE_MCP_OAUTH_PORT=8765. Add http://localhost:8765 to your OAuth client's
redirect URIs in Google Cloud Console.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

# Load .env via app.env
import app.env  # noqa: F401

from app.mcp_client import _run_async, _ensure_workspace_mcp_oauth_async


def main() -> None:
    print("Starting workspace-mcp OAuth bootstrap (one session, stays open for redirect)...")
    print("If a browser opens, sign in with Google. Redirect will hit this process on port 8765.\n")
    try:
        result = _run_async(_ensure_workspace_mcp_oauth_async())
        print(result)
    except KeyboardInterrupt:
        print("\nInterrupted. Run again when ready to complete OAuth.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
