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
    """Apply a single state change to the knowledge graph."""
    change_type = change.get("type", "")

    match change_type:
        case "hp_change":
            # Would need character UUID — for now, log it
            logger.info(f"HP change: {change.get('amount', 0)}")

        case "item_acquired":
            logger.info(f"Item acquired: {change.get('item', 'unknown')}")

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
            logger.info(f"Location changed to: {change.get('location', 'unknown')}")

        case "npc_opinion_changed":
            logger.info(f"NPC opinion change: {change.get('npc')} by {change.get('change', 0)}")

        case "xp_gained":
            logger.info(f"XP gained: {change.get('amount', 0)}")

        case "rest":
            logger.info(f"Rest: {change.get('rest_type', 'short')}")

        case _:
            logger.info(f"Unhandled state change type: {change_type}")
