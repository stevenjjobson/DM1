"""
Archivist Agent for DungeonMasterONE.

The sole writer to the knowledge graph. Responsibilities:
  1. Build context packages for other agents (Narrator, NPC, Storyteller)
  2. Extract entities and relationships from narrative text
  3. Apply structured game state changes (HP, inventory, spell slots)
  4. Maintain graph invariants (temporal edges, no orphan nodes)

Design: structured changes (item pickup, HP) use direct CRUD.
Narrative text uses Graphiti's add_episode() for LLM entity extraction.
"""

import json
import logging

from dm1.graph.client import add_narrative_episode, search
from dm1.graph.mutations import (
    create_quest,
    give_item_to_character,
    move_entity,
    record_event,
    update_character_hp,
    update_npc_opinion,
)
from dm1.graph.queries import build_narrator_context
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)


async def build_context_package(
    campaign_id: str,
    player_action: str,
    location_name: str = "",
) -> dict:
    """Build the context package for the Narrator agent.

    Queries the knowledge graph for current character state, location,
    plot state, and action-relevant context.
    """
    return await build_narrator_context(campaign_id, player_action, location_name)


async def process_narrative(
    campaign_id: str,
    narrative_text: str,
    player_action: str,
    turn_number: int,
) -> dict:
    """Process narrator output — extract entities and update the knowledge graph.

    This is the main post-narration hook. It:
    1. Ingests the narrative as a Graphiti episode (LLM extracts entities)
    2. Uses a fast LLM call to identify structured state changes
    3. Applies those changes via direct CRUD

    Returns a dict of changes made for the turn_complete message.
    """
    changes = {"entities_extracted": False, "state_changes": []}

    # 1. Ingest narrative for entity extraction
    try:
        await add_narrative_episode(
            name=f"Turn {turn_number}",
            narrative_text=f"Player action: {player_action}\n\nDM narration: {narrative_text}",
            group_id=campaign_id,
            turn_number=turn_number,
            source_description="gameplay turn",
        )
        changes["entities_extracted"] = True
    except Exception as e:
        logger.error(f"Failed to ingest narrative episode: {e}")

    # 2. Identify structured state changes via LLM
    try:
        state_changes = await _extract_state_changes(narrative_text, player_action)
        changes["state_changes"] = state_changes

        # 3. Apply changes
        for change in state_changes:
            await _apply_state_change(change, campaign_id, turn_number)
    except Exception as e:
        logger.error(f"Failed to extract/apply state changes: {e}")

    # 4. Record the turn as an event
    try:
        await record_event(
            event_type="turn",
            description=f"Turn {turn_number}: {player_action[:100]}",
            turn_number=turn_number,
            group_id=campaign_id,
        )
    except Exception as e:
        logger.error(f"Failed to record turn event: {e}")

    # 5. Update scene state for narrator continuity
    try:
        await _update_scene_state(campaign_id, narrative_text, player_action)
    except Exception as e:
        logger.error(f"Failed to update scene state: {e}")

    return changes


