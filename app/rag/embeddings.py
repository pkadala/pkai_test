"""Embedding model selection - OpenAI or Gemini based on config."""
from __future__ import annotations

from langchain_core.embeddings import Embeddings

from app import env as env_loader


def get_embeddings() -> Embeddings:
    """Return the configured embedding model (OpenAI or Gemini)."""
    if env_loader.llm_provider() == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=env_loader.gemini_embedding_model(),
            google_api_key=env_loader.get_google_key(),
        )
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=env_loader.openai_embedding_model(),
        openai_api_key=env_loader.get_openai_key(),
    )
