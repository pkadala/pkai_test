"""Ingestion sources: local and Google Drive (service account / SDK)."""
from __future__ import annotations

from langchain_core.documents import Document

from ingestion.sources.local import load_documents_local
from ingestion.sources.gdrive_sdk import load_documents_gdrive_sdk

IngestSourceKind = str  # "local" | "gdrive_sdk"


def load_documents_from_source(
    source: IngestSourceKind,
    *,
    local_path: str | None = None,
    folder_id: str | None = None,
    gdrive_credentials_path: str | None = None,
    gdrive_recursive: bool = True,
) -> list[Document]:
    """
    Load documents from the given source.
    - local: uses local_path or default documents/ directory
    - gdrive_sdk: Google Drive API with service account (folder_id optional)
    """
    if source == "local":
        return load_documents_local(directory=local_path)
    if source == "gdrive_sdk":
        return load_documents_gdrive_sdk(
            folder_id=folder_id,
            credentials_path=gdrive_credentials_path,
            recursive=gdrive_recursive,
        )
    raise ValueError(f"Unknown ingestion source: {source}")
