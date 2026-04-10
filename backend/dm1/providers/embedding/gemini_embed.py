"""
Gemini Embedding 2 provider for DungeonMasterONE.

Embeds text and images into a unified vector space for cross-modal retrieval,
duplicate detection, and campaign style fingerprinting.
"""

import logging

from google import genai
from google.genai import types

from dm1.config.settings import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def embed_text(text: str, dimensions: int = 768) -> list[float]:
    """Embed text using Gemini Embedding 2.

    Args:
        text: The text to embed
        dimensions: 768 (fast) or 3072 (precise)
    """
    client = _get_client()
    response = client.models.embed_content(
        model="gemini-embedding-exp-03-07",  # Latest embedding model
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=dimensions),
    )
    return response.embeddings[0].values


async def embed_texts(texts: list[str], dimensions: int = 768) -> list[list[float]]:
    """Batch embed multiple texts."""
    client = _get_client()
    response = client.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=dimensions),
    )
    return [e.values for e in response.embeddings]
