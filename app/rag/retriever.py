"""Retriever interface used by the agent; implementation-agnostic."""
from __future__ import annotations

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

from app.rag.vectorstore_factory import get_vectorstore


def get_retriever(k: int = 4) -> BaseRetriever:
    """Return a retriever over the active vector store. Agent depends only on this interface."""
    return get_vectorstore().as_retriever(search_kwargs={"k": k})


def _is_placeholder_doc(doc: Document) -> bool:
    """True for synthetic docs used when no FAISS index exists yet."""
    meta = doc.metadata or {}
    if meta.get("_pkai_placeholder") or meta.get("source") == "__pkai_empty_index__":
        return True
    text = (doc.page_content or "").strip()
    return text == "Initial placeholder"


def retrieve(query: str, k: int = 4) -> list[Document]:
    """Convenience: retrieve documents for a query (never return empty-index placeholders)."""
    # Over-fetch then filter so we still return up to k real chunks if the index mixes real + dummy.
    raw = get_retriever(k=max(k * 4, k + 8)).invoke(query)
    filtered = [d for d in raw if not _is_placeholder_doc(d)]
    return filtered[:k]
