"""
Storyteller Agent for DungeonMasterONE.

Manages long-term narrative arcs, pacing, and quest generation.
The Storyteller monitors gameplay and injects events when:
- The pace is too slow (exploration stagnates)
- A plot arc needs advancement
- A quest milestone is reached

Input: Plot graph state, recent events, player behavior patterns
Output: Pacing events, quest structures, milestone triggers
"""

import logging

from dm1.graph.client import search
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)

STORYTELLER_SYSTEM_PROMPT = """You are a story pacing analyst for a D&D campaign. Your job is to evaluate the current state of the story and decide if any pacing intervention is needed.

Analyze the recent events and determine:
1. PACING_STATUS: "good" (story is flowing naturally), "slow" (needs injection), or "climactic" (approaching a key moment)
2. SUGGESTED_EVENT: If pacing is slow, describe a brief event to inject (an encounter, a discovery, a complication). If pacing is good, say "none".
3. QUEST_UPDATE: If any quest progress should be noted, describe it. Otherwise "none".

Keep your analysis brief and actionable."""


async def evaluate_pacing(campaign_id: str, recent_turns: int = 5) -> dict:
    """Evaluate story pacing and suggest interventions if needed.

    Returns: {
        "pacing_status": "good" | "slow" | "climactic",
        "suggested_event": str | None,
        "quest_update": str | None,
    }
    """
    # Get recent events from knowledge graph
    recent = await search(
        "recent events encounters discoveries conversations turns",
        campaign_id,
        limit=recent_turns * 2,
    )
    recent_facts = "\n".join(f"- {e.fact}" for e in recent[:10])

    # Get active quests
    quests = await search("active quests objectives goals progress", campaign_id, limit=5)
    quest_facts = "\n".join(f"- {e.fact}" for e in quests[:5])

    router = get_llm_router()
    response = await router.generate(
        messages=[
            LLMMessage(role="system", content=STORYTELLER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"Recent events (last {recent_turns} turns):\n{recent_facts}\n\nActive quests:\n{quest_facts}",
            ),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.7,
        max_tokens=300,
    )

    return _parse_storyteller_response(response.content)


def _parse_storyteller_response(text: str) -> dict:
    """Parse storyteller evaluation into structured components."""
    pacing_status = "good"
    suggested_event = None
    quest_update = None

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("PACING_STATUS:"):
            status = line[14:].strip().lower().strip('"')
            if status in ("good", "slow", "climactic"):
                pacing_status = status
        elif line.startswith("SUGGESTED_EVENT:"):
            event = line[16:].strip()
            if event.lower() != "none":
                suggested_event = event
        elif line.startswith("QUEST_UPDATE:"):
            update = line[13:].strip()
            if update.lower() != "none":
                quest_update = update

    return {
        "pacing_status": pacing_status,
        "suggested_event": suggested_event,
        "quest_update": quest_update,
    }


async def generate_pacing_event(campaign_id: str, event_description: str) -> str:
    """Generate a brief narrative beat for a pacing event.

    Called when the Storyteller decides the story needs a push.
    Returns narrative text to be injected before the player's next turn.
    """
    router = get_llm_router()
    response = await router.generate(
        messages=[
            LLMMessage(
                role="system",
                content="You are a D&D Dungeon Master. Write a brief (1-2 paragraphs) "
                "atmospheric event that happens between player actions. Write in second "
                "person ('You notice...'). This should create intrigue or urgency without "
                "requiring immediate player action.",
            ),
            LLMMessage(role="user", content=f"Generate this event: {event_description}"),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.85,
        max_tokens=300,
    )
    return response.content
