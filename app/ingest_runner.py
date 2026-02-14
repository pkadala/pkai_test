"""Run document ingestion from the web app; returns result for API."""
from __future__ import annotations

from pathlib import Path

from app.schemas import IngestRequest, IngestResponse


def run_ingest(options: IngestRequest | None = None) -> IngestResponse:
    """Load documents from the chosen source, chunk, embed, and persist. Returns result for API."""
    opts = options or IngestRequest()
    source = (opts.source or "local").strip().lower()
    if source not in ("local", "gdrive_oauth"):
        return IngestResponse(ok=False, message=f"Unknown source: {opts.source}", chunks_created=0)

    try:
        from ingestion.sources import load_documents_from_source
        from ingestion.chunk_and_embed import chunk_documents
        from app.rag.vectorstore_factory import get_vectorstore_from_documents
    except ImportError as e:
        return IngestResponse(ok=False, message=f"Import error: {e}", chunks_created=0)

    try:
        documents = load_documents_from_source(
            source,
            local_path=opts.local_path or None,
            folder_id=opts.folder_id or None,
            gdrive_credentials_path=None,
            workspace_mcp_path=None,
        )
    except ValueError as e:
        return IngestResponse(ok=False, message=str(e), chunks_created=0)
    except Exception as e:
        return IngestResponse(ok=False, message=f"Load error: {e}", chunks_created=0)

    if not documents:
        return IngestResponse(
            ok=True,
            message=_no_docs_message(source),
            chunks_created=0,
        )

    chunks = chunk_documents(documents)
    texts = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vs = get_vectorstore_from_documents(texts, metadatas)

    index_path = Path(__file__).resolve().parent.parent / "data" / "faiss_index"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(index_path))
    return IngestResponse(
        ok=True,
        message=f"Ingested {len(documents)} document(s) into {len(chunks)} chunks ({source}). FAISS index saved.",
        chunks_created=len(chunks),
    )


def _no_docs_message(source: str) -> str:
    if source == "local":
        return "No documents found. Add .txt, .md, .pdf, or .docx files to the documents/ directory."
    if source == "gdrive_oauth":
        return "No supported files in your Google Drive (or folder). Connect Google Drive first if you haven’t."
    return "No documents found."