async def _extract_state_changes(narrative_text: str, player_action: str) -> list[dict]:
    """Use a fast LLM call to identify game state changes from narrative text.

    Returns a list of change dicts like:
    [
        {"type": "hp_change", "amount": -5},
        {"type": "item_acquired", "item": "rusty key", "description": "A small iron key"},
        {"type": "quest_started", "name": "Find the Missing Merchant", "objectives": [...]},
    ]
    """
    router = get_llm_router()

    response = await router.generate(
        messages=[
            LLMMessage(
                role="system",
                content="""Analyze the D&D game narrative and identify any game state changes.
Return a JSON array of changes. Possible change types:
- {"type": "hp_change", "amount": -5} — HP gained or lost
- {"type": "item_acquired", "item": "name", "description": "brief description"}
- {"type": "item_lost", "item": "name"}
- {"type": "quest_started", "name": "quest name", "objectives": ["objective 1", "objective 2"]}
- {"type": "quest_completed", "name": "quest name"}
- {"type": "location_changed", "location": "new location name"}
- {"type": "npc_opinion_changed", "npc": "npc name", "change": 5}
- {"type": "xp_gained", "amount": 100}
- {"type": "condition_applied", "condition": "poisoned"}
- {"type": "condition_removed", "condition": "poisoned"}
- {"type": "spell_cast", "spell": "spell name", "slot_level": 1}
- {"type": "rest", "rest_type": "short" or "long"}

If no state changes occurred, return an empty array: []
Return ONLY the JSON array, no other text.""",
            ),
            LLMMessage(
                role="user",
                content=f"Player action: {player_action}\n\nNarration: {narrative_text}",
            ),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.1,  # Low temperature for structured extraction
        max_tokens=500,
    )

    try:
        changes = json.loads(response.content)
        if isinstance(changes, list):
            return changes
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        text = response.content.strip()
        if text.startswith("["):
            try:
                end = text.rindex("]") + 1
                changes = json.loads(text[:end])
                if isinstance(changes, list):
                    return changes
            except (json.JSONDecodeError, ValueError):
                pass

    logger.warning(f"Failed to parse state changes from LLM response: {response.content[:200]}")
    return []


async def _apply_state_change(change: dict, campaign_id: str, turn_number: int):
    """Apply a single state change to the knowledge graph and MongoDB."""
    from bson import ObjectId
    from dm1.api.database import get_database

    change_type = change.get("type", "")
    db = await get_database()

    # Load character_id for mutations that need it
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    character_id = campaign.get("character_id") if campaign else None

    match change_type:
        case "hp_change":
            amount = change.get("amount", 0)
            if character_id and amount != 0:
                try:
                    await update_character_hp(character_id, amount, campaign_id)
                except Exception:
                    pass
                # Also update MongoDB fallback
                if campaign and campaign.get("character_attrs"):
                    attrs = campaign["character_attrs"]
                    new_hp = max(0, min(attrs.get("max_hp", 0), attrs.get("hp", 0) + amount))
                    await db.campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$set": {"character_attrs.hp": new_hp}},
                    )
            logger.info(f"HP change: {amount}")

        case "item_acquired":
            item_name = change.get("item", "unknown")
            if character_id:
                try:
                    await give_item_to_character(
                        item_name=item_name,
                        item_attributes={"item_type": "found", "description": item_name},
                        character_uuid=character_id,
                        group_id=campaign_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to add item to graph: {e}")
            logger.info(f"Item acquired: {item_name}")

        case "quest_started":
            try:
                await create_quest(
                    quest_name=change.get("name", "Unknown Quest"),
                    description=change.get("name", ""),
                    objectives=change.get("objectives", []),
                    quest_giver_uuid=None,
                    group_id=campaign_id,
                )
                logger.info(f"Quest started: {change.get('name')}")
            except Exception as e:
                logger.error(f"Failed to create quest: {e}")

        case "location_changed":
            new_location = change.get("location", "unknown")
            if character_id:
                try:
                    await move_entity(character_id, new_location, campaign_id)
                except Exception as e:
                    logger.warning(f"Failed to update location in graph: {e}")
            logger.info(f"Location changed to: {new_location}")

        case "npc_opinion_changed":
            npc_name = change.get("npc", "")
            opinion_change = change.get("change", 0)
            if npc_name and opinion_change != 0:
                try:
                    await update_npc_opinion(npc_name, opinion_change, campaign_id)
                except Exception as e:
                    logger.warning(f"Failed to update NPC opinion: {e}")
            logger.info(f"NPC opinion change: {npc_name} by {opinion_change}")

        case "xp_gained":
            amount = change.get("amount", 0)
            if campaign and campaign.get("character_attrs") and amount > 0:
                new_xp = campaign["character_attrs"].get("xp", 0) + amount
                await db.campaigns.update_one(
                    {"_id": ObjectId(campaign_id)},
                    {"$set": {"character_attrs.xp": new_xp}},
                )
            logger.info(f"XP gained: {amount}")

        case "rest":
            rest_type = change.get("rest_type", "short")
            # Restore spell slots on rest
            if campaign and campaign.get("character_attrs", {}).get("spell_slots"):
                if rest_type == "long":
                    slots = campaign["character_attrs"]["spell_slots"]
                    restored = {k: {"max": v["max"], "current": v["max"]} for k, v in slots.items()}
                    await db.campaigns.update_one(
                        {"_id": ObjectId(campaign_id)},
                        {"$set": {"character_attrs.spell_slots": restored}},
                    )
            logger.info(f"Rest: {rest_type}")

        case _:
            logger.info(f"Unhandled state change type: {change_type}")


SCENE_EXTRACTION_PROMPT = """Analyze this D&D narrative and extract the current scene state. Return JSON only.

{
  "location": "name of the current location the player is in",
  "description": "1-sentence description of the location",
  "npcs_present": ["list", "of", "NPC", "names", "currently", "in", "scene"],
  "atmosphere": "one word: calm, tense, dangerous, mysterious, festive, eerie",
  "summary": "2-3 sentence summary of what just happened this turn"
}"""


async def _update_scene_state(campaign_id: str, narrative_text: str, player_action: str):
    """Extract scene state from narrative and persist to MongoDB for turn continuity."""
    from bson import ObjectId
    from dm1.api.database import get_database

    router = get_llm_router()

    response = await router.generate(
        messages=[
            LLMMessage(role="system", content=SCENE_EXTRACTION_PROMPT),
            LLMMessage(role="user", content=f"Narrative:\n{narrative_text[:1500]}\n\nPlayer action: {player_action}"),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.1,
        max_tokens=300,
    )

    try:
        # Parse JSON from response (strip markdown fences if present)
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        scene_data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        # Fallback: store just the narrative summary
        scene_data = {"summary": narrative_text[:300]}
        logger.warning("Failed to parse scene extraction, using fallback")

    scene = {
        "location": scene_data.get("location", ""),
        "description": scene_data.get("description", ""),
        "npcs_present": scene_data.get("npcs_present", []),
        "atmosphere": scene_data.get("atmosphere", ""),
        "last_narrative": scene_data.get("summary", narrative_text[:300]),
        "last_player_action": player_action[:200],
    }

    db = await get_database()
    await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {"scene": scene}},
    )
    logger.info(f"Scene state updated: location={scene['location']}, npcs={len(scene['npcs_present'])}")
