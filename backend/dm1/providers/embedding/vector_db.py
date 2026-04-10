"""
Qdrant vector database provider for DungeonMasterONE.

Per-campaign collections with named vectors (768d fast + 3072d precise).
Handles collection lifecycle, embedding storage, and similarity search.
"""

import logging
import uuid as uuid_mod
from typing import Any

import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from dm1.config.settings import settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None


async def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client


def _collection_name(campaign_id: str) -> str:
    return f"campaign_{campaign_id}"


def _normalize(vector: list[float]) -> list[float]:
    """Normalize a vector for cosine similarity (required for 768d from Gemini)."""
    arr = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


async def create_campaign_collection(campaign_id: str) -> None:
    """Create a Qdrant collection for a campaign with named vectors."""
    client = await get_qdrant()
    name = _collection_name(campaign_id)

    exists = await client.collection_exists(name)
    if exists:
        return

    await client.create_collection(
        collection_name=name,
        vectors_config={
            "fast": VectorParams(size=768, distance=Distance.COSINE),
        },
    )
    logger.info(f"Created Qdrant collection: {name}")


async def delete_campaign_collection(campaign_id: str) -> None:
    """Delete a campaign's Qdrant collection."""
    client = await get_qdrant()
    name = _collection_name(campaign_id)
    if await client.collection_exists(name):
        await client.delete_collection(name)
        logger.info(f"Deleted Qdrant collection: {name}")


async def store_embedding(
    campaign_id: str,
    vector_768: list[float],
    metadata: dict[str, Any],
) -> str:
    """Store an embedding with metadata in the campaign collection.

    Returns the point UUID.
    """
    client = await get_qdrant()
    point_id = str(uuid_mod.uuid4())

    await client.upsert(
        collection_name=_collection_name(campaign_id),
        points=[
            PointStruct(
                id=point_id,
                vector={"fast": _normalize(vector_768)},
                payload=metadata,
            )
        ],
    )
    return point_id


async def search_similar(
    campaign_id: str,
    query_vector: list[float],
    asset_type: str | None = None,
    threshold: float = 0.85,
    limit: int = 5,
) -> list[dict]:
    """Search for similar assets in the campaign collection.

    Returns list of {score, payload} dicts.
    """
    client = await get_qdrant()
    name = _collection_name(campaign_id)

    if not await client.collection_exists(name):
        return []

    query_filter = None
    if asset_type:
        query_filter = Filter(
            must=[FieldCondition(key="asset_type", match=MatchValue(value=asset_type))]
        )

    results = await client.query_points(
        collection_name=name,
        query=_normalize(query_vector),
        using="fast",
        query_filter=query_filter,
        score_threshold=threshold,
        limit=limit,
        with_payload=True,
    )

    return [
        {"score": point.score, "payload": point.payload}
        for point in results.points
    ]
