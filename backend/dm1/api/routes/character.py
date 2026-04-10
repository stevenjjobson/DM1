"""
Character creation API for DungeonMasterONE.

Validates character build choices and finalizes character creation,
writing the complete character to the knowledge graph.
"""

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from dm1.api.database import get_database
from dm1.graph.mutations import give_item_to_character
from dm1.api.middleware.auth import get_current_user_id
from dm1.models.campaign import CampaignStatus
from dm1.rules.dice import ability_modifier, proficiency_bonus, validate_point_buy
from dm1.rules.srd_repository import SRDRepository

router = APIRouter(prefix="/character", tags=["character"])


class AbilityScoreAssignment(BaseModel):
    strength: int = Field(ge=1, le=30)
    dexterity: int = Field(ge=1, le=30)
    constitution: int = Field(ge=1, le=30)
    intelligence: int = Field(ge=1, le=30)
    wisdom: int = Field(ge=1, le=30)
    charisma: int = Field(ge=1, le=30)


class CharacterCreateRequest(BaseModel):
    campaign_id: str
    name: str = Field(min_length=2, max_length=50)
    race_index: str
    subrace_index: str | None = None
    class_index: str
    background_index: str = "acolyte"
    abilities: AbilityScoreAssignment
    selected_skills: list[str] = []
    selected_spells: list[str] = []
    backstory: str = ""
    appearance: dict = {}  # Hair, eyes, skin, etc. — feeds Binding Contract


class CharacterPreview(BaseModel):
    """Computed character sheet preview for the review step."""
    name: str
    race: str
    char_class: str
    level: int = 1
    hp: int
    ac: int
    speed: int
    proficiency_bonus: int
    abilities: dict[str, int]
    modifiers: dict[str, int]
    saving_throws: dict[str, int]
    skills: dict[str, int]
    proficient_saves: list[str]
    proficient_skills: list[str]
    selected_spells: list[str]


