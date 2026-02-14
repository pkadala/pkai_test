"""
MCP client that connects to the workspace-mcp PyPI server (stdio or streamable-http)
to create files in Google Drive and tasks in Google Tasks. Requires GOOGLE_OAUTH_CLIENT_ID
and GOOGLE_OAUTH_CLIENT_SECRET; OAuth runs on first use of workspace-mcp.
Transport: WORKSPACE_MCP_TRANSPORT=stdio (default) or streamable-http with WORKSPACE_MCP_HTTP_URL.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import sys

from langchain_core.tools import tool

# Run async MCP client in a thread so asyncio.run() works when called from FastAPI (which already has a running event loop).
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mcp_client")


def _run_async(coro):
    """Run a coroutine in a dedicated thread; safe when called from an async context (e.g. FastAPI)."""
    def _run():
        return asyncio.run(coro)
    return _executor.submit(_run).result()


def _user_google_email() -> str | None:
    """Email for workspace-mcp tools that require user_google_email (e.g. list_task_lists). From .env or env."""
    from app import env as env_loader
    email = env_loader.user_google_email()
    return email.strip() if email else None


def _get_workspace_mcp_command_and_args() -> tuple[str, list[str]]:
    """Return (command, args) to run workspace-mcp with Drive and Tasks tools."""
    command = os.environ.get("WORKSPACE_MCP_COMMAND")
    if command:
        args_str = os.environ.get("WORKSPACE_MCP_ARGS", "--tools drive tasks")
        args = [a.strip() for a in args_str.split() if a.strip()]
        return command, args
    import shutil
    script = "workspace-mcp.exe" if sys.platform == "win32" else "workspace-mcp"
    if shutil.which(script):
        return script, ["--tools", "drive", "tasks"]
    return sys.executable, ["-m", "workspace_mcp", "--tools", "drive", "tasks"]


def _parse_tool_result(content: list) -> str:
    """Extract text from MCP CallToolResult content."""
    if not content:
        return ""
    for part in content:
        if isinstance(part, dict):
            if part.get("type") == "text":
                return part.get("text", "") or ""
        elif hasattr(part, "type") and getattr(part, "type") == "text":
            return getattr(part, "text", "") or ""
    return ""


async def _call_tool(session, name: str, args: dict) -> str:
    """Call MCP tool and return text content."""
    try:
        result = await session.call_tool(name, args)
        content = result.content if hasattr(result, "content") else []
        return _parse_tool_result(content)
    except Exception as e:
        return f"Error: {e}"


def _workspace_mcp_env() -> dict:
    """Env for workspace-mcp subprocess: OAuth port + credentials from .env so the subprocess sees them."""
    from app import env as env_loader
    env = os.environ.copy()
    env["WORKSPACE_MCP_PORT"] = str(env_loader.workspace_mcp_oauth_port())
    env["WORKSPACE_MCP_BASE_URI"] = env_loader.workspace_mcp_base_uri()
    env["GOOGLE_OAUTH_REDIRECT_URI"] = env_loader.workspace_mcp_oauth_redirect_uri()
    if env_loader.google_oauth_client_id():
        env["GOOGLE_OAUTH_CLIENT_ID"] = env_loader.google_oauth_client_id()
    if env_loader.google_oauth_client_secret():
        env["GOOGLE_OAUTH_CLIENT_SECRET"] = env_loader.google_oauth_client_secret()
    if env_loader.user_google_email():
        env["USER_GOOGLE_EMAIL"] = env_loader.user_google_email()
    return env


async def _with_session(coro):
    """Run an async coroutine that takes (session) and returns a value."""
    from app import env as env_loader
    from mcp import ClientSession

    transport = env_loader.workspace_mcp_transport()
    if transport == "streamable-http":
        url = env_loader.workspace_mcp_http_url()
        if not url:
            raise ValueError(
                "WORKSPACE_MCP_HTTP_URL is required when WORKSPACE_MCP_TRANSPORT=streamable-http. "
                "Start the server with e.g. uvx workspace-mcp --transport streamable-http"
            )
        from mcp.client.streamable_http import streamable_http_client
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await coro(session)
    else:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        command, args = _get_workspace_mcp_command_and_args()
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=_workspace_mcp_env(),
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await coro(session)


async def _ensure_workspace_mcp_oauth_async() -> str:
    """
    Keep one workspace-mcp session open, trigger OAuth if needed, and wait until tokens work.
    Call this once (e.g. from scripts/auth_workspace_mcp.py) so the process stays up to receive
    the redirect at localhost:8765. Returns a status message.
    """

    async def run(session):
        user_email = _user_google_email()
        list_args = {"max_results": 5}
        if user_email:
            list_args["user_google_email"] = user_email
        raw = await _call_tool(session, "list_task_lists", list_args)
        if raw.strip().startswith("[") or raw.strip().startswith("{"):
            try:
                data = json.loads(raw)
                items = data if isinstance(data, list) else data.get("items", data.get("task_lists", data.get("taskLists", [])))
                if items:
                    return "OK: workspace-mcp already has valid tokens. Task lists found."
            except (json.JSONDecodeError, KeyError):
                pass
        # Likely needs OAuth or error - keep this process/session alive so callback can hit localhost:8765
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            lambda: input(
                "\n>>> A browser may have opened for Google sign-in. Complete the sign-in; "
                "when you see the redirect (or 'This site can't be reached' after success), "
                "come back here and press Enter to retry... "
            ),
        )
        raw2 = await _call_tool(session, "list_task_lists", list_args)
        if raw2.strip().startswith("[") or raw2.strip().startswith("{"):
            return "OK: OAuth completed. workspace-mcp has saved tokens. You can close this and use the app."
        return f"Retry result: {raw2[:400]}"

    return await _with_session(run)


async def _list_task_lists_async(max_results: int = 20) -> str:
    """List the user's Google Task lists via workspace-mcp list_task_lists tool."""
    async def run(session):
        user_email = _user_google_email()
        list_args = {"max_results": max_results}
        if user_email:
            list_args["user_google_email"] = user_email
        raw = await _call_tool(session, "list_task_lists", list_args)
        if not raw.strip().startswith("[") and not raw.strip().startswith("{"):
            if "user_google_email" in raw.lower() or "missing" in raw.lower():
                return (
                    "Error: Set USER_GOOGLE_EMAIL in .env to your Google account email for list_task_lists."
                )
            return raw
        try:
            data = json.loads(raw)
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items", data.get("task_lists", data.get("taskLists", [])))
            if not items:
                return "No task lists found. Create a task list in Google Tasks first."
            lines = []
            for i, t in enumerate(items, 1):
                tid = t.get("id") or t.get("task_list_id") or "?"
                title = t.get("title") or t.get("name") or "Untitled"
                lines.append(f"{i}. {title} (id: {tid})")
            return "\n".join(lines)
        except (json.JSONDecodeError, KeyError):
            return raw
    return await _with_session(run)


