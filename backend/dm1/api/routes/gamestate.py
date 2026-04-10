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
        try:
            node = await get_node_by_uuid(character_id)
            if node and node.attributes:
                character_data = node.attributes
        except Exception:
            pass

    # Fallback: check if character data was stored in the campaign doc
    if not character_data and campaign.get("character_attrs"):
        character_data = campaign["character_attrs"]

    # Get related facts from graph search
    graph_facts = []
    try:
        graph_facts = await search("player character stats equipment location", campaign_id, limit=8)
    except Exception:
        pass

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

    # Search specifically for OWNED_BY relationships
    item_edges = await search(
        "player character owns carries possesses equipped weapon armor",
        campaign_id, limit=15
    )

    items = []
    for edge in item_edges:
        # Only include edges that indicate ownership or equipment
        fact_lower = edge.fact.lower()
        name_lower = edge.name.lower()
        if name_lower in ("owned_by", "equipped_by") or \
           any(kw in fact_lower for kw in ["owns", "owned by", "carries", "equipped", "picked up", "acquired"]):
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

    # Search specifically for quest structure edges
    quest_edges = await search(
        "quest objective mission task goal given by",
        campaign_id, limit=15
    )

    active_quests = []
    completed_quests = []
    seen = set()
    for edge in quest_edges:
        # Only include quest-related edges, deduplicate by fact
        name_lower = edge.name.lower()
        fact_lower = edge.fact.lower()
        if name_lower not in ("has_objective", "given_by") and \
           not any(kw in fact_lower for kw in ["quest", "objective", "mission", "find", "retrieve", "rescue", "investigate"]):
            continue
        # Deduplicate similar facts
        short = fact_lower[:60]
        if short in seen:
            continue
        seen.add(short)

        quest_item = {"fact": edge.fact, "type": edge.name}
        if "completed" in fact_lower or "finished" in fact_lower:
            completed_quests.append(quest_item)
        else:
            active_quests.append(quest_item)

    return {
        "active": active_quests,
        "completed": completed_quests,
        "total": len(active_quests) + len(completed_quests),
    }
