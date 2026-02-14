"""LangChain agent: orchestrator with RAG and explicit tool invocation."""
from __future__ import annotations

import logging

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from app.llm_factory import get_llm
from app.tools.rag_tool import search_knowledge_base
from app.tools.external_tool import fetch_external_updates
from app.mcp_client import create_file_in_drive, create_google_task, list_google_task_lists
from app.schemas import ChatResponse, SuggestedAction

SYSTEM_PROMPT = """You are the Personal Knowledge AI Assistant (PKAI). You help the user reason over their personal knowledge.

- Use the search_knowledge_base tool when the user's question is about their own documents, notes, or stored information.
- Use fetch_external_updates only when the user explicitly asks for external or recent information.
- To save a note or document for the user, use create_file_in_drive (creates a file in their Google Drive).
- To list the user's task lists, use list_google_task_lists.
- To create a task for the user, use create_google_task (creates a task in their Google Tasks). These execute immediately; report what was done.

Be concise and grounded. When you use retrieved knowledge, say so briefly. If a tool returns an error (e.g. starts with 'Error:' or 'Tool error:'), always quote that exact error message in your reply so the user knows what went wrong."""

TOOLS = [search_knowledge_base, fetch_external_updates, create_file_in_drive, list_google_task_lists, create_google_task]
TOOL_MAP = {t.name: t for t in TOOLS}


def _run_tool(name: str, args: dict) -> str:
    """Invoke a tool by name and return its string result."""
    tool = TOOL_MAP.get(name)
    if not tool:
        return f"Unknown tool: {name}"
    try:
        result = tool.invoke(args)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"Tool error: {e}"


def run_agent(query: str, chat_history: list | None = None) -> ChatResponse:
    """
    Run the agent on a user query using tool-calling loop.
    Returns a structured response with explainability.
    """
    llm = get_llm().bind_tools(TOOLS)
    messages: list = [
        SystemMessage(content=SYSTEM_PROMPT),
    ]
    if chat_history:
        for msg in chat_history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=query))

    tools_invoked: list[str] = []
    suggested_actions: list[SuggestedAction] = []
    max_turns = 10

    output = "No response."
    for _ in range(max_turns):
        response = llm.invoke(messages)
        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            output = response.content if isinstance(getattr(response, "content", None), str) else str(getattr(response, "content", "") or "")
            break

        for tc in tool_calls:
            # Handle both dict and object with name/args/id
            if isinstance(tc, dict):
                tool_name = tc.get("name", "")
                args = tc.get("args") or {}
                tool_id = tc.get("id", "unknown")
            else:
                tool_name = getattr(tc, "name", "") or ""
                args = getattr(tc, "args", None) or {}
                tool_id = getattr(tc, "id", "unknown")
            if not tool_name:
                continue
            tools_invoked.append(tool_name)
            result = _run_tool(tool_name, args)
            if result.strip().lower().startswith("error") or "tool error" in result.lower():
                logging.warning("Tool %s returned error: %s", tool_name, result[:500])
            messages.append(ToolMessage(content=result, tool_call_id=tool_id))


    used_knowledge = "search_knowledge_base" in tools_invoked

    return ChatResponse(
        response=output,
        used_knowledge=used_knowledge,
        tools_invoked=tools_invoked,
        suggested_actions=suggested_actions,
    )
