"""Ingestion via the workspace-mcp PyPI package (Python Google Workspace MCP).

Uses the MCP server's tools in stdio mode. No clone or build; install with pip install workspace-mcp.
Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET; OAuth runs on first use.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from langchain_core.documents import Document


def _parse_tool_result(content: list) -> str:
    """Extract text from MCP CallToolResult content (list of TextContent)."""
    if not content:
        return ""
    for part in content:
        if isinstance(part, dict):
            if part.get("type") == "text":
                return part.get("text", "") or ""
        elif hasattr(part, "type") and getattr(part, "type") == "text":
            return getattr(part, "text", "") or ""
    return ""


def _parse_list_result(raw: str) -> list[dict]:
    """Parse list/search tool response into list of items with id/name."""
    try:
        if isinstance(raw, str) and (raw.startswith("[") or raw.startswith("{")):
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "files" in data:
                return data["files"]
            if isinstance(data, dict) and "documents" in data:
                return data["documents"]
            if isinstance(data, dict) and "spreadsheets" in data:
                return data["spreadsheets"]
            if isinstance(data, dict) and "items" in data:
                return data["items"]
            return [data] if data else []
    except json.JSONDecodeError:
        pass
    return []


async def _call_tool_text(session, name: str, args: dict) -> str:
    """Call MCP tool and return text content."""
    try:
        result = await session.call_tool(name, args)
        content = result.content if hasattr(result, "content") else []
        return _parse_tool_result(content)
    except Exception:
        return ""


def _get_workspace_mcp_command_and_args() -> tuple[str, list[str]]:
    """Return (command, args) to run the workspace-mcp PyPI package in stdio mode."""
    command = os.environ.get("WORKSPACE_MCP_COMMAND")
    if command:
        args_str = os.environ.get("WORKSPACE_MCP_ARGS", "--tools drive docs sheets slides")
        args = [a.strip() for a in args_str.split() if a.strip()]
        return command, args
    # Prefer console script if on PATH (e.g. after pip install workspace-mcp)
    import shutil
    script = "workspace-mcp.exe" if sys.platform == "win32" else "workspace-mcp"
    if shutil.which(script):
        return script, ["--tools", "drive", "docs", "sheets", "slides"]
    # Fall back to current Python -m workspace_mcp
    return sys.executable, ["-m", "workspace_mcp", "--tools", "drive", "docs", "sheets", "slides"]


async def _ingest_via_workspace_mcp_async(max_per_type: int = 20) -> list[Document]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command, args = _get_workspace_mcp_command_and_args()
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=os.environ.copy(),
    )
    docs: list[Document] = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Docs: search_docs then get_doc_content (workspace-mcp PyPI tool names)
            try:
                raw = await _call_tool_text(session, "search_docs", {"query": "", "page_size": max_per_type})
                for item in _parse_list_result(raw):
                    doc_id = item.get("id") or item.get("document_id") or item.get("doc_id")
                    name = item.get("name", "doc")
                    if not doc_id:
                        continue
                    try:
                        text = await _call_tool_text(session, "get_doc_content", {"document_id": doc_id})
                        if text:
                            docs.append(
                                Document(
                                    page_content=text,
                                    metadata={"source": f"workspace://{name}", "file_id": doc_id, "ingest_source": "workspace_mcp"},
                                )
                            )
                    except Exception:
                        continue
            except Exception:
                pass

            # Sheets: list_spreadsheets then read_sheet_values (Extended tier)
            try:
                raw = await _call_tool_text(session, "list_spreadsheets", {})
                for item in _parse_list_result(raw):
                    sheet_id = item.get("id") or item.get("spreadsheet_id") or item.get("spreadsheetId")
                    name = item.get("name", "sheet")
                    if not sheet_id:
                        continue
                    try:
                        text = await _call_tool_text(
                            session,
                            "read_sheet_values",
                            {"spreadsheet_id": sheet_id, "range": "Sheet1"},
                        )
                        if text:
                            docs.append(
                                Document(
                                    page_content=text,
                                    metadata={"source": f"workspace://{name}", "file_id": sheet_id, "ingest_source": "workspace_mcp"},
                                )
                            )
                    except Exception:
                        continue
            except Exception:
                pass

            # Drive: search_drive_files then get_drive_file_content
            try:
                raw = await _call_tool_text(
                    session,
                    "search_drive_files",
                    {"query": "", "page_size": max_per_type},
                )
                for item in _parse_list_result(raw):
                    fid = item.get("id") or item.get("file_id")
                    name = item.get("name", "file")
                    if not fid:
                        continue
                    try:
                        text = await _call_tool_text(session, "get_drive_file_content", {"file_id": fid})
                        if text:
                            docs.append(
                                Document(
                                    page_content=text,
                                    metadata={"source": f"workspace://{name}", "file_id": fid, "ingest_source": "workspace_mcp"},
                                )
                            )
                    except Exception:
                        continue
            except Exception:
                pass
    return docs


def load_documents_workspace_mcp(workspace_path: str | None = None) -> list[Document]:
    """
    Load documents from Google Workspace using the workspace-mcp PyPI package (stdio).

    No path or clone needed. Install with: pip install workspace-mcp
    Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET; OAuth runs on first use.
    Optional: WORKSPACE_MCP_COMMAND, WORKSPACE_MCP_ARGS to override how the server is run.
    """
    # workspace_path kept for API compatibility but ignored (PyPI package needs no path)
    return asyncio.run(_ingest_via_workspace_mcp_async())
