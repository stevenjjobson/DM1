"""
Game state API endpoints for DungeonMasterONE.

Serves live character sheet, inventory, spellbook, and quest log —
all derived from the knowledge graph. These are read-only views;
game state is mutated only through gameplay turns via the Archivist.
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from dm1.api.database import get_database
from dm1.api.middleware.auth import get_current_user_id
from dm1.graph.client import search, get_node_by_uuid
from dm1.rules.dice import ability_modifier, proficiency_bonus
from dm1.rules.skills import SKILL_ABILITIES

router = APIRouter(prefix="/gamestate", tags=["gamestate"])


@router.get("/{campaign_id}/character")
async def get_character_sheet(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the full character sheet derived from the knowledge graph."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    character_id = campaign.get("character_id")

    # Try to load character node from graph
    character_data = {}
    if character_id:
        node = await get_node_by_uuid(character_id)
        if node:
            character_data = node.attributes or {}

    # Get related facts from graph search
    graph_facts = await search("player character stats equipment location", campaign_id, limit=10)

    # Build structured character sheet
    abilities = character_data.get("abilities", {})
    level = character_data.get("level", 1)
    prof = proficiency_bonus(level)

    modifiers = {k: ability_modifier(v) for k, v in abilities.items()} if abilities else {}

    return {
        "name": character_data.get("name", campaign.get("name", "Adventurer")),
        "race": character_data.get("race", "Unknown"),
        "class": character_data.get("char_class", "Unknown"),
        "level": level,
        "xp": character_data.get("xp", 0),
        "hp": character_data.get("hp", 0),
        "max_hp": character_data.get("max_hp", 0),
        "ac": character_data.get("ac", 10),
        "speed": character_data.get("speed", 30),
        "proficiency_bonus": prof,
        "abilities": abilities,
        "modifiers": modifiers,
        "conditions": character_data.get("conditions", []),
        "proficiencies": character_data.get("proficiencies", []),
        "background": character_data.get("background", ""),
        "backstory": character_data.get("backstory", ""),
        "current_turn": campaign.get("current_turn", 0),
        "graph_context": [{"fact": e.fact, "type": e.name} for e in graph_facts[:8]],
    }


@router.get("/{campaign_id}/inventory")
async def get_inventory(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the character's inventory from the knowledge graph."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Search for items owned by the character
    item_edges = await search(
        "items equipment weapons armor potions owned carried inventory",
        campaign_id, limit=20
    )

    items = []
    for edge in item_edges:
        if any(kw in edge.name.lower() for kw in ["owned", "equipped", "item"]) or \
           any(kw in edge.fact.lower() for kw in ["owns", "owned", "carries", "equipped", "acquired", "found", "item"]):
            items.append({
                "fact": edge.fact,
                "type": edge.name,
                "uuid": edge.uuid,
            })

    return {"items": items, "total": len(items)}


@router.get("/{campaign_id}/spellbook")
async def get_spellbook(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the character's spellbook from the knowledge graph."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get spell slots from character node
    character_id = campaign.get("character_id")
    spell_slots = {}
    if character_id:
        node = await get_node_by_uuid(character_id)
        if node and node.attributes:
            spell_slots = node.attributes.get("spell_slots", {})

    # Search for known spells
    spell_edges = await search(
        "spells known prepared cantrips magic arcane divine",
        campaign_id, limit=20
    )

    spells = []
    for edge in spell_edges:
        if any(kw in edge.fact.lower() for kw in ["spell", "cantrip", "knows", "prepared", "cast"]):
            spells.append({
                "fact": edge.fact,
                "type": edge.name,
                "uuid": edge.uuid,
            })

    return {
        "spells": spells,
        "spell_slots": spell_slots,
        "total": len(spells),
    }


@router.get("/{campaign_id}/quests")
async def get_quest_log(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get active and completed quests from the knowledge graph."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Search for quest-related facts
    quest_edges = await search(
        "quests objectives goals missions tasks quest given find rescue",
        campaign_id, limit=20
    )

    active_quests = []
    completed_quests = []
    for edge in quest_edges:
        quest_item = {"fact": edge.fact, "type": edge.name, "uuid": edge.uuid}
        if "completed" in edge.fact.lower() or "finished" in edge.fact.lower():
            completed_quests.append(quest_item)
        else:
            active_quests.append(quest_item)

    return {
        "active": active_quests,
        "completed": completed_quests,
        "total": len(active_quests) + len(completed_quests),
    }
