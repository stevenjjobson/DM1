"""
Knowledge graph mutation operations for DungeonMasterONE.

These are higher-level operations that compose the base CRUD from client.py
into game-state-meaningful actions. Only the Archivist agent calls these.

Design principle: structured game state changes (item pickup, spell cast,
HP change) use direct CRUD. Narrative text that needs entity extraction
uses add_narrative_episode().
"""

from dm1.graph.client import (
    add_narrative_episode,
    create_edge,
    create_node,
    invalidate_edge,
    search,
    update_node_attributes,
)
from dm1.graph.schema import (
    CharacterAttributes,
    EdgeType,
    EventAttributes,
    ItemAttributes,
    LocationAttributes,
    NPCAttributes,
    NodeType,
    QuestAttributes,
    ObjectiveAttributes,
)


async def create_character(
    name: str,
    attributes: dict,
    group_id: str,
    starting_location_uuid: str | None = None,
) -> str:
    """Create a player character node and place them at a starting location."""
    node = await create_node(
        name=name,
        node_type=NodeType.CHARACTER,
        attributes=attributes,
        group_id=group_id,
        summary=f"Player character: {name}",
    )

    if starting_location_uuid:
        await create_edge(
            source_uuid=node.uuid,
            target_uuid=starting_location_uuid,
            edge_type=EdgeType.LOCATED_AT,
            fact=f"{name} is at the starting location",
            group_id=group_id,
        )

    return node.uuid


async def create_npc(
    name: str,
    attributes: dict,
    group_id: str,
    location_uuid: str | None = None,
) -> str:
    """Create an NPC node and optionally place them at a location."""
    node = await create_node(
        name=name,
        node_type=NodeType.NPC,
        attributes=attributes,
        group_id=group_id,
        summary=f"NPC: {name}",
    )

    if location_uuid:
        await create_edge(
            source_uuid=node.uuid,
            target_uuid=location_uuid,
            edge_type=EdgeType.LOCATED_AT,
            fact=f"{name} is located here",
            group_id=group_id,
        )

    return node.uuid


async def create_location(
    name: str,
    attributes: dict,
    group_id: str,
    connected_to_uuid: str | None = None,
) -> str:
    """Create a location node and optionally connect it to another location."""
    node = await create_node(
        name=name,
        node_type=NodeType.LOCATION,
        attributes=attributes,
        group_id=group_id,
        summary=f"Location: {name}",
    )

    if connected_to_uuid:
        await create_edge(
            source_uuid=node.uuid,
            target_uuid=connected_to_uuid,
            edge_type=EdgeType.CONNECTED_TO,
            fact=f"{name} is connected to another location",
            group_id=group_id,
        )

    return node.uuid


async def give_item_to_character(
    item_name: str,
    item_attributes: dict,
    character_uuid: str,
    group_id: str,
) -> str:
    """Create an item and assign ownership to a character."""
    item_node = await create_node(
        name=item_name,
        node_type=NodeType.ITEM,
        attributes=item_attributes,
        group_id=group_id,
        summary=f"Item: {item_name}",
    )

    await create_edge(
        source_uuid=item_node.uuid,
        target_uuid=character_uuid,
        edge_type=EdgeType.OWNED_BY,
        fact=f"{item_name} is owned by the player character",
        group_id=group_id,
    )

    return item_node.uuid


async def transfer_item(
    item_uuid: str,
    old_owner_edge_uuid: str,
    new_owner_uuid: str,
    item_name: str,
    new_owner_name: str,
    group_id: str,
) -> str:
    """Transfer an item from one entity to another."""
    # Invalidate old ownership
    await invalidate_edge(old_owner_edge_uuid)

    # Create new ownership
    edge = await create_edge(
        source_uuid=item_uuid,
        target_uuid=new_owner_uuid,
        edge_type=EdgeType.OWNED_BY,
        fact=f"{item_name} is now owned by {new_owner_name}",
        group_id=group_id,
    )

    return edge.uuid


