"""External tool: fetch updates from external sources (demo)."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def fetch_external_updates(source: str = "default") -> str:
    """
    Fetch the latest updates from an external source.
    Use when the user asks for recent or external information not in the knowledge base.
    """
    # Demo implementation: return a placeholder. Real implementation could call APIs, RSS, etc.
    return f"[External] No live updates configured for source '{source}'. This is a placeholder; integrate RSS or APIs as needed."
