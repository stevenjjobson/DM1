"""
Orchestrator — LangGraph workflow for DungeonMasterONE.

Defines the directed graph that routes player actions through the agent pipeline:
  START → orchestrator → [conditional routing] → narrator → archivist → END

Phase 1C implements the core loop: Orchestrator, Narrator, Archivist.
NPC Agent, Storyteller, and Visual Director are added in later sub-phases.
"""

import logging
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from dm1.agents.archivist import build_context_package, process_narrative
from dm1.agents.narrator import generate_narrative, parse_suggestions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Schema
# ---------------------------------------------------------------------------

class GameState(TypedDict):
    """LangGraph state passed through the workflow."""
    # Input
    campaign_id: str
    player_action: str
    turn_number: int

    # Orchestrator output
    action_type: str  # "narrative", "combat", "npc_interaction", "exploration", "system_query"

    # Context (built by archivist)
    context_package: dict

    # Narrator output
    narrative: str
    suggested_actions: list[str]
    narrator_usage: dict

    # Archivist output
    graph_changes: dict

    # Error tracking
    error: str


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

async def orchestrator_node(state: GameState) -> dict:
    """Classify the player's action and decide the routing."""
    action = state["player_action"].lower()

    # Simple keyword-based classification for Phase 1C
    # Will be replaced with LLM classification in later phases
    if any(w in action for w in ["attack", "fight", "cast", "strike", "shoot", "swing"]):
        action_type = "combat"
    elif any(w in action for w in ["talk", "ask", "speak", "say", "tell", "greet"]):
        action_type = "npc_interaction"
    elif any(w in action for w in ["look", "search", "examine", "inspect", "investigate", "explore"]):
        action_type = "exploration"
    elif any(w in action for w in ["inventory", "stats", "character", "spells", "quest"]):
        action_type = "system_query"
    else:
        action_type = "narrative"

    logger.info(f"Orchestrator: action_type={action_type} for '{state['player_action'][:50]}'")
    return {"action_type": action_type}


async def context_node(state: GameState) -> dict:
    """Build context package from the knowledge graph (Archivist read-only)."""
    try:
        context = await build_context_package(
            campaign_id=state["campaign_id"],
            player_action=state["player_action"],
        )
        return {"context_package": context}
    except Exception as e:
        logger.error(f"Context building failed: {e}")
        return {"context_package": {}, "error": str(e)}


async def narrator_node(state: GameState) -> dict:
    """Generate narrative response."""
    try:
        result = await generate_narrative(
            player_action=state["player_action"],
            context_package=state.get("context_package", {}),
            turn_number=state["turn_number"],
        )
        return {
            "narrative": result["narrative"],
            "suggested_actions": result["suggested_actions"],
            "narrator_usage": result["usage"],
        }
    except Exception as e:
        logger.error(f"Narrator failed: {e}")
        return {
            "narrative": "The world seems to shimmer and waver — something has disrupted the fabric of reality. Perhaps try a different approach.",
            "suggested_actions": ["Look around", "Wait", "Try something else"],
            "error": str(e),
        }


async def archivist_node(state: GameState) -> dict:
    """Process narrative output and update the knowledge graph."""
    try:
        changes = await process_narrative(
            campaign_id=state["campaign_id"],
            narrative_text=state.get("narrative", ""),
            player_action=state["player_action"],
            turn_number=state["turn_number"],
        )
        return {"graph_changes": changes}
    except Exception as e:
        logger.error(f"Archivist failed: {e}")
        return {"graph_changes": {"error": str(e)}}


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_gameplay_graph() -> StateGraph:
    """Build the LangGraph workflow for gameplay turns.

    Phase 1C flow:
      START → orchestrator → context → narrator → archivist → END

    Later phases add conditional routing, NPC agent, storyteller, visual director.
    """
    graph = StateGraph(GameState)

    # Add nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("context", context_node)
    graph.add_node("narrator", narrator_node)
    graph.add_node("archivist", archivist_node)

    # Linear flow for Phase 1C
    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "context")
    graph.add_edge("context", "narrator")
    graph.add_edge("narrator", "archivist")
    graph.add_edge("archivist", END)

    return graph


# ---------------------------------------------------------------------------
# Compiled Graph (singleton)
# ---------------------------------------------------------------------------

_compiled_graph = None


def get_gameplay_graph():
    """Get the compiled gameplay graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_gameplay_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


async def run_turn(campaign_id: str, player_action: str, turn_number: int) -> dict:
    """Execute a single gameplay turn through the orchestrator pipeline.

    Returns the final state with narrative, suggested actions, and graph changes.
    """
    graph = get_gameplay_graph()

    initial_state: GameState = {
        "campaign_id": campaign_id,
        "player_action": player_action,
        "turn_number": turn_number,
        "action_type": "",
        "context_package": {},
        "narrative": "",
        "suggested_actions": [],
        "narrator_usage": {},
        "graph_changes": {},
        "error": "",
    }

    result = await graph.ainvoke(initial_state)

    return {
        "narrative": result.get("narrative", ""),
        "suggested_actions": result.get("suggested_actions", []),
        "action_type": result.get("action_type", ""),
        "graph_changes": result.get("graph_changes", {}),
        "usage": result.get("narrator_usage", {}),
        "error": result.get("error", ""),
    }
