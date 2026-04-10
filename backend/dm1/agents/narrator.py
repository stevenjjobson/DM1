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

NARRATOR_SYSTEM_PROMPT = """You are the Dungeon Master for a D&D 5e adventure. You narrate the story in second person ("You enter the tavern...").

## Core Rules

1. **Scene continuity is paramount.** You will receive CURRENT SCENE context showing where the player is, who is present, and what just happened. NEVER contradict this context. Build on it — don't restart the scene.

2. **Stay in the location** unless the player explicitly moves. If the player says "I look around," describe what they see HERE, not somewhere new.

3. **Reference NPCs by name** when they're listed as present. Don't invent new NPCs when established ones are available for the scene.

4. **Build on the previous turn.** If the last turn ended with tension, continue that tension. If the player just spoke to an NPC, that NPC is still there and remembers the conversation.

## Prose Craft

- Write 2-4 paragraphs of vivid, immersive prose in second person
- Voice NPCs with distinct speech patterns — use attribution tags ("growls", "whispers", "declares")
- Use em-dashes for dramatic pauses, short sentences for tension, flowing sentences for calm
- Enforce rules narratively — if an action is impossible, narrate the failure naturally

## Suggested Actions

End every response with exactly 3 contextually relevant action suggestions:
SUGGESTED_ACTIONS: ["action 1", "action 2", "action 3"]

Actions should follow naturally from the current scene — talking to present NPCs, exploring the current location, advancing the active quest. Make the first option the most plot-advancing."""


def build_narrator_prompt(
    player_action: str,
    context_package: dict,
    turn_number: int,
) -> list[LLMMessage]:
    """Build the message list for the Narrator LLM call."""
    context_parts = []

    # Scene state (highest priority — this is what grounds the narrative)
    scene = context_package.get("scene", {})
    if scene:
        scene_lines = []
        if scene.get("location"):
            scene_lines.append(f"Location: {scene['location']}")
        if scene.get("description"):
            scene_lines.append(f"Description: {scene['description']}")
        if scene.get("npcs_present"):
            npcs = ", ".join(scene["npcs_present"]) if isinstance(scene["npcs_present"], list) else scene["npcs_present"]
            scene_lines.append(f"NPCs present: {npcs}")
        if scene.get("atmosphere"):
            scene_lines.append(f"Atmosphere: {scene['atmosphere']}")
        if scene_lines:
            context_parts.append("CURRENT SCENE:\n" + "\n".join(scene_lines))

    # Previous turn (continuity anchor)
    if scene.get("last_narrative"):
        prev = f"PREVIOUS TURN SUMMARY:\n{scene['last_narrative']}"
        if scene.get("last_player_action"):
            prev += f"\nThe player's last action was: {scene['last_player_action']}"
        context_parts.append(prev)

    # Graph-derived context (supplementary)
    if context_package.get("character_state"):
        char = context_package["character_state"]
        facts = [e["fact"] for e in char.get("primary_edges", [])[:3]]
        if facts:
            context_parts.append("CHARACTER FACTS:\n" + "\n".join(f"- {f}" for f in facts))

    if context_package.get("plot_state"):
        plot = context_package["plot_state"]
        quests = [e["fact"] for e in plot.get("active_quests", [])[:3]]
        if quests:
            context_parts.append("ACTIVE QUESTS:\n" + "\n".join(f"- {f}" for f in quests))

    if context_package.get("action_context"):
        action_ctx = [e["fact"] for e in context_package["action_context"][:3]]
        if action_ctx:
            context_parts.append("RELEVANT CONTEXT:\n" + "\n".join(f"- {f}" for f in action_ctx))

    # Mechanical outcomes (dice rolls, skill checks)
    if context_package.get("mechanics"):
        context_parts.append(context_package["mechanics"])

    # NPC Agent dialogue (pre-generated in-character response)
    if context_package.get("npc_dialogue"):
        context_parts.append(f"NPC DIALOGUE (use this in your narration, adapt it naturally):\n{context_package['npc_dialogue']}")
    if context_package.get("npc_reveals"):
        context_parts.append(f"NPC REVEALS (weave this information into the conversation):\n{context_package['npc_reveals']}")

    # Storyteller pacing event (inject naturally at the start of the narrative)
    if context_package.get("pacing_event"):
        context_parts.append(f"PACING EVENT (something unexpected happens — weave this into the scene before responding to the player's action):\n{context_package['pacing_event']}")
    if context_package.get("quest_update"):
        context_parts.append(f"QUEST PROGRESS (acknowledge this development):\n{context_package['quest_update']}")

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
