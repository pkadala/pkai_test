"""Ingestion sources: local, Google Drive SDK, Google Drive OAuth, Google Workspace MCP."""
from __future__ import annotations

from langchain_core.documents import Document

from ingestion.sources.local import load_documents_local
from ingestion.sources.gdrive_sdk import load_documents_gdrive_sdk
from ingestion.sources.gdrive_oauth import load_documents_gdrive_oauth
from ingestion.sources.workspace_mcp import load_documents_workspace_mcp

IngestSourceKind = str  # "local" | "gdrive_sdk" | "gdrive_oauth" | "workspace_mcp"


def load_documents_from_source(
    source: IngestSourceKind,
    *,
    local_path: str | None = None,
    folder_id: str | None = None,
    gdrive_credentials_path: str | None = None,
    workspace_mcp_path: str | None = None,
) -> list[Document]:
    """
    Load documents from the given source.
    - local: uses local_path or default documents/ directory
    - gdrive_sdk: Google Drive API with service account (folder_id optional)
    - gdrive_oauth: Google Drive with user OAuth (folder_id optional; connect first via Ingest page)
    - workspace_mcp: workspace-mcp PyPI package (stdio); no path needed
    """
    if source == "local":
        return load_documents_local(directory=local_path)
    if source == "gdrive_sdk":
        return load_documents_gdrive_sdk(
            folder_id=folder_id,
            credentials_path=gdrive_credentials_path,
        )
    if source == "gdrive_oauth":
        return load_documents_gdrive_oauth(folder_id=folder_id)
    if source == "workspace_mcp":
        return load_documents_workspace_mcp(workspace_path=workspace_mcp_path)
    raise ValueError(f"Unknown ingestion source: {source}")
