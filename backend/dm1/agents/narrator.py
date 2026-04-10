"""
Narrator Agent for DungeonMasterONE.

Generates all story text the player sees. Receives context from the Archivist
(graph state, NPC output, plot arcs) and produces:
  - Narrative prose (streamed to the client)
  - 2-3 suggested actions for the next beat
  - Mechanical outcomes woven into prose (dice rolls, spell effects)

The Narrator never queries the knowledge graph directly — it receives a
pre-assembled context package from the Archivist.

Prose craft: written for eventual single-voice TTS performance
(attribution tags, em-dashes for pauses, short sentences for tension).
"""

import json
import logging

from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)

NARRATOR_SYSTEM_PROMPT = """You are the Dungeon Master for a D&D 5e adventure. You narrate the story in second person ("You enter the tavern..."). Your responsibilities:

1. **Narrate the scene** — Describe what the player experiences based on their action and the current game state. Write vivid, immersive prose in 2-4 paragraphs.

2. **Enforce rules narratively** — If a player attempts something impossible (no spell slots, encumbered, etc.), narrate the failure naturally. Never show error messages.

3. **NPC dialogue** — Voice NPCs with distinct speech patterns. Use attribution tags ("growls", "whispers", "declares") rather than just "says".

4. **Prose craft for voice** — Write for single-voice narration:
   - Use em-dashes for dramatic pauses
   - Short sentences for tension, flowing sentences for calm
   - No stage directions like [angry] — convey mood through prose
   - Attribution tags guide vocal delivery

5. **Suggested actions** — After your narrative, provide exactly 3 contextually relevant action suggestions the player could take next. Format them as a JSON array on its own line, prefixed with "SUGGESTED_ACTIONS:".

IMPORTANT: End every response with a line containing:
SUGGESTED_ACTIONS: ["action 1", "action 2", "action 3"]

These should be natural actions that follow from the narrative — exploring, talking to NPCs, investigating, fighting, etc. Make the first action the most plot-advancing option."""


def build_narrator_prompt(
    player_action: str,
    context_package: dict,
    turn_number: int,
) -> list[LLMMessage]:
    """Build the message list for the Narrator LLM call."""
    # Assemble context into a concise summary for the narrator
    context_parts = []

    if context_package.get("character_state"):
        char = context_package["character_state"]
        facts = [e["fact"] for e in char.get("primary_edges", [])[:5]]
        if facts:
            context_parts.append("CHARACTER STATE:\n" + "\n".join(f"- {f}" for f in facts))

    if context_package.get("location"):
        loc = context_package["location"]
        entities = [e["fact"] for e in loc.get("entities_present", [])[:5]]
        connections = [e["fact"] for e in loc.get("connections", [])[:3]]
        if entities:
            context_parts.append("PRESENT HERE:\n" + "\n".join(f"- {f}" for f in entities))
        if connections:
            context_parts.append("NEARBY:\n" + "\n".join(f"- {f}" for f in connections))

    if context_package.get("plot_state"):
        plot = context_package["plot_state"]
        quests = [e["fact"] for e in plot.get("active_quests", [])[:3]]
        events = [e["fact"] for e in plot.get("recent_events", [])[:3]]
        if quests:
            context_parts.append("ACTIVE QUESTS:\n" + "\n".join(f"- {f}" for f in quests))
        if events:
            context_parts.append("RECENT EVENTS:\n" + "\n".join(f"- {f}" for f in events))

    if context_package.get("action_context"):
        action_ctx = [e["fact"] for e in context_package["action_context"][:3]]
        if action_ctx:
            context_parts.append("RELEVANT CONTEXT:\n" + "\n".join(f"- {f}" for f in action_ctx))

    # Mechanical outcomes (dice rolls, skill checks)
    if context_package.get("mechanics"):
        context_parts.append(context_package["mechanics"])

    context_text = "\n\n".join(context_parts) if context_parts else "No prior context — this is the beginning of the adventure."

    user_message = f"""Turn {turn_number}

GAME STATE:
{context_text}

PLAYER ACTION: {player_action}

Narrate what happens next. Remember to end with SUGGESTED_ACTIONS."""

    return [
        LLMMessage(role="system", content=NARRATOR_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_message),
    ]


async def generate_narrative(
    player_action: str,
    context_package: dict,
    turn_number: int,
) -> dict:
    """Generate a complete narrative response (non-streaming).

    Returns: {"narrative": str, "suggested_actions": list[str], "usage": dict}
    """
    messages = build_narrator_prompt(player_action, context_package, turn_number)
    router = get_llm_router()

    response = await router.generate(
        messages=messages,
        model_role=ModelRole.NARRATIVE,
        temperature=0.85,
        max_tokens=2000,
    )

    narrative, suggestions = _parse_narrator_output(response.content)

    return {
        "narrative": narrative,
        "suggested_actions": suggestions,
        "usage": {
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        },
    }


async def generate_narrative_stream(
    player_action: str,
    context_package: dict,
    turn_number: int,
):
    """Generate a streaming narrative response.

    Yields: LLMStreamChunk objects. The caller (WebSocket handler) sends
    each chunk to the client as it arrives. Suggested actions are parsed
    from the accumulated text after the stream completes.
    """
    messages = build_narrator_prompt(player_action, context_package, turn_number)
    router = get_llm_router()

    accumulated = ""
    async for chunk in router.generate_stream(
        messages=messages,
        model_role=ModelRole.NARRATIVE,
        temperature=0.85,
        max_tokens=2000,
    ):
        accumulated += chunk.content
        yield chunk

    # Parse suggestions from accumulated text (after stream completes)
    # The WebSocket handler will call parse_suggestions() separately


def _parse_narrator_output(text: str) -> tuple[str, list[str]]:
    """Parse narrative text and suggested actions from narrator output."""
    suggestions = []
    narrative = text

    # Find SUGGESTED_ACTIONS line
    if "SUGGESTED_ACTIONS:" in text:
        parts = text.rsplit("SUGGESTED_ACTIONS:", 1)
        narrative = parts[0].strip()
        try:
            suggestions = json.loads(parts[1].strip())
        except (json.JSONDecodeError, IndexError):
            suggestions = ["Look around", "Talk to someone nearby", "Continue forward"]
    else:
        suggestions = ["Look around", "Talk to someone nearby", "Continue forward"]

    return narrative, suggestions


def parse_suggestions(accumulated_text: str) -> list[str]:
    """Extract suggested actions from accumulated streamed text."""
    _, suggestions = _parse_narrator_output(accumulated_text)
    return suggestions


async def generate_session_recap(
    context_package: dict,
    turn_number: int,
) -> str:
    """Generate a recap for session resume ('When we last left off...')."""
    messages = [
        LLMMessage(
            role="system",
            content="You are a D&D Dungeon Master. The player is resuming their adventure. "
            "Provide a brief recap (2-3 sentences) of where they left off, written in second person. "
            "Be concise and atmospheric.",
        ),
        LLMMessage(
            role="user",
            content=f"Turn {turn_number}. Recent context:\n"
            + "\n".join(
                e["fact"]
                for e in context_package.get("plot_state", {}).get("recent_events", [])[:5]
            ),
        ),
    ]

    router = get_llm_router()
    response = await router.generate(
        messages=messages,
        model_role=ModelRole.AGENT,
        temperature=0.7,
        max_tokens=200,
    )
    return response.content
