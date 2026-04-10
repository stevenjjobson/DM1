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
from dm1.graph.client import search
from dm1.rules.dice import ability_modifier, proficiency_bonus
from dm1.rules.skills import SKILL_ABILITIES

router = APIRouter(prefix="/gamestate", tags=["gamestate"])


@router.get("/{campaign_id}/character")
async def get_character_sheet(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the full character sheet for a campaign."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get character data from graph context
    edges = await search("player character stats abilities level class race", campaign_id, limit=10)

    # For now, return campaign-stored character info
    # In full implementation, this would query the Character node from Neo4j
    character_id = campaign.get("character_id")

    # Build character sheet from campaign metadata + graph
    # This is a simplified version — full implementation queries the knowledge graph node
    return {
        "campaign_id": campaign_id,
        "character_id": character_id,
        "name": campaign.get("name", "Adventurer"),
        "status": campaign.get("status"),
        "current_turn": campaign.get("current_turn", 0),
        "graph_facts": [{"fact": e.fact, "name": e.name} for e in edges[:10]],
    }


@router.get("/{campaign_id}/inventory")
async def get_inventory(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the character's inventory (items with active OWNED_BY edges)."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    edges = await search("items equipment weapons armor potions inventory owned carried", campaign_id, limit=20)

    return {
        "items": [
            {"fact": e.fact, "name": e.name, "uuid": e.uuid}
            for e in edges
            if "owned" in e.fact.lower() or "item" in e.name.lower() or "equip" in e.name.lower()
        ],
    }


@router.get("/{campaign_id}/spellbook")
async def get_spellbook(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the character's known spells and slot status."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    edges = await search("spells known prepared cantrips magic spell slots", campaign_id, limit=20)

    return {
        "spells": [
            {"fact": e.fact, "name": e.name, "uuid": e.uuid}
            for e in edges
            if "spell" in e.fact.lower() or "spell" in e.name.lower()
        ],
    }


@router.get("/{campaign_id}/quests")
async def get_quest_log(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get active and completed quests."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    edges = await search("quests objectives goals missions active completed", campaign_id, limit=20)

    return {
        "quests": [
            {"fact": e.fact, "name": e.name, "uuid": e.uuid}
            for e in edges
        ],
    }
