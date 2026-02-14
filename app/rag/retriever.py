"""Retriever interface used by the agent; implementation-agnostic."""
from __future__ import annotations

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

from app.rag.vectorstore_factory import get_vectorstore


def get_retriever(k: int = 4) -> BaseRetriever:
    """Return a retriever over the active vector store. Agent depends only on this interface."""
    return get_vectorstore().as_retriever(search_kwargs={"k": k})


def retrieve(query: str, k: int = 4) -> list[Document]:
    """Convenience: retrieve documents for a query."""
    return get_retriever(k=k).invoke(query)
