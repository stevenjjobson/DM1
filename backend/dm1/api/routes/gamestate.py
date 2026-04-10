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
    graph_node_name = None
    if character_id:
        try:
            node = await get_node_by_uuid(character_id)
            if node:
                graph_node_name = node.name  # Graphiti node name (character name)
                if node.attributes:
                    character_data = node.attributes
        except Exception:
            pass

    # Fallback: check if character data was stored in the campaign doc
    if not character_data and campaign.get("character_attrs"):
        character_data = campaign["character_attrs"]

    # World Knowledge: key people, places, and things discovered during play.
    # Suppressed until turn 3+ — genesis creates graph edges that shouldn't
    # appear before the DM introduces them in narration.
    current_turn = campaign.get("current_turn", 0)
    graph_facts = []
    if current_turn >= 3:
        try:
            results = await search(
                "NPC met spoke with location visited discovered tavern village dungeon found learned",
                campaign_id, limit=20
            )
            # Filter out internal quest structure edges and deduplicate
            skip_prefixes = ["quest given", "quest objective", "has_objective", "given_by"]
            seen = set()
            for edge in results:
                fact_lower = edge.fact.lower()
                # Skip quest scaffolding — these are internal graph structure
                if any(fact_lower.startswith(p) for p in skip_prefixes):
                    continue
                # Skip very short or generic edges
                if len(edge.fact) < 15:
                    continue
                # Deduplicate
                key = fact_lower[:50]
                if key in seen:
                    continue
                seen.add(key)
                graph_facts.append(edge)
                if len(graph_facts) >= 8:
                    break
        except Exception:
            pass

    # Build structured character sheet
    abilities = character_data.get("abilities", {})
    level = character_data.get("level", 1)
    prof = proficiency_bonus(level)

    modifiers = {k: ability_modifier(v) for k, v in abilities.items()} if abilities else {}

    # Hit dice info
    hit_die_type = character_data.get("hit_die_type", "d8")
    hit_dice_current = character_data.get("hit_dice_current", level)
    hit_dice_total = character_data.get("hit_dice_total", level)

    return {
        "name": character_data.get("name") or graph_node_name or campaign.get("name", "Adventurer"),
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
        "hit_die": hit_die_type,
        "hit_dice": f"{hit_dice_current}/{hit_dice_total} {hit_die_type}",
        "conditions": character_data.get("conditions", []),
        "proficiencies": character_data.get("proficiencies", []),
        "background": character_data.get("background", ""),
        "backstory": character_data.get("backstory", ""),
        "current_turn": campaign.get("current_turn", 0),
        "portrait_url": f"/api/assets/campaigns/{campaign_id}/{campaign.get('portrait_filename')}" if campaign.get("portrait_filename") else None,
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

    # Get starting equipment from campaign data (reliable fallback)
    character_attrs = campaign.get("character_attrs", {})
    stored_equipment = character_attrs.get("equipment", [])

    # Load SRD for item details
    srd = None
    try:
        from dm1.rules.srd_repository import SRDRepository
        srd = SRDRepository.get()
    except Exception:
        pass

    items = []
    seen_names = set()
    gold = 0

    # First: show stored starting equipment
    for equip in stored_equipment:
        name = equip.get("name", "Unknown")
        index = equip.get("index", "")
        qty = equip.get("quantity", 1)

        # Track gold separately
        if index == "gp" or name.lower() == "gold pieces":
            gold += qty
            continue

        if name not in seen_names:
            seen_names.add(name)
            item_entry = {
                "name": name,
                "index": index,
                "quantity": qty,
                "source": "starting",
                "category": "gear",
                "weight": 0,
            }
            # Enrich from SRD
            if srd and index:
                srd_item = srd.get_equipment(index)
                if srd_item:
                    cat = srd_item.get("equipment_category", {}).get("index", "gear")
                    item_entry["category"] = cat
                    item_entry["weight"] = srd_item.get("weight", 0)
                    if "damage" in srd_item:
                        item_entry["damage"] = srd_item["damage"].get("damage_dice", "")
                    if "armor_class" in srd_item:
                        ac_data = srd_item["armor_class"]
                        item_entry["ac_bonus"] = ac_data.get("base", 0)
            items.append(item_entry)

    # Then: add any items found in the knowledge graph (acquired during play)
    try:
        item_edges = await search(
            "player owns carries acquired found picked up",
            campaign_id, limit=10
        )
        for edge in item_edges:
            fact_lower = edge.fact.lower()
            if any(kw in fact_lower for kw in ["owns", "owned", "acquired", "picked up", "found", "received"]):
                # Avoid duplicating starting equipment
                if not any(s.lower() in fact_lower for s in seen_names):
                    items.append({
                        "name": edge.fact,
                        "index": "",
                        "quantity": 1,
                        "source": "found",
                        "category": "gear",
                        "weight": 0,
                    })
    except Exception:
        pass

    total_weight = sum(i.get("weight", 0) * i.get("quantity", 1) for i in items)

    return {"items": items, "total": len(items), "gold": gold, "total_weight": total_weight}


@router.get("/{campaign_id}/spellbook")
async def get_spellbook(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get the character's spellbook from character attrs + knowledge graph."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    character_attrs = campaign.get("character_attrs", {})

    # Spell slots from character attrs (most reliable) or graph node
    spell_slots = character_attrs.get("spell_slots", {})
    if not spell_slots:
        character_id = campaign.get("character_id")
        if character_id:
            try:
                node = await get_node_by_uuid(character_id)
                if node and node.attributes:
                    spell_slots = node.attributes.get("spell_slots", {})
            except Exception:
                pass

    # Build spell list from stored cantrips + spells (set at character creation)
    srd = None
    try:
        from dm1.rules.srd_repository import SRDRepository
        srd = SRDRepository.get()
    except Exception:
        pass

    cantrips = []
    for spell_index in character_attrs.get("known_cantrips", []):
        spell_data = srd.get_spell(spell_index) if srd else None
        cantrips.append({
            "index": spell_index,
            "name": spell_data["name"] if spell_data else spell_index.replace("-", " ").title(),
            "level": 0,
            "school": spell_data.get("school", {}).get("name", "") if spell_data else "",
        })

    spells = []
    for spell_index in character_attrs.get("known_spells", []):
        spell_data = srd.get_spell(spell_index) if srd else None
        spells.append({
            "index": spell_index,
            "name": spell_data["name"] if spell_data else spell_index.replace("-", " ").title(),
            "level": spell_data.get("level", 1) if spell_data else 1,
            "school": spell_data.get("school", {}).get("name", "") if spell_data else "",
        })

    # Also check graph for spells acquired during play
    try:
        spell_edges = await search(
            "learned spell acquired new cantrip",
            campaign_id, limit=10
        )
        seen = {s["index"] for s in cantrips + spells}
        for edge in spell_edges:
            if any(kw in edge.fact.lower() for kw in ["learned", "acquired", "new spell"]):
                if edge.fact not in seen:
                    spells.append({"index": "", "name": edge.fact, "level": -1, "school": ""})
    except Exception:
        pass

    return {
        "cantrips": cantrips,
        "spells": spells,
        "spell_slots": spell_slots,
        "total": len(cantrips) + len(spells),
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

    # Don't show quests until the DM has introduced the world (after turn 2+)
    # Genesis pre-creates quest hooks but they shouldn't appear before the DM reveals them
    current_turn = campaign.get("current_turn", 0)
    if current_turn < 2:
        return {"active": [], "completed": [], "total": 0}

    # Search for quest structure edges
    quest_edges = await search(
        "quest objective mission task goal given by",
        campaign_id, limit=15
    )

    active_quests = []
    completed_quests = []
    seen = set()
    for edge in quest_edges:
        name_lower = edge.name.lower()
        fact_lower = edge.fact.lower()
        if name_lower not in ("has_objective", "given_by") and \
           not any(kw in fact_lower for kw in ["quest", "objective", "mission", "find", "retrieve", "rescue", "investigate"]):
            continue
        # Deduplicate
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
