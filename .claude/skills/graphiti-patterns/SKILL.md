---
name: graphiti-patterns
description: "Integration patterns for Graphiti + Neo4j in DungeonMasterONE — temporal knowledge graph operations"
---

## When to use

Invoke this skill when:
- Building or modifying the `dm1/graph/` module (schema, client, queries, mutations)
- Working on the Archivist agent (the sole graph writer)
- Implementing entity extraction from narrative text
- Designing temporal queries (current state vs historical state)
- Debugging knowledge graph issues (missing entities, stale edges, temporal inconsistencies)

## Current API Shape (graphiti-core v0.28.2)

### Installation
```bash
pip install graphiti-core[google-genai]
```

### Initialization with Gemini
```python
from graphiti_core import Graphiti
from graphiti_core.llm_client.google_client import GoogleClient
from graphiti_core.llm_client.config import LLMConfig

gemini_client = GoogleClient(
    config=LLMConfig(api_key=settings.GEMINI_API_KEY, model="gemini-2.5-flash")
)
graphiti = Graphiti(uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD, llm_client=gemini_client)
await graphiti.build_indices_and_constraints()  # Run once per database
```

### Core Types
- **EntityNode**: `name`, `labels[]`, `summary`, `attributes{}`, `name_embedding`, `uuid`, `group_id`
- **EntityEdge**: `source_node_uuid`, `target_node_uuid`, `name`, `fact`, `fact_embedding`, `valid_at`, `invalid_at`, `expired_at`, `episodes[]`
- **EpisodicNode**: `name`, `content`, `source` (text/json/message), `source_description`, `valid_at`
- **EpisodeType**: `.text`, `.json`, `.message`

### Adding Data
```python
# Narrative text (LLM extracts entities + relationships)
await graphiti.add_episode(
    name="Turn 47", episode_body="narrative text...",
    source=EpisodeType.text, source_description="gameplay",
    reference_time=datetime.now(timezone.utc), group_id=campaign_id
)

# Direct CRUD (deterministic, no LLM call — use for structured game state changes)
node = EntityNode(name="Sword of Flames", labels=["Item", "Weapon"], summary="...")
await node.save(graphiti.graph_driver)

edge = EntityEdge(source_node_uuid=player_uuid, target_node_uuid=sword_uuid,
    name="OWNED_BY", fact="Player acquired Sword of Flames", valid_at=datetime.now(timezone.utc))
await edge.save(graphiti.graph_driver)
```

### Searching
```python
from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF

results = await graphiti.search(query="...", config=EDGE_HYBRID_SEARCH_RRF, group_ids=[campaign_id])
# Optional: center_node_uuid for graph-distance reranking
```

### Temporal Operations
```python
# Invalidate a fact (e.g., item dropped, NPC moved)
edge.invalid_at = datetime.now(timezone.utc)
edge.expired_at = datetime.now(timezone.utc)
await edge.save(graphiti.graph_driver)

# Query only active facts
from graphiti_core.search.search_filters import SearchFilters, DateFilter
filters = SearchFilters(edge_filters={"invalid_at": DateFilter(equals=None)})
results = await graphiti.search("query", edge_search_filter=filters, group_ids=[campaign_id])
```

## DM1 Integration Pattern

### Campaign Isolation
Use `group_id=campaign_id` on ALL operations. Each campaign is a fully isolated namespace.

### Archivist as Sole Writer
ALL graph mutations MUST go through the Archivist agent. No other agent calls `add_episode()`, `node.save()`, or `edge.save()` directly. This prevents race conditions and ensures a single serialization point.

### When to Use add_episode() vs Direct CRUD

| Scenario | Method | Rationale |
|---|---|---|
| Narrator output (narrative text) | `add_episode()` | LLM extracts entities and relationships from prose |
| Item pickup/drop | Direct CRUD (`edge.save()`) | Deterministic, no LLM needed, faster |
| Spell slot change | Direct CRUD (`node.save()`) | Structured state update |
| HP change | Direct CRUD (`node.save()`) | Structured state update |
| NPC dialogue | `add_episode()` | May reveal new information, relationships |
| Quest creation | Direct CRUD | Structured quest/objective nodes |

### DM1 Node → Graphiti Mapping

| DM1 Node Type | Graphiti Labels | Key Attributes |
|---|---|---|
| Character | `["Character", "Player"]` | race, class, level, hp, abilities |
| NPC | `["NPC", race]` | personality, motivations, opinion_of_player |
| Item | `["Item", item_type]` | weight, value, magical, properties |
| Location | `["Location", location_type]` | connections, discovered_at |
| Quest | `["Quest"]` | status, quest_confidence |
| Spell | `["Spell", school]` | level, components, duration |

### DM1 Edge → Graphiti Mapping

| DM1 Edge | Graphiti `name` | Temporal? | Notes |
|---|---|---|---|
| OWNED_BY | "OWNED_BY" | Yes | `invalid_at` set when item dropped/traded |
| EQUIPPED_BY | "EQUIPPED_BY" | Yes | |
| LOCATED_AT | "LOCATED_AT" | Yes | Updated when entity moves |
| KNOWS_SPELL | "KNOWS_SPELL" | Yes | |
| GIVEN_BY | "GIVEN_BY" | No | Quest origin doesn't change |
| HAS_OBJECTIVE | "HAS_OBJECTIVE" | No | |

## Common Pitfalls

1. **LLM cost on add_episode()**: Every call triggers entity extraction via LLM. Batch multiple events into a single episode when possible ("Turn 47: The player fought the goblin, found a sword, and entered the cave").

2. **Entity deduplication**: Graphiti deduplicates entities by semantic similarity. If the LLM extracts "The Innkeeper" and "Barkeep Grom" as separate entities when they're the same NPC, you may get duplicates. Use consistent naming in narrator output to mitigate.

3. **SEMAPHORE_LIMIT**: Controls concurrent LLM operations (default 10). Set via environment variable. Tune based on Gemini rate limits.

4. **Contradiction detection**: Graphiti auto-invalidates superseded facts ("Alice works at Acme" becomes invalid when "Alice works at Globex" is ingested). This is usually helpful but can cause issues if the LLM misinterprets narrative — e.g., an NPC lying could be detected as a "contradiction" and invalidate a true fact. Solution: mark NPC speech as a separate episode with appropriate source_description.

5. **Community detection**: `build_communities()` is useful for summarizing regions/factions but is computationally expensive. Run periodically (end of session, not per-turn).

## Code Examples

### Building the Archivist Context Package
```python
async def build_context_package(graphiti: Graphiti, campaign_id: str, player_uuid: str, location_uuid: str) -> dict:
    """Assemble graph context for the Narrator."""
    # Current character state
    char_edges = await graphiti.search("player character state", group_ids=[campaign_id], center_node_uuid=player_uuid)
    # Nearby entities
    location_edges = await graphiti.search("entities at current location", group_ids=[campaign_id], center_node_uuid=location_uuid)
    # Recent events (last 5 turns)
    recent = await graphiti.search("recent events", group_ids=[campaign_id])
    return {"character": char_edges, "location": location_edges, "recent_events": recent[:10]}
```
