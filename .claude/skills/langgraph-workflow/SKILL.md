---
name: langgraph-workflow
description: "LangGraph workflow patterns for DungeonMasterONE agent orchestration — StateGraph, routing, checkpointing, streaming"
---

## When to use

Invoke this skill when:
- Building or modifying the `dm1/agents/orchestrator.py` (LangGraph workflow definition)
- Adding new agent nodes to the workflow graph
- Implementing conditional routing logic
- Working on checkpointing / session persistence
- Debugging workflow execution order or parallel execution
- Implementing streaming narrative output through the graph

## Current API Shape (langgraph v1.1.6)

### Installation
```bash
pip install langgraph langgraph-checkpoint-mongodb
```

### State Schema
```python
from typing import TypedDict, Annotated
import operator

class GameState(TypedDict):
    turn_number: int
    action: str
    action_type: str  # orchestrator sets this
    narrator_output: str
    archivist_output: dict
    npc_output: str
    storyteller_output: dict
    visual_output: dict
    suggested_actions: list[str]
    graph_mutations: Annotated[list, operator.add]  # Append reducer
```

Use `Annotated[list, operator.add]` for fields that accumulate across nodes (mutations, messages). Use plain types for fields that each node overwrites.

### Graph Construction
```python
from langgraph.graph import START, END, StateGraph

graph = StateGraph(GameState)
graph.add_node("name", function)          # Add a node
graph.add_edge("a", "b")                  # Fixed edge
graph.add_edge("a", "b"); graph.add_edge("a", "c")  # Parallel: b and c run simultaneously
graph.add_conditional_edges("a", router_fn, {"val1": "b", "val2": "c"})  # Conditional
compiled = graph.compile(checkpointer=checkpointer)
```

### Conditional Routing
```python
def route_action(state: GameState) -> str:
    match state["action_type"]:
        case "narrative" | "combat": return "narrator"
        case "npc_interaction": return "npc_agent"
        case "exploration": return "storyteller"
        case "system_query": return "archivist"
    return "narrator"

graph.add_conditional_edges("orchestrator", route_action, {
    "narrator": "narrator", "npc_agent": "npc_agent",
    "storyteller": "storyteller", "archivist": "archivist"
})
```

### MongoDB Checkpointing
```python
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

client = MongoClient(settings.MONGODB_URI)
checkpointer = MongoDBSaver(client, db_name="dm1_checkpoints")
compiled = graph.compile(checkpointer=checkpointer)

# thread_id = campaign_id for per-campaign isolation
config = {"configurable": {"thread_id": campaign_id}}
result = compiled.invoke(state, config)

# Resume from checkpoint
state = compiled.get_state(config)
```

### Streaming
```python
# Stream node-level updates to WebSocket
for event in compiled.stream(state, config, stream_mode="updates"):
    if "narrator" in event:
        # Send narrative text to client
        await websocket.send_json({"type": "narrative", "text": event["narrator"]["narrator_output"]})
```

**Important:** LangGraph streams at the NODE level (after node completes). For token-by-token streaming within the narrator, handle LLM streaming inside the node function and yield chunks via a separate mechanism (e.g., callback or async generator).

## DM1 Integration Pattern

### DM1 Orchestrator Graph
```
START → orchestrator → [conditional routing]
  ├── narrator → archivist + visual_director (parallel) → response → END
  ├── npc_agent → narrator → archivist + visual_director (parallel) → response → END
  ├── storyteller → narrator → archivist + visual_director (parallel) → response → END
  └── archivist (system query, read-only) → response → END
```

### Node Function Pattern
Each agent node follows this pattern:
```python
async def narrator_node(state: GameState) -> dict:
    context = state.get("archivist_output", {})  # From prior node
    npc_dialogue = state.get("npc_output", "")
    
    narrative = await llm_provider.generate(
        messages=[...],  # Build prompt from context + action
        model="narrative",
        stream=True
    )
    
    suggestions = extract_suggestions(narrative)
    
    return {
        "narrator_output": narrative,
        "suggested_actions": suggestions
    }
```

### Crash Recovery
```python
# On session resume:
config = {"configurable": {"thread_id": campaign_id}}
checkpoint = compiled.get_state(config)

if checkpoint and checkpoint.values.get("_in_progress"):
    # Mid-turn crash — rollback to last complete turn
    # Player re-submits their last action
    pass
else:
    # Clean state — generate recap and continue
    pass
```

## Common Pitfalls

1. **Don't modify state in place** — always return a new dict from nodes. Mutations are applied by the framework via reducers.

2. **Parallel branches must not write to the same field** (unless using an append reducer). Archivist writes to `archivist_output`, visual_director writes to `visual_output` — no conflicts.

3. **State size** — the full state passes through every node. Store large data (images, generated audio) as file paths or URLs, not inline binary data.

4. **Thread ID is critical** — every invoke/stream call needs `{"configurable": {"thread_id": campaign_id}}`. Without it, checkpoints won't be isolated per campaign.

5. **Async nodes** — use `async def` for node functions that call external APIs. LangGraph supports async execution natively.

6. **Error handling** — if one parallel branch fails (visual_director API error), the other branch (archivist) may have already committed. Handle errors within nodes (try/except → return error state) rather than letting exceptions propagate.
