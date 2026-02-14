"""Load configuration from .env only. No hardcoded values; set all in .env."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

# Load .env from project root (parent of app/) so it works when running from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.is_file():
    from dotenv import load_dotenv
    load_dotenv(_env_path, override=False)


def _get(key: str) -> str:
    return os.environ.get(key, "").strip()


def _get_from_env_file(key: str) -> str:
    """Read key from .env file (load/reload .env then return value)."""
    if _env_path.is_file():
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
    return os.environ.get(key, "").strip()


def env() -> str:
    """ENV: local or railway."""
    return _get("ENV").lower()


def llm_provider() -> str:
    """LLM_PROVIDER: openai or gemini."""
    return _get("LLM_PROVIDER").lower()


def is_local() -> bool:
    return env() == "local"


def is_railway() -> bool:
    return env() == "railway"


def get_openai_key() -> str:
    key = _get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
    return key


def get_google_key() -> str:
    key = _get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
    return key


def openai_api_key() -> str | None:
    v = _get("OPENAI_API_KEY")
    return v or None


def openai_model() -> str:
    return _get("OPENAI_MODEL")


def google_api_key() -> str | None:
    v = _get("GOOGLE_API_KEY")
    return v or None


def gemini_model() -> str:
    return _get("GEMINI_MODEL")


def openai_embedding_model() -> str:
    return _get("OPENAI_EMBEDDING_MODEL")


def gemini_embedding_model() -> str:
    return _get("GEMINI_EMBEDDING_MODEL")


def database_url() -> str | None:
    v = _get("DATABASE_URL")
    return v or None


def google_drive_credentials_path() -> str | None:
    v = _get("GOOGLE_DRIVE_CREDENTIALS_PATH")
    return v or None


def google_oauth_client_id() -> str | None:
    v = _get("GOOGLE_OAUTH_CLIENT_ID")
    return v or None


def google_oauth_client_secret() -> str | None:
    v = _get("GOOGLE_OAUTH_CLIENT_SECRET")
    return v or None


def google_oauth_redirect_uri() -> str:
    return _get("GOOGLE_OAUTH_REDIRECT_URI")


def user_google_email() -> str | None:
    v = _get("USER_GOOGLE_EMAIL") or _get("GOOGLE_EMAIL")
    return v or None


def workspace_mcp_oauth_redirect_uri() -> str:
    """Full OAuth redirect URI for workspace-mcp (e.g. http://localhost:8765/oauth2callback)."""
    return _get("WORKSPACE_MCP_OAUTH_REDIRECT_URI")


def _parse_workspace_mcp_redirect_uri() -> tuple[str, int]:
    """Parse WORKSPACE_MCP_OAUTH_REDIRECT_URI into (base_uri, port)."""
    uri = workspace_mcp_oauth_redirect_uri()
    if not uri:
        return "", 0
    try:
        p = urlparse(uri)
        if not p.scheme or not p.netloc:
            return "", 0
        port = p.port
        if port is None:
            port = 443 if p.scheme == "https" else 80
        base = f"{p.scheme}://{p.netloc}"
        return base, port
    except Exception:
        return "", 0


def workspace_mcp_base_uri() -> str:
    """Base URI for workspace-mcp (scheme + host + port), derived from WORKSPACE_MCP_OAUTH_REDIRECT_URI."""
    base, _ = _parse_workspace_mcp_redirect_uri()
    return base


def workspace_mcp_oauth_port() -> int:
    """Port for workspace-mcp OAuth server, derived from WORKSPACE_MCP_OAUTH_REDIRECT_URI."""
    _, port = _parse_workspace_mcp_redirect_uri()
    return port


def workspace_mcp_transport() -> str:
    """WORKSPACE_MCP_TRANSPORT: stdio (default) or streamable-http. Always read from .env."""
    return _get_from_env_file("WORKSPACE_MCP_TRANSPORT").lower() or "stdio"


def workspace_mcp_http_url() -> str:
    """WORKSPACE_MCP_HTTP_URL: MCP endpoint when transport is streamable-http. Always read from .env."""
    return _get_from_env_file("WORKSPACE_MCP_HTTP_URL").strip()
