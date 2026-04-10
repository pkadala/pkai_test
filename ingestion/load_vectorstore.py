"""Load documents using LangChain loaders (placeholder: extend with real loaders)."""
from __future__ import annotations

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


def _load_one_file(path: Path) -> list[Document]:
    """Load a single supported file; return [] if unsupported or error."""
    try:
        suf = path.suffix.lower()
        if suf == ".txt":
            loader = TextLoader(str(path), encoding="utf-8")
        elif suf == ".md":
            loader = UnstructuredMarkdownLoader(str(path))
        elif suf == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suf in (".docx", ".doc"):
            loader = Docx2txtLoader(str(path))
        else:
            return []
        return loader.load()
    except Exception as e:
        print(f"Skip {path}: {e}")
        return []


def load_documents(directory: str | Path | None = None) -> list[Document]:
    """
    Load supported documents from a directory (recursive) or a single file path.
    Supports .txt, .md, .pdf, .docx.
    """
    base = Path(directory).expanduser() if directory else get_documents_dir()
    if not base.exists():
        return []

    if base.is_file():
        docs = _load_one_file(base)
    else:
        docs = []
        for path in base.rglob("*"):
            if path.is_file():
                docs.extend(_load_one_file(path))

    for d in docs:
        if not d.metadata.get("source"):
            d.metadata["source"] = str(d.metadata.get("source", "unknown"))
    return docs
