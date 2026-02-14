"""Load documents using LangChain loaders (placeholder: extend with real loaders)."""
from __future__ import annotations

import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    PyPDFLoader,
    Docx2txtLoader,
)


def get_documents_dir() -> Path:
    """Default documents directory relative to project root."""
    root = Path(__file__).resolve().parent.parent
    return root / "documents"


def load_documents(directory: str | Path | None = None) -> list[Document]:
    """
    Load all supported documents from a directory.
    Supports .txt, .md, .pdf, .docx.
    """
    base = Path(directory) if directory else get_documents_dir()
    if not base.exists():
        return []

    docs = []
    for path in base.rglob("*"):
        if path.is_file():
            try:
                if path.suffix.lower() == ".txt":
                    loader = TextLoader(str(path), encoding="utf-8")
                elif path.suffix.lower() == ".md":
                    loader = UnstructuredMarkdownLoader(str(path))
                elif path.suffix.lower() == ".pdf":
                    loader = PyPDFLoader(str(path))
                elif path.suffix.lower() in (".docx", ".doc"):
                    loader = Docx2txtLoader(str(path))
                else:
                    continue
                docs.extend(loader.load())
            except Exception as e:
                print(f"Skip {path}: {e}")
                continue

    for d in docs:
        if not d.metadata.get("source"):
            d.metadata["source"] = str(d.metadata.get("source", "unknown"))
    return docs