@router.post("/{campaign_id}/generate-portrait")
async def generate_portrait_on_demand(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Generate or regenerate a character portrait for an active campaign."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    character_attrs = campaign.get("character_attrs", {})
    if not character_attrs:
        raise HTTPException(status_code=400, detail="No character data found")

    import asyncio
    asyncio.create_task(_generate_portrait(
        character_name=character_attrs.get("name", "Adventurer"),
        race_name=character_attrs.get("race", "Human"),
        class_name=character_attrs.get("char_class", "Fighter"),
        appearance=character_attrs.get("binding_contract", {}),
        campaign_id=campaign_id,
        campaign_tone=campaign.get("settings", {}).get("tone", "epic_fantasy"),
    ))

    return {"status": "generating", "message": "Portrait generation started. Refresh in a few moments."}


@router.post("/preview", response_model=CharacterPreview)
async def preview_character(
    body: CharacterCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Compute a full character sheet preview from the build choices.

    Used in the Review step of the wizard to show the final character before confirming.
    """
    srd = SRDRepository.get()

    # Validate race
    race = srd.get_race(body.race_index)
    if not race:
        raise HTTPException(status_code=400, detail=f"Unknown race: {body.race_index}")

    # Validate class
    char_class = srd.get_class(body.class_index)
    if not char_class:
        raise HTTPException(status_code=400, detail=f"Unknown class: {body.class_index}")

    # Apply racial ability bonuses
    abilities = body.abilities.model_dump()
    for bonus in race.get("ability_bonuses", []):
        ability_key = bonus["ability_score"]["index"]
        # Map SRD index (e.g., "str") to full name
        ability_map = {"str": "strength", "dex": "dexterity", "con": "constitution",
                       "int": "intelligence", "wis": "wisdom", "cha": "charisma"}
        full_name = ability_map.get(ability_key, ability_key)
        if full_name in abilities:
            abilities[full_name] += bonus["bonus"]

    # Apply subrace bonuses
    if body.subrace_index:
        subrace = srd.get_subrace(body.subrace_index)
        if subrace:
            for bonus in subrace.get("ability_bonuses", []):
                ability_key = bonus["ability_score"]["index"]
                full_name = ability_map.get(ability_key, ability_key)
                if full_name in abilities:
                    abilities[full_name] += bonus["bonus"]

    # Calculate modifiers
    modifiers = {k: ability_modifier(v) for k, v in abilities.items()}

    # HP at level 1: max hit die + CON modifier
    hp = char_class["hit_die"] + modifiers["constitution"]

    # AC: 10 + DEX modifier (no armor)
    ac = 10 + modifiers["dexterity"]

    # Speed from race
    speed = race.get("speed", 30)

    # Proficiency bonus at level 1
    prof = proficiency_bonus(1)

    # Saving throw proficiencies
    proficient_saves = [st["index"] for st in char_class.get("saving_throws", [])]

    # Calculate saving throws
    save_map = {"str": "strength", "dex": "dexterity", "con": "constitution",
                "int": "intelligence", "wis": "wisdom", "cha": "charisma"}
    saving_throws = {}
    for save_idx, ability_name in save_map.items():
        mod = modifiers[ability_name]
        if save_idx in proficient_saves:
            mod += prof
        saving_throws[save_idx] = mod

    # Calculate skill modifiers
    from dm1.rules.skills import SKILL_ABILITIES
    skills = {}
    for skill_idx, ability_name in SKILL_ABILITIES.items():
        mod = modifiers.get(ability_name, 0)
        if skill_idx in body.selected_skills:
            mod += prof
        skills[skill_idx] = mod

    return CharacterPreview(
        name=body.name,
        race=race["name"],
        char_class=char_class["name"],
        level=1,
        hp=max(1, hp),
        ac=ac,
        speed=speed,
        proficiency_bonus=prof,
        abilities=abilities,
        modifiers=modifiers,
        saving_throws=saving_throws,
        skills=skills,
        proficient_saves=proficient_saves,
        proficient_skills=body.selected_skills,
        selected_spells=body.selected_spells,
    )


@router.post("/create")
async def create_character(
    body: CharacterCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Finalize character creation and write to the knowledge graph.

    Also starts the campaign (genesis) if not already started.
    """
    # Verify campaign
    campaign = await db.campaigns.find_one({"_id": ObjectId(body.campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Compute the preview (validates everything)
    srd = SRDRepository.get()
    race = srd.get_race(body.race_index)
    char_class = srd.get_class(body.class_index)

    # Build character attributes for knowledge graph
    abilities = body.abilities.model_dump()
    for bonus in race.get("ability_bonuses", []):
        ability_map = {"str": "strength", "dex": "dexterity", "con": "constitution",
                       "int": "intelligence", "wis": "wisdom", "cha": "charisma"}
        full_name = ability_map.get(bonus["ability_score"]["index"], bonus["ability_score"]["index"])
        if full_name in abilities:
            abilities[full_name] += bonus["bonus"]

    modifiers = {k: ability_modifier(v) for k, v in abilities.items()}
    hp = max(1, char_class["hit_die"] + modifiers["constitution"])

    character_attributes = {
        "name": body.name,
        "race": race["name"],
        "char_class": char_class["name"],
        "level": 1,
        "xp": 0,
        "hp": hp,
        "max_hp": hp,
        "ac": 10 + modifiers["dexterity"],
        "speed": race.get("speed", 30),
        "proficiency_bonus": 2,
        "abilities": abilities,
        "hit_dice_total": 1,
        "hit_dice_current": 1,
        "hit_die_type": f"d{char_class['hit_die']}",
        "proficiencies": body.selected_skills,
        "background": body.background_index,
        "backstory": body.backstory,
        "binding_contract": body.appearance,
    }

    # Store selected spells (cantrips vs. leveled)
    if body.selected_spells:
        character_attributes["known_cantrips"] = [
            s for s in body.selected_spells
            if (spell := srd.get_spell(s)) and spell.get("level") == 0
        ]
        character_attributes["known_spells"] = [
            s for s in body.selected_spells
            if (spell := srd.get_spell(s)) and spell.get("level", 0) > 0
        ]

    # Build spell slots
    slots = srd.spell_slots_for_class_level(body.class_index, 1)
    if slots:
        character_attributes["spell_slots"] = {
            str(lvl): {"max": count, "current": count}
            for lvl, count in slots.items()
        }

    # Build starting equipment from SRD class data
    starting_items = _get_starting_equipment(srd, body.class_index)
    character_attributes["equipment"] = starting_items

    # Generate world and create character in knowledge graph
    from dm1.agents.genesis import generate_world, populate_knowledge_graph

    world = await generate_world(
        campaign_name=campaign["name"],
        tone=campaign["settings"].get("tone", "epic_fantasy"),
        character_name=body.name,
        character_class=char_class["name"],
        character_race=race["name"],
        world_setting=campaign["settings"].get("world_setting", "surprise_me"),
        backstory=body.backstory,
        background=body.background_index,
    )

    created = await populate_knowledge_graph(
        world=world,
        campaign_id=body.campaign_id,
        character_name=body.name,
        character_attributes=character_attributes,
    )

    # Initialize scene state from genesis world
    starting_loc = next(
        (loc for loc in world.locations if loc.name == world.starting_location),
        world.locations[0] if world.locations else None,
    )
    scene = {
        "location": world.starting_location,
        "description": starting_loc.description if starting_loc else "",
        "npcs_present": [
            npc.name for npc in world.npcs
            if npc.location == world.starting_location
        ],
        "atmosphere": "calm",
        "last_narrative": world.opening_narration[:500],
        "last_player_action": "",
    }

    # Update campaign — store character attrs + scene state
    await db.campaigns.update_one(
        {"_id": ObjectId(body.campaign_id)},
        {"$set": {
            "status": CampaignStatus.ACTIVE,
            "character_id": created["character_uuid"],
            "character_attrs": character_attributes,
            "scene": scene,
            "current_turn": 0,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    # Create starting equipment as graph nodes (background)
    import asyncio
    asyncio.create_task(_create_equipment_nodes(
        starting_items, created["character_uuid"], body.campaign_id
    ))

    # Generate character portrait (background — doesn't block response)
    asyncio.create_task(_generate_portrait(
        character_name=body.name,
        race_name=race["name"],
        class_name=char_class["name"],
        appearance=body.appearance,
        campaign_id=body.campaign_id,
        campaign_tone=campaign["settings"].get("tone", "epic_fantasy"),
    ))

    return {
        "character_uuid": created["character_uuid"],
        "opening_narration": world.opening_narration,
        "locations_created": len(created["locations"]),
        "npcs_created": len(created["npcs"]),
    }


def _get_starting_equipment(srd: SRDRepository, class_index: str) -> list[dict]:
    """Get default starting equipment for a class from SRD data."""
    cls = srd.get_class(class_index)
    if not cls:
        return []

    items = []
    # Fixed starting equipment
    for entry in cls.get("starting_equipment", []):
        equip = entry.get("equipment", {})
        items.append({
            "name": equip.get("name", "Unknown item"),
            "index": equip.get("index", ""),
            "quantity": entry.get("quantity", 1),
        })

    # If no fixed equipment, build defaults from the first option of each choice
    if not items:
        for option_set in cls.get("starting_equipment_options", []):
            options = option_set.get("from", {}).get("options", [])
            if options:
                first = options[0]
                if first.get("option_type") == "counted_reference":
                    equip = first.get("of", {})
                    items.append({
                        "name": equip.get("name", "Equipment"),
                        "index": equip.get("index", ""),
                        "quantity": first.get("count", 1),
                    })
                elif first.get("option_type") == "multiple":
                    for sub in first.get("items", []):
                        equip = sub.get("of", sub.get("option", {}))
                        items.append({
                            "name": equip.get("name", "Equipment"),
                            "index": equip.get("index", ""),
                            "quantity": sub.get("count", 1),
                        })

    # Always include an explorer's pack and gold
    if not any(i["name"].lower() == "explorer's pack" for i in items):
        items.append({"name": "Explorer's Pack", "index": "explorers-pack", "quantity": 1})
    items.append({"name": "Gold Pieces", "index": "gp", "quantity": 15})

    return items


async def _create_equipment_nodes(items: list[dict], character_uuid: str, campaign_id: str):
    """Background task: create item nodes in the knowledge graph."""
    try:
        for item in items:
            await give_item_to_character(
                item_name=item["name"],
                item_attributes={
                    "item_type": "equipment",
                    "quantity": item.get("quantity", 1),
                    "description": item["name"],
                },
                character_uuid=character_uuid,
                group_id=campaign_id,
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to create equipment nodes: {e}")


async def _generate_portrait(
    character_name: str,
    race_name: str,
    class_name: str,
    appearance: dict,
    campaign_id: str,
    campaign_tone: str = "epic_fantasy",
):
    """Background task: generate character portrait via Nano Banana 2."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        from dm1.providers.image.imagen import generate_character_portrait

        # Build portrait prompt from appearance data
        appearance_parts = []
        if appearance.get("hair"):
            appearance_parts.append(f"{appearance['hair']} hair")
        if appearance.get("eyes"):
            appearance_parts.append(f"{appearance['eyes']} eyes")
        if appearance.get("skin"):
            appearance_parts.append(f"{appearance['skin']} skin")
        if appearance.get("build"):
            appearance_parts.append(f"{appearance['build']} build")
        if appearance.get("distinguishing"):
            appearance_parts.append(appearance["distinguishing"])

        appearance_desc = ", ".join(appearance_parts) if appearance_parts else "no specific details"

        tone_styles = {
            "epic_fantasy": "fantasy art portrait, vibrant, heroic lighting",
            "dark_gritty": "dark fantasy portrait, muted tones, harsh shadows",
            "lighthearted": "whimsical fantasy portrait, bright colors, friendly",
            "horror": "dark portrait, unsettling atmosphere, pale lighting",
            "mystery": "noir-inspired portrait, dramatic contrast, moody",
        }
        style = tone_styles.get(campaign_tone, "fantasy character portrait")

        prompt = (
            f"D&D character portrait of {character_name}, a {race_name} {class_name}. "
            f"Appearance: {appearance_desc}. "
            f"Style: {style}. Head and shoulders composition, detailed face."
        )

        result = await generate_character_portrait(
            prompt=prompt,
            campaign_id=campaign_id,
        )

        if result:
            # Store portrait path in campaign document
            from dm1.api.database import get_database
            db = await get_database()
            await db.campaigns.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"portrait_filename": result["filename"]}},
            )
            logger.info(f"Portrait generated for {character_name}: {result['filename']}")
        else:
            logger.warning(f"Portrait generation returned no result for {character_name}")

    except Exception as e:
        logger.error(f"Portrait generation failed for {character_name}: {e}")
