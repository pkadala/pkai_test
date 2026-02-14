"""Vector store: FAISS only (no database)."""
from __future__ import annotations

import os

from langchain_core.vectorstores import VectorStore

from app.rag.embeddings import get_embeddings


def _faiss_index_path() -> str:
    """Path to FAISS index directory (data/faiss_index under project root)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "faiss_index")


def get_vectorstore() -> VectorStore:
    """
    Return the active vector store. Always FAISS (load from disk if present, else in-memory).
    """
    embeddings = get_embeddings()
    from langchain_community.vectorstores import FAISS

    index_path = _faiss_index_path()
    if os.path.exists(index_path):
        return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    return FAISS.from_texts(["Initial placeholder"], embeddings)


def get_vectorstore_from_documents(texts: list[str], metadatas: list[dict] | None = None) -> VectorStore:
    """Build a new vector store from document chunks (for ingestion). Always FAISS."""
    embeddings = get_embeddings()
    from langchain_community.vectorstores import FAISS

    return FAISS.from_texts(texts, embeddings, metadatas=metadatas or [])
