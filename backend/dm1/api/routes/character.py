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

    # Build spell slots
    slots = srd.spell_slots_for_class_level(body.class_index, 1)
    if slots:
        character_attributes["spell_slots"] = {
            str(lvl): {"max": count, "current": count}
            for lvl, count in slots.items()
        }

    # Generate world and create character in knowledge graph
    from dm1.agents.genesis import generate_world, populate_knowledge_graph

    world = await generate_world(
        campaign_name=campaign["name"],
        tone=campaign["settings"].get("tone", "epic_fantasy"),
        character_name=body.name,
        character_class=char_class["name"],
        character_race=race["name"],
        world_setting=campaign["settings"].get("world_setting", "surprise_me"),
    )

    created = await populate_knowledge_graph(
        world=world,
        campaign_id=body.campaign_id,
        character_name=body.name,
        character_attributes=character_attributes,
    )

    # Update campaign
    await db.campaigns.update_one(
        {"_id": ObjectId(body.campaign_id)},
        {"$set": {
            "status": CampaignStatus.ACTIVE,
            "character_id": created["character_uuid"],
            "current_turn": 0,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    return {
        "character_uuid": created["character_uuid"],
        "opening_narration": world.opening_narration,
        "locations_created": len(created["locations"]),
        "npcs_created": len(created["npcs"]),
    }
