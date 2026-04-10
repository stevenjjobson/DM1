"""
Genesis Prompt System for DungeonMasterONE.

Creates the initial world state when a campaign is started. Uses structured
output (JSON mode) to generate a parseable world definition, then populates
the knowledge graph with locations, NPCs, and quest hooks.
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel

from dm1.graph.mutations import (
    create_character,
    create_location,
    create_npc,
    create_quest,
)
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Output Schema
# ---------------------------------------------------------------------------

class GenesisNPC(BaseModel):
    name: str
    race: str
    role: str
    personality: str
    description: str
    location: str  # References a location name from the same output


class GenesisLocation(BaseModel):
    name: str
    location_type: str
    description: str
    connections: list[str]  # Names of connected locations


class GenesisQuestHook(BaseModel):
    name: str
    description: str
    objectives: list[str]
    quest_giver: str  # NPC name


class GenesisWorld(BaseModel):
    opening_narration: str
    starting_location: str  # Name of the starting location
    locations: list[GenesisLocation]
    npcs: list[GenesisNPC]
    quest_hooks: list[GenesisQuestHook]


# ---------------------------------------------------------------------------
# World Generation
# ---------------------------------------------------------------------------

GENESIS_SYSTEM_PROMPT = """You are a world-building assistant for a D&D 5e campaign. Generate a starting world based on the player's preferences.

Create a small, playable starting area with:
- 3-4 interconnected locations (a hub location + 2-3 adjacent areas)
- 3-5 NPCs with distinct personalities and motivations
- 1-2 quest hooks to get the adventure started
- An atmospheric opening narration (2-3 paragraphs, second person)

The world should feel lived-in and reactive. NPCs should have clear motivations that create potential for emergent story. Quest hooks should arise naturally from the setting.

Return your response as a JSON object matching the provided schema exactly."""


async def generate_world(
    campaign_name: str,
    tone: str,
    character_name: str = "the adventurer",
    character_class: str = "adventurer",
    character_race: str = "human",
    world_setting: str = "surprise_me",
) -> GenesisWorld:
    """Generate a starting world from campaign settings using structured output."""
    router = get_llm_router()

    tone_descriptions = {
        "epic_fantasy": "High fantasy with grand quests, ancient magic, and legendary heroes.",
        "dark_gritty": "Low fantasy with moral ambiguity, scarce magic, and harsh consequences.",
        "lighthearted": "Fun and whimsical with humor, quirky NPCs, and low stakes.",
        "horror": "Creeping dread, hidden horrors, and a sense of wrongness beneath the surface.",
        "mystery": "Intrigue, clues, red herrings, and a central mystery to unravel.",
    }
    tone_desc = tone_descriptions.get(tone, "A classic fantasy adventure.")

    prompt = f"""Campaign: {campaign_name}
Tone: {tone_desc}
Player Character: {character_name}, a {character_race} {character_class}
World Setting: {world_setting}