async def move_entity(
    entity_uuid: str,
    old_location_edge_uuid: str | None,
    new_location_uuid: str,
    entity_name: str,
    location_name: str,
    group_id: str,
) -> str:
    """Move a character/NPC to a new location."""
    if old_location_edge_uuid:
        await invalidate_edge(old_location_edge_uuid)

    edge = await create_edge(
        source_uuid=entity_uuid,
        target_uuid=new_location_uuid,
        edge_type=EdgeType.LOCATED_AT,
        fact=f"{entity_name} moved to {location_name}",
        group_id=group_id,
    )

    return edge.uuid


async def learn_spell(
    character_uuid: str,
    spell_name: str,
    spell_attributes: dict,
    group_id: str,
) -> str:
    """Add a spell to a character's known spells."""
    spell_node = await create_node(
        name=spell_name,
        node_type=NodeType.SPELL,
        attributes=spell_attributes,
        group_id=group_id,
        summary=f"Spell: {spell_name}",
    )

    await create_edge(
        source_uuid=character_uuid,
        target_uuid=spell_node.uuid,
        edge_type=EdgeType.KNOWS_SPELL,
        fact=f"The player character knows {spell_name}",
        group_id=group_id,
    )

    return spell_node.uuid


async def create_quest(
    quest_name: str,
    description: str,
    objectives: list[str],
    quest_giver_uuid: str | None,
    group_id: str,
    revealed: bool = True,
) -> str:
    """Create a quest with objectives, optionally linked to a quest giver."""
    quest_node = await create_node(
        name=quest_name,
        node_type=NodeType.QUEST,
        attributes={"status": "active", "description": description, "quest_confidence": 0.9, "revealed": revealed},
        group_id=group_id,
        summary=f"Quest: {quest_name}",
    )

    for obj_desc in objectives:
        obj_node = await create_node(
            name=obj_desc[:50],
            node_type=NodeType.OBJECTIVE,
            attributes={"status": "active", "description": obj_desc, "progress": ""},
            group_id=group_id,
            summary=f"Objective: {obj_desc}",
        )
        await create_edge(
            source_uuid=quest_node.uuid,
            target_uuid=obj_node.uuid,
            edge_type=EdgeType.HAS_OBJECTIVE,
            fact=f"Quest objective: {obj_desc}",
            group_id=group_id,
        )

    if quest_giver_uuid:
        await create_edge(
            source_uuid=quest_node.uuid,
            target_uuid=quest_giver_uuid,
            edge_type=EdgeType.GIVEN_BY,
            fact=f"Quest given by an NPC",
            group_id=group_id,
        )

    return quest_node.uuid


async def record_event(
    event_type: str,
    description: str,
    turn_number: int,
    group_id: str,
    participants: list[str] | None = None,
    location_uuid: str | None = None,
) -> str:
    """Record a game event with optional participant and location links."""
    event_node = await create_node(
        name=f"Turn {turn_number}: {event_type}",
        node_type=NodeType.EVENT,
        attributes={
            "event_type": event_type,
            "turn_number": turn_number,
            "description": description,
        },
        group_id=group_id,
        summary=description,
    )

    if participants:
        for p_uuid in participants:
            await create_edge(
                source_uuid=p_uuid,
                target_uuid=event_node.uuid,
                edge_type=EdgeType.PARTICIPATED_IN,
                fact=f"Participated in: {description}",
                group_id=group_id,
            )

    if location_uuid:
        await create_edge(
            source_uuid=event_node.uuid,
            target_uuid=location_uuid,
            edge_type=EdgeType.OCCURRED_AT,
            fact=f"Event occurred at this location",
            group_id=group_id,
        )

    return event_node.uuid


async def update_character_hp(character_uuid: str, new_hp: int, max_hp: int | None = None) -> None:
    """Update character hit points."""
    updates = {"hp": new_hp}
    if max_hp is not None:
        updates["max_hp"] = max_hp
    await update_node_attributes(character_uuid, updates)


async def update_npc_opinion(npc_uuid: str, opinion_change: int) -> None:
    """Adjust an NPC's opinion of the player."""
    from dm1.graph.client import get_node_by_uuid
    node = await get_node_by_uuid(npc_uuid)
    if node:
        current = node.attributes.get("opinion_of_player", 0)
        new_opinion = max(-100, min(100, current + opinion_change))
        await update_node_attributes(npc_uuid, {"opinion_of_player": new_opinion})
