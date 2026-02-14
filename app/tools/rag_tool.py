"""RAG tool: search the personal knowledge base."""
from __future__ import annotations

from langchain_core.tools import tool

from app.rag.retriever import retrieve


@tool
def search_knowledge_base(query: str, k: int = 4) -> str:
    """
    Search the user's personal knowledge base for relevant information.
    Use this when you need to answer questions using the user's own documents and notes.
    """
    docs = retrieve(query, k=k)
    if not docs:
        return "No relevant documents found in the knowledge base."
    parts = []
    for i, doc in enumerate(docs, 1):
        content = doc.page_content.strip()
        source = doc.metadata.get("source", "unknown")
        parts.append(f"[{i}] (source: {source})\n{content}")
    return "\n\n---\n\n".join(parts)
