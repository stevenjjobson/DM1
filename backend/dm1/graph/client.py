"""
Graphiti client wrapper for DungeonMasterONE.

Provides the singleton Graphiti instance connected to Neo4j with Gemini LLM.
All graph operations go through this module — no other code touches Graphiti
or Neo4j directly.

The Archivist agent is the sole writer; other agents use query functions only.
"""

import logging
from datetime import datetime, timezone

from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode, EpisodeType

from dm1.config.settings import settings
from dm1.graph.schema import EdgeType, NodeType, TEMPORAL_EDGES

logger = logging.getLogger(__name__)

_graphiti: Graphiti | None = None


async def get_graphiti() -> Graphiti:
    """Get or create the singleton Graphiti instance."""
    global _graphiti
    if _graphiti is None:
        _graphiti = await _create_graphiti()
    return _graphiti


async def _create_graphiti() -> Graphiti:
    """Initialize Graphiti with Neo4j and Gemini LLM."""
    # Try Gemini first, fall back to no LLM for direct CRUD operations
    llm_client = None
    if settings.gemini_api_key:
        try:
            from graphiti_core.llm_client.google_client import GoogleClient
            from graphiti_core.llm_client.config import LLMConfig

            llm_client = GoogleClient(
                config=LLMConfig(
                    api_key=settings.gemini_api_key,
                    model="gemini-2.5-flash",  # Flash for entity extraction (cost-efficient)
                )
            )
            logger.info("Graphiti initialized with Gemini LLM")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini LLM for Graphiti: {e}")

    graphiti = Graphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        llm_client=llm_client,
    )

    # Create indexes (idempotent — safe to call every startup)
    try:
        await graphiti.build_indices_and_constraints()
        logger.info("Graphiti indices and constraints ready")
    except Exception as e:
        logger.warning(f"Failed to build Graphiti indices: {e}")

    return graphiti


async def close_graphiti():
    """Close the Graphiti connection."""
    global _graphiti
    if _graphiti is not None:
        try:
            await _graphiti.close()
        except Exception:
            pass
        _graphiti = None


# ---------------------------------------------------------------------------
# Node Operations (direct CRUD — used for structured game state changes)
# ---------------------------------------------------------------------------

async def create_node(
    name: str,
    node_type: NodeType,
    attributes: dict,
    group_id: str,
    summary: str = "",
) -> EntityNode:
    """Create an entity node in the knowledge graph."""
    graphiti = await get_graphiti()
    labels = [node_type.value]

    node = EntityNode(
        name=name,
        labels=labels,
        summary=summary or f"{node_type.value}: {name}",
        attributes=attributes,
        group_id=group_id,
    )
    await node.save(graphiti.driver)
    logger.info(f"Created node: {node_type.value}/{name} in group {group_id}")
    return node


async def get_node_by_uuid(uuid: str) -> EntityNode | None:
    """Retrieve a node by its UUID."""
    graphiti = await get_graphiti()
    try:
        return await EntityNode.get_by_uuid(graphiti.driver, uuid)
    except Exception:
        return None


async def update_node_attributes(uuid: str, attributes: dict) -> EntityNode | None:
    """Update specific attributes on an existing node."""
    node = await get_node_by_uuid(uuid)
    if node is None:
        return None

    node.attributes.update(attributes)
    graphiti = await get_graphiti()
    await node.save(graphiti.driver)
    return node


# ---------------------------------------------------------------------------
# Edge Operations (direct CRUD)
# ---------------------------------------------------------------------------

async def create_edge(
    source_uuid: str,
    target_uuid: str,
    edge_type: EdgeType,
    fact: str,
    group_id: str,
) -> EntityEdge:
    """Create a relationship edge between two nodes."""
    graphiti = await get_graphiti()
    now = datetime.now(timezone.utc)

    edge = EntityEdge(
        source_node_uuid=source_uuid,
        target_node_uuid=target_uuid,
        name=edge_type.value,
        fact=fact,
        group_id=group_id,
        valid_at=now if edge_type in TEMPORAL_EDGES else None,
    )
    await edge.save(graphiti.driver)
    logger.info(f"Created edge: {edge_type.value} from {source_uuid[:8]} to {target_uuid[:8]}")
    return edge


async def invalidate_edge(edge_uuid: str) -> EntityEdge | None:
    """Invalidate a temporal edge (set invalid_at to now)."""
    graphiti = await get_graphiti()
    try:
        edge = await EntityEdge.get_by_uuid(graphiti.driver, edge_uuid)
    except Exception:
        return None

    if edge is None:
        return None

    now = datetime.now(timezone.utc)
    edge.invalid_at = now
    edge.expired_at = now
    await edge.save(graphiti.driver)
    logger.info(f"Invalidated edge: {edge.name} ({edge_uuid[:8]})")
    return edge


# ---------------------------------------------------------------------------
# Episode Ingestion (LLM-driven entity extraction from narrative text)
# ---------------------------------------------------------------------------

async def add_narrative_episode(
    name: str,
    narrative_text: str,
    group_id: str,
    turn_number: int,
    source_description: str = "gameplay narrative",
) -> None:
    """Ingest narrative text and extract entities/relationships via LLM.

    This is the LLM-driven path — use for narrative text where entities and
    relationships need to be extracted automatically. For structured game state
    changes (item pickup, spell cast), use direct CRUD operations instead.
    """
    graphiti = await get_graphiti()
    await graphiti.add_episode(
        name=name,
        episode_body=narrative_text,
        source=EpisodeType.text,
        source_description=source_description,
        reference_time=datetime.now(timezone.utc),
        group_id=group_id,
    )
    logger.info(f"Ingested narrative episode: {name} (turn {turn_number}) in group {group_id}")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

async def search(
    query: str,
    group_id: str,
    center_node_uuid: str | None = None,
    limit: int = 10,
) -> list[EntityEdge]:
    """Hybrid search (semantic + BM25 + graph traversal) with optional graph-distance reranking."""
    graphiti = await get_graphiti()
    results = await graphiti.search(
        query=query,
        group_ids=[group_id],
        center_node_uuid=center_node_uuid,
        num_results=limit,
    )
    return results
