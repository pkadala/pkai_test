"""
Ingest documents: load, chunk, embed, and write to FAISS.
Run from project root with LLM_PROVIDER/API keys set.

  LLM_PROVIDER=openai OPENAI_API_KEY=... python -m ingestion.ingest_docs
"""
from __future__ import annotations

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.load_vectorstore import load_documents, get_documents_dir
from ingestion.chunk_and_embed import chunk_documents
from app.rag.vectorstore_factory import get_vectorstore_from_documents


def main() -> None:
    docs_dir = get_documents_dir()
    print(f"Loading documents from {docs_dir}...")
    documents = load_documents(docs_dir)
    if not documents:
        print("No documents found. Add .txt, .md, .pdf, or .docx files to the 'documents/' directory.")
        return

    print(f"Loaded {len(documents)} document(s). Chunking...")
    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks.")

    texts = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]

    print("Building vector store and embedding...")
    vs = get_vectorstore_from_documents(texts, metadatas)

    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faiss_index")
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    vs.save_local(index_path)
    print(f"Saved FAISS index to {index_path}")
    print("Done.")


if __name__ == "__main__":
    main()