Generate the starting world. Make it immediately playable — the player should have
something interesting to do from the very first turn."""

    response = await router.generate(
        messages=[
            LLMMessage(role="system", content=GENESIS_SYSTEM_PROMPT),
            LLMMessage(role="user", content=prompt),
        ],
        model_role=ModelRole.GENESIS,
        temperature=0.9,
        max_tokens=4000,
        response_schema=GenesisWorld,
    )

    try:
        world = GenesisWorld.model_validate_json(response.content)
    except Exception as e:
        logger.error(f"Failed to parse genesis output: {e}")
        logger.error(f"Raw output: {response.content[:500]}")
        # Fallback: minimal world
        world = _create_fallback_world(character_name)

    return world


async def populate_knowledge_graph(
    world: GenesisWorld,
    campaign_id: str,
    character_name: str,
    character_attributes: dict,
) -> dict:
    """Populate the knowledge graph with the generated world.

    Returns a dict of created entity UUIDs for reference.
    """
    created = {"locations": {}, "npcs": {}, "quests": [], "character_uuid": None}

    # 1. Create locations
    for loc in world.locations:
        uuid = await create_location(
            name=loc.name,
            attributes={
                "location_type": loc.location_type,
                "description": loc.description,
                "discovered_at_turn": 0,
            },
            group_id=campaign_id,
        )
        created["locations"][loc.name] = uuid

    # 2. Connect locations
    for loc in world.locations:
        for conn_name in loc.connections:
            if conn_name in created["locations"] and loc.name in created["locations"]:
                from dm1.graph.client import create_edge
                from dm1.graph.schema import EdgeType

                await create_edge(
                    source_uuid=created["locations"][loc.name],
                    target_uuid=created["locations"][conn_name],
                    edge_type=EdgeType.CONNECTED_TO,
                    fact=f"{loc.name} is connected to {conn_name}",
                    group_id=campaign_id,
                )

    # 3. Create player character at starting location
    starting_loc_uuid = created["locations"].get(world.starting_location)
    character_uuid = await create_character(
        name=character_name,
        attributes=character_attributes,
        group_id=campaign_id,
        starting_location_uuid=starting_loc_uuid,
    )
    created["character_uuid"] = character_uuid

    # 4. Create NPCs at their locations
    for npc in world.npcs:
        npc_loc_uuid = created["locations"].get(npc.location)
        uuid = await create_npc(
            name=npc.name,
            attributes={
                "race": npc.race,
                "role": npc.role,
                "personality": npc.personality,
                "motivations": [],
                "opinion_of_player": 0,
            },
            group_id=campaign_id,
            location_uuid=npc_loc_uuid,
        )
        created["npcs"][npc.name] = uuid

    # 5. Create quest hooks (hidden until DM introduces them in narration)
    for quest in world.quest_hooks:
        quest_giver_uuid = created["npcs"].get(quest.quest_giver)
        quest_uuid = await create_quest(
            quest_name=quest.name,
            description=quest.description,
            objectives=quest.objectives,
            quest_giver_uuid=quest_giver_uuid,
            group_id=campaign_id,
            revealed=False,
        )
        created["quests"].append(quest_uuid)

    logger.info(
        f"Genesis populated: {len(created['locations'])} locations, "
        f"{len(created['npcs'])} NPCs, {len(created['quests'])} quests"
    )

    return created


def _create_fallback_world(character_name: str) -> GenesisWorld:
    """Minimal fallback world if genesis prompt fails."""
    return GenesisWorld(
        opening_narration=(
            f"You find yourself standing at the edge of a small village as dawn breaks over the horizon. "
            f"The scent of fresh bread drifts from a nearby bakery, and the sound of a blacksmith's hammer "
            f"rings through the crisp morning air. A weathered signpost reads 'Millhaven — Population: 247'. "
            f"Something tells you this quiet place holds more secrets than it lets on."
        ),
        starting_location="Millhaven Village Square",
        locations=[
            GenesisLocation(
                name="Millhaven Village Square",
                location_type="village",
                description="A small cobblestone square at the heart of the village, with a well, a notice board, and a few market stalls.",
                connections=["The Rusty Tankard", "Village Outskirts"],
            ),
            GenesisLocation(
                name="The Rusty Tankard",
                location_type="tavern",
                description="A warm, dimly lit tavern with low ceilings and the smell of ale. The innkeeper watches newcomers with guarded curiosity.",
                connections=["Millhaven Village Square"],
            ),
            GenesisLocation(
                name="Village Outskirts",
                location_type="wilderness",
                description="Rolling hills and dense forest border the village. A dirt path leads north toward the mountains.",
                connections=["Millhaven Village Square"],
            ),
        ],
        npcs=[
            GenesisNPC(
                name="Greta Ironhands",
                race="Dwarf",
                role="innkeeper",
                personality="Gruff but warm. Protective of the village. Knows everyone's secrets.",
                description="A stout dwarf woman with calloused hands and a no-nonsense demeanor.",
                location="The Rusty Tankard",
            ),
            GenesisNPC(
                name="Tomas the Elder",
                race="Human",
                role="village_elder",
                personality="Worried and cautious. Carries the weight of the village's problems.",
                description="An elderly man with kind eyes and trembling hands.",
                location="Millhaven Village Square",
            ),
        ],
        quest_hooks=[
            GenesisQuestHook(
                name="The Missing Shepherd",
                description="A shepherd has gone missing in the hills north of the village. His flock was found scattered and bloodied.",
                objectives=["Speak to Tomas the Elder about the missing shepherd", "Search the northern hills"],
                quest_giver="Tomas the Elder",
            ),
        ],
    )
