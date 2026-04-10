"""
NPC Agent (PMTA — Persistent Motivation-Triggered Agent) for DungeonMasterONE.

Simulates NPC personalities, motivations, and responses during interactions.
Each significant NPC has a motivation graph (goals, fears, opinion of player).

Input: NPC data from knowledge graph + current interaction context
Output: In-character dialogue, opinion changes, emergent event triggers
"""

import logging

from dm1.graph.client import search
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)

NPC_SYSTEM_PROMPT = """You are simulating an NPC in a D&D 5e campaign. Stay in character at all times.

Given the NPC's personality, motivations, and history with the player, generate:
1. In-character dialogue (2-4 lines)
2. An opinion change value (-10 to +10) based on the player's action
3. Any information the NPC would reveal based on their knowledge and trust level

Format your response as:
DIALOGUE: [NPC's spoken words and actions, written in third person: "The innkeeper leans forward..."]
OPINION_CHANGE: [integer from -10 to +10]
REVEALS: [Any new information the NPC shares, or "nothing" if they withhold]"""


async def simulate_npc_interaction(
    npc_name: str,
    player_action: str,
    campaign_id: str,
) -> dict:
    """Simulate an NPC's response to a player interaction.

    Returns: {
        "dialogue": str,
        "opinion_change": int,
        "reveals": str,
    }
    """
    # Get NPC context from knowledge graph
    npc_context = await search(
        f"{npc_name} personality motivations history interactions opinion",
        campaign_id,
        limit=10,
    )
    npc_facts = "\n".join(f"- {e.fact}" for e in npc_context[:8])

    router = get_llm_router()
    response = await router.generate(
        messages=[
            LLMMessage(role="system", content=NPC_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"NPC: {npc_name}\n\nKnown facts about this NPC:\n{npc_facts}\n\nPlayer action: {player_action}",
            ),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.8,
        max_tokens=500,
    )

    return _parse_npc_response(response.content)


def _parse_npc_response(text: str) -> dict:
    """Parse NPC agent output into structured components."""
    dialogue = ""
    opinion_change = 0
    reveals = ""

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("DIALOGUE:"):
            dialogue = line[9:].strip()
        elif line.startswith("OPINION_CHANGE:"):
            try:
                opinion_change = int(line[15:].strip())
                opinion_change = max(-10, min(10, opinion_change))
            except ValueError:
                opinion_change = 0
        elif line.startswith("REVEALS:"):
            reveals = line[8:].strip()

    # If parsing failed, use the whole text as dialogue
    if not dialogue:
        dialogue = text.strip()

    return {
        "dialogue": dialogue,
        "opinion_change": opinion_change,
        "reveals": reveals if reveals.lower() != "nothing" else "",
    }
