"""Indexed document stats for the Ingest page and index deletion (FAISS)."""
from __future__ import annotations

import os
import shutil
from typing import Any

from app.rag.vectorstore_factory import get_faiss_index_path, get_vectorstore


def get_indexed_stats() -> dict[str, Any]:
    """
    Return stats and list of indexed documents for display.
    Returns: { chunk_count, file_count, storage_type, sources: [{source, chunk_count, metadata}] }
    """
    store = get_vectorstore()
    return _get_faiss_indexed(store)


def _get_faiss_indexed(store: Any) -> dict[str, Any]:
    """Extract indexed docs from FAISS docstore, grouped by source."""
    sources_map: dict[str, dict[str, Any]] = {}

    try:
        docstore = getattr(store, "docstore", None)
        if docstore is None:
            return {"chunk_count": 0, "file_count": 0, "sources": [], "storage_type": "faiss"}

        doc_dict = getattr(docstore, "_dict", {})
        if not doc_dict:
            return {"chunk_count": 0, "file_count": 0, "sources": [], "storage_type": "faiss"}

        for _doc_id, doc in doc_dict.items():
            if "PKAI knowledge base initialized" in (doc.page_content or ""):
                continue
            if "Initial placeholder" in (doc.page_content or ""):
                continue
            source = doc.metadata.get("source", "unknown")
            if source not in sources_map:
                sources_map[source] = {
                    "source": source,
                    "chunk_count": 0,
                    "metadata": dict(doc.metadata),
                }
            sources_map[source]["chunk_count"] += 1

        sources = list(sources_map.values())
        total_chunks = sum(s["chunk_count"] for s in sources)
        return {
            "chunk_count": total_chunks,
            "file_count": len(sources),
            "sources": sources[:100],
            "storage_type": "faiss",
            "storage_path": get_faiss_index_path(),
        }
    except Exception:
        return {"chunk_count": 0, "file_count": 0, "sources": [], "storage_type": "faiss"}


def delete_index() -> tuple[bool, str]:
    """Delete the FAISS index directory. Returns (success, message)."""
    index_path = get_faiss_index_path()
    try:
        if os.path.exists(index_path):
            shutil.rmtree(index_path)
            return True, f"Index deleted ({index_path})"
        return True, "No index found (already empty)"
    except Exception as e:
        return False, str(e)
