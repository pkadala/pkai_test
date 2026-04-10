"""LangChain agent: orchestrator with RAG and explicit tool invocation."""
from __future__ import annotations

import json
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
from app.schemas import ChatResponse, ToolInvocationRecord

SYSTEM_PROMPT = """You are the Personal Knowledge AI Assistant (PKAI). You help the user reason over their personal knowledge.

- Use the search_knowledge_base tool when the user's question is about their own documents, notes, or stored information. When they ask to "list all the X" or "find the X", infer the search query from X (e.g. for "list all the DIDs" use query "DID" or "DID document"; for "list my notes on Y" use "Y"). Do not ask the user to specify the query unless the topic is truly ambiguous.
- If search_knowledge_base returns no relevant documents (or the knowledge base is empty), say so briefly, then you may answer from general knowledge when that helps the user (e.g. definitions, history, how-tos). Clearly separate the two: first state nothing matched their stored documents, then give the general answer so they know what came from where.
- Use fetch_external_updates only when the user explicitly asks for external or recent information.
- To save a note or document for the user, use create_file_in_drive (creates a file in their Google Drive). When the user did not specify a file name, choose a sensible default from the content (e.g. dids.txt for a list of DIDs, notes.txt for notes). Do not ask the user for a file name unless they explicitly asked to choose one.
- To list the user's task lists, use list_google_task_lists.
- To create a task for the user, use create_google_task (creates a task in their Google Tasks). These execute immediately; report what was done.

Be concise and grounded. Prefer completing multi-step requests (search, save, create task) in one go using sensible defaults rather than asking for confirmation or choices the user did not request. When you use retrieved knowledge, say so briefly. If a tool returns an error (e.g. starts with 'Error:' or 'Tool error:'), always quote that exact error message in your reply so the user knows what went wrong."""

TOOLS = [search_knowledge_base, fetch_external_updates, create_file_in_drive, list_google_task_lists, create_google_task]
TOOL_MAP = {t.name: t for t in TOOLS}

_ACTION_TOOLS = frozenset({"create_file_in_drive", "create_google_task"})


def _format_tool_error(e: BaseException, max_length: int = 1500) -> str:
    """Unwrap exception chain (TaskGroup, ExceptionGroup, __cause__) and return a detailed message."""
    parts: list[str] = []
    seen: set[int] = set()

    def add(exc: BaseException | None) -> None:
        if exc is None or id(exc) in seen:
            return
        seen.add(id(exc))
        if hasattr(exc, "exceptions"):
            for sub in getattr(exc, "exceptions", ()):
                add(sub)
            return
        msg = f"{type(exc).__name__}: {exc}"
        if msg.strip():
            parts.append(msg)
        add(getattr(exc, "__cause__", None))
        add(getattr(exc, "__context__", None))

    add(e)
    if not parts:
        parts.append(f"{type(e).__name__}: {e}")
    detail = " | ".join(parts)
    if len(detail) > max_length:
        detail = detail[: max_length - 3] + "..."
    return detail


def _run_tool(name: str, args: dict) -> str:
    """Invoke a tool by name and return its string result."""
    tool = TOOL_MAP.get(name)
    if not tool:
        return f"Unknown tool: {name}"
    try:
        result = tool.invoke(args)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        detail = _format_tool_error(e)
        logging.exception("Tool %s failed: %s", name, detail)
        return f"Tool error: {detail}"


def _extract_content(response) -> str:
    c = getattr(response, "content", None)
    if isinstance(c, str):
        return c
    return str(c or "")


def run_agent(query: str, chat_history: list | None = None) -> ChatResponse:
    """
    Run the agent on a user query using tool-calling loop.
    Returns a structured response with explainability (pkai-style UI).
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
    tool_records: list[ToolInvocationRecord] = []
    reasoning_steps: list[dict] = []
    max_turns = 10

    output = "No response."
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = _extract_content(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        messages.append(response)

        if not tool_calls:
            output = content.strip() or output
            break

        if content.strip():
            reasoning_steps.append({"type": "thought", "content": content.strip()})

        for tc in tool_calls:
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
            tool_records.append(
                ToolInvocationRecord(tool_name=tool_name, tool_input=args if isinstance(args, dict) else {}, tool_output=result)
            )
            ti_display = json.dumps(args, ensure_ascii=False, indent=2) if args else ""
            reasoning_steps.append(
                {
                    "type": "tool",
                    "tool_name": tool_name,
                    "tool_input": ti_display,
                    "tool_output": result[:800] + ("..." if len(result) > 800 else ""),
                }
            )
            messages.append(ToolMessage(content=result, tool_call_id=tool_id))

    used_knowledge = "search_knowledge_base" in tools_invoked
    action_proposed = bool(tools_invoked and _ACTION_TOOLS.intersection(tools_invoked))

    return ChatResponse(
        response=output,
        used_knowledge=used_knowledge,
        tools_invoked=tools_invoked,
        tool_records=tool_records,
        reasoning_steps=reasoning_steps,
        action_proposed=action_proposed,
    )
