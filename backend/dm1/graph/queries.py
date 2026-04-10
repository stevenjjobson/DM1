"""
Standard query patterns for the DungeonMasterONE knowledge graph.

These implement the 5 query patterns from architecture.md:
1. Current character state
2. NPC memory
3. Location context
4. Item history
5. Plot state (active quests)

All queries use Graphiti's hybrid search with group_id scoping.
"""

from dm1.graph.client import get_graphiti, search, get_node_by_uuid
from graphiti_core.nodes import EntityNode


async def get_current_character_state(group_id: str) -> dict:
    """Query 1: Full character state — abilities, HP, AC, conditions, equipment.

    Returns the Character node with all active (non-invalidated) edges:
    OWNED_BY items, EQUIPPED_BY items, KNOWS_SPELL spells, LOCATED_AT location.
    """
    edges = await search("player character current state abilities equipment", group_id)
    character_edges = await search("character stats level hit points armor class", group_id)

    return {
        "primary_edges": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in edges],
        "stat_edges": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in character_edges],
    }


async def get_npc_memory(group_id: str, npc_name: str) -> dict:
    """Query 2: NPC memory — all interactions between the NPC and the player.

    Used by the NPC Agent to build context for dialogue generation.
    Returns events where both NPC and Character participated, ordered by turn.
    """
    edges = await search(
        f"interactions with {npc_name} conversations meetings events",
        group_id,
        limit=15,
    )
    opinion_edges = await search(
        f"{npc_name} opinion relationship trust hostility",
        group_id,
        limit=5,
    )

    return {
        "interactions": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in edges],
        "relationship": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in opinion_edges],
    }


async def get_location_context(group_id: str, location_name: str) -> dict:
    """Query 3: Location context — entities at current location + connected locations.

    Returns all entities LOCATED_AT the given location and adjacent locations.
    """
    entities_here = await search(
        f"entities at {location_name} people items creatures present",
        group_id,
        limit=15,
    )
    connections = await search(
        f"locations connected to {location_name} paths exits entrances",
        group_id,
        limit=10,
    )

    return {
        "entities_present": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in entities_here],
        "connections": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in connections],
    }


async def get_item_history(group_id: str, item_name: str) -> dict:
    """Query 4: Item history — ownership timeline and location history.

    Returns the full edge timeline for an item (who owned it, where it was).
    """
    edges = await search(
        f"{item_name} owned by carried found acquired dropped traded",
        group_id,
        limit=10,
    )

    return {
        "history": [
            {
                "fact": e.fact,
                "name": e.name,
                "valid_at": str(e.valid_at) if e.valid_at else None,
                "invalid_at": str(e.invalid_at) if e.invalid_at else None,
                "uuid": e.uuid,
            }
            for e in edges
        ],
    }


async def get_plot_state(group_id: str) -> dict:
    """Query 5: Plot state — active quests, objectives, and recent events.

    Returns all Quest nodes with status=active, their objectives, and recent plot events.
    """
    quest_edges = await search(
        "active quests objectives goals missions tasks",
        group_id,
        limit=10,
    )
    recent_events = await search(
        "recent events happened encounters discoveries",
        group_id,
        limit=10,
    )

    return {
        "active_quests": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in quest_edges],
        "recent_events": [{"fact": e.fact, "name": e.name, "uuid": e.uuid} for e in recent_events],
    }


async def build_narrator_context(group_id: str, player_action: str, location_name: str = "") -> dict:
    """Build the full context package for the Narrator agent.

    Combines character state, location context, recent events, and
    action-relevant context into a single package.
    """
    character = await get_current_character_state(group_id)
    plot = await get_plot_state(group_id)

    # Action-specific context
    action_context = await search(player_action, group_id, limit=5)

    location = {}
    if location_name:
        location = await get_location_context(group_id, location_name)

    return {
        "character_state": character,
        "location": location,
        "plot_state": plot,
        "action_context": [{"fact": e.fact, "name": e.name} for e in action_context],
    }
