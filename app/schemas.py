"""Pydantic models for API and agent I/O."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from the UI."""

    message: str = Field(..., min_length=1, description="User query")
    session_id: str | None = Field(None, description="Optional session id for continuity")


class ChatResponse(BaseModel):
    """Response from the agent with explainability fields."""

    response: str = Field(..., description="Agent reply text")
    used_knowledge: bool = Field(False, description="Whether personal knowledge was retrieved")
    tools_invoked: list[str] = Field(default_factory=list, description="Names of tools invoked")
    suggested_actions: list[SuggestedAction] = Field(
        default_factory=list,
        description="State-changing actions requiring user confirmation",
    )


class SuggestedAction(BaseModel):
    """A state-changing action proposed by the agent; requires user confirmation."""

    tool_name: str
    description: str
    params: dict = Field(default_factory=dict)


class IngestRequest(BaseModel):
    """Ingestion request: source and optional parameters."""

    source: str = Field(default="local", description="local | gdrive_oauth")
    local_path: str | None = Field(None, description="Local folder path for documents (local); default is project documents/")
    folder_id: str | None = Field(None, description="Google Drive folder name or ID (gdrive_oauth); blank = entire Drive")


class IngestResponse(BaseModel):
    """Result of document ingestion."""

    ok: bool
    message: str
    chunks_created: int = 0
