"""LLM factory: OpenAI or Gemini based on config."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app import env as env_loader


def get_llm() -> BaseChatModel:
    """Return the configured chat model (OpenAI or Gemini)."""
    if env_loader.llm_provider() == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=env_loader.gemini_model(),
            google_api_key=env_loader.get_google_key(),
            temperature=0,
            convert_system_message_to_human=True,
        )
    # OpenAI
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=env_loader.openai_model(),
        openai_api_key=env_loader.get_openai_key(),
        temperature=0,
    )
