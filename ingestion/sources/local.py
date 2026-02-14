"""Local ingestion: load from documents/ directory."""
from __future__ import annotations

from langchain_core.documents import Document

from ingestion.load_vectorstore import load_documents, get_documents_dir


def load_documents_local(directory: str | None = None) -> list[Document]:
    """Load documents from local documents/ directory (or given path)."""
    return load_documents(directory)