async def _create_file_in_drive_async(
    name: str,
    content: str,
    folder_id: str | None = None,
    mime_type: str = "text/plain",
) -> str:
    """Create a file in Google Drive via workspace-mcp create_drive_file tool."""

    async def run(session):
        user_email = _user_google_email()
        args = {"file_name": name, "content": content, "mime_type": mime_type}
        if user_email:
            args["user_google_email"] = user_email
        if folder_id:
            args["folder_id"] = folder_id
        return await _call_tool(session, "create_drive_file", args)

    return await _with_session(run)


async def _create_google_task_async(
    title: str,
    task_list_id: str | None = None,
    notes: str | None = None,
    due: str | None = None,
) -> str:
    """Create a task in Google Tasks via workspace-mcp create_task tool. Uses first task list if task_list_id not given."""

    async def run(session):
        tid = task_list_id
        user_email = _user_google_email()
        if not tid:
            list_args = {"max_results": 10}
            if user_email:
                list_args["user_google_email"] = user_email
            raw = await _call_tool(session, "list_task_lists", list_args)
            if not raw.strip().startswith("[") and not raw.strip().startswith("{"):
                if "user_google_email" in raw.lower() or "missing" in raw.lower():
                    return (
                        "Error: workspace-mcp requires user_google_email for list_task_lists. "
                        "Set USER_GOOGLE_EMAIL (or GOOGLE_EMAIL) in .env to your Google account email, or pass task_list_id to create_google_task."
                    )
                # workspace-mcp may return human-readable text like "Task Lists for ... - My Tasks (ID: xxx)"
                match = re.search(r"\(ID:\s*([^)]+)\)|ID:\s*([^\s\n]+)", raw, re.IGNORECASE)
                if match:
                    tid = (match.group(1) or match.group(2) or "").strip()
                if not tid:
                    return f"Error: Could not get task list. Response: {raw[:300]}"
            else:
                try:
                    data = json.loads(raw)
                    if isinstance(data, list) and data:
                        tid = data[0].get("id") or data[0].get("task_list_id")
                    elif isinstance(data, dict):
                        items = data.get("items", data.get("task_lists", data.get("taskLists", [])))
                        if items:
                            tid = items[0].get("id") or items[0].get("task_list_id")
                    if not tid:
                        return "Error: No task list found. Create a task list in Google Tasks first or pass task_list_id."
                except (json.JSONDecodeError, KeyError, IndexError):
                    match = re.search(r"\(ID:\s*([^)]+)\)|ID:\s*([^\s\n]+)", raw, re.IGNORECASE)
                    if match:
                        tid = (match.group(1) or match.group(2) or "").strip()
                    if not tid:
                        return f"Error: Could not get task list. Response: {raw[:200]}"
        args = {"task_list_id": tid, "title": title}
        if user_email:
            args["user_google_email"] = user_email
        if notes:
            args["notes"] = notes
        if due:
            args["due"] = due
        return await _call_tool(session, "create_task", args)

    return await _with_session(run)


@tool
def list_google_task_lists(max_results: int = 20) -> str:
    """
    List the user's Google Task lists. Optional: max_results (default 20).
    Requires workspace-mcp OAuth (GOOGLE_OAUTH_CLIENT_ID/SECRET) and USER_GOOGLE_EMAIL in .env.
    """
    coro = _list_task_lists_async(max_results=max_results)
    return _run_async(coro)


@tool
def create_file_in_drive(
    name: str,
    content: str,
    folder_id: str | None = None,
    mime_type: str = "text/plain",
) -> str:
    """
    Create a file in the user's Google Drive with the given name and content.
    Optional: folder_id (Drive folder ID), mime_type (default text/plain).
    Requires workspace-mcp OAuth (GOOGLE_OAUTH_CLIENT_ID/SECRET).
    """
    coro = _create_file_in_drive_async(name, content, folder_id, mime_type)
    return _run_async(coro)


@tool
def create_google_task(
    title: str,
    task_list_id: str | None = None,
    notes: str | None = None,
    due: str | None = None,
) -> str:
    """
    Create a task in the user's Google Tasks. Optional: task_list_id (uses first list if omitted), notes, due (RFC 3339).
    Requires workspace-mcp OAuth (GOOGLE_OAUTH_CLIENT_ID/SECRET).
    """
    coro = _create_google_task_async(title, task_list_id, notes, due)
    return _run_async(coro)
