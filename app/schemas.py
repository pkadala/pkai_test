"""Pydantic models for API and agent I/O."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from the UI."""

    message: str = Field(..., min_length=1, description="User query")
    session_id: str | None = Field(None, description="Optional session id for continuity")


class ToolInvocationRecord(BaseModel):
    """One tool call with inputs and output (explainability)."""

    tool_name: str
    tool_input: dict = Field(default_factory=dict)
    tool_output: str = ""


class ChatResponse(BaseModel):
    """Response from the agent with explainability fields."""

    response: str = Field(..., description="Agent reply text")
    used_knowledge: bool = Field(False, description="Whether personal knowledge was retrieved")
    tools_invoked: list[str] = Field(default_factory=list, description="Tool names invoked")
    tool_records: list[ToolInvocationRecord] = Field(
        default_factory=list,
        description="Detailed tool invocations",
    )
    reasoning_steps: list[dict] = Field(
        default_factory=list,
        description="Thought and tool steps for processing flow UI",
    )
    action_proposed: bool = Field(
        False,
        description="Whether a state-changing external action ran (Drive / Tasks tools)",
    )
    suggested_actions: list["SuggestedAction"] = Field(
        default_factory=list,
        description="State-changing actions requiring user confirmation",
    )


class SuggestedAction(BaseModel):
    """A state-changing action proposed by the agent; requires user confirmation."""

    tool_name: str
    description: str
    params: dict = Field(default_factory=dict)


class QueryRequest(BaseModel):
    """JSON API query (matches pkai-style /api/query)."""

    query: str = Field(..., min_length=1, description="The user's question or request")
    thread_id: str | None = Field(
        default=None,
        description="Conversation thread ID (optional; reserved for future use).",
    )


class ToolInvocation(BaseModel):
    """Record of a tool invocation for JSON API explainability."""

    tool_name: str
    tool_input: dict = Field(default_factory=dict)
    tool_output: str = ""


class AgentResponse(BaseModel):
    """Structured agent response for /api/query."""

    response: str = Field(..., description="The agent's synthesized response")
    knowledge_used: bool = Field(
        default=False,
        description="Whether personal knowledge base was retrieved",
    )
    tools_invoked: list[ToolInvocation] = Field(
        default_factory=list,
        description="List of tools invoked during reasoning",
    )
    action_proposed: bool = Field(
        default=False,
        description="Whether external state-changing tools were used",
    )


class IngestRequest(BaseModel):
    """Ingestion request: source and optional parameters."""

    source: str = Field(default="local", description="local | gdrive_sdk | gdrive_oauth | workspace_mcp")
    local_path: str | None = Field(None, description="Local folder path (local)")
    folder_id: str | None = Field(None, description="Drive folder name or ID (gdrive_* sources)")
    document_ids: str | None = Field(None, description="Comma-separated file IDs (optional)")
    recursive: bool = Field(True, description="Include subfolders for Google Drive SDK ingest (default on)")
    gdrive_credentials_path: str | None = Field(
        None,
        description="Override path to service account JSON (gdrive_sdk)",
    )


class IngestResponse(BaseModel):
    """Result of document ingestion."""

    ok: bool
    message: str
    chunks_created: int = 0
