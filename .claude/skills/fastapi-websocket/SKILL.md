---
name: fastapi-websocket
description: "FastAPI WebSocket patterns for DungeonMasterONE — JWT auth, LLM streaming, connection management, message protocol"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/api/routes/gameplay.py` (WebSocket endpoint)
- Building or modifying `dm1/api/websocket/` (connection manager, message handlers)
- Implementing streaming narrative delivery to the client
- Working on WebSocket authentication
- Debugging connection lifecycle issues (disconnects, reconnection)

## Current API Shape (FastAPI + Starlette WebSocket)

### Installation
```bash
pip install fastapi uvicorn websockets uvloop
```

### WebSocket Endpoint with JWT Auth
```python
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query, WebSocketException, status

async def verify_ws_token(websocket: WebSocket, token: str = Query(...)) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

@app.websocket("/ws/gameplay/{campaign_id}")
async def gameplay_ws(websocket: WebSocket, campaign_id: str, user: dict = Depends(verify_ws_token)):
    await manager.connect(campaign_id, websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            # Route to orchestrator, stream response
    except WebSocketDisconnect:
        manager.disconnect(campaign_id)
```

Client connects: `ws://host/ws/gameplay/{campaign_id}?token=eyJ...`

### Streaming LLM Chunks
```python
# Inside the WebSocket handler:
async for chunk in orchestrator.stream(action, campaign_id):
    await websocket.send_json({"type": "narrative_chunk", "text": chunk})
await websocket.send_json({"type": "narrative_end"})
await websocket.send_json({"type": "suggestions", "actions": suggestions})
```

### Connection Manager
```python
class GameplayConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, campaign_id: str, ws: WebSocket):
        await ws.accept()
        self.active[campaign_id] = ws

    def disconnect(self, campaign_id: str):
        self.active.pop(campaign_id, None)

    async def send(self, campaign_id: str, data: dict):
        if ws := self.active.get(campaign_id):
            await ws.send_json(data)
```

## DM1 Message Protocol

### Client → Server
```json
{"type": "action", "text": "I search the room"}
{"type": "system", "command": "get_character_sheet"}
```

### Server → Client
```json
{"type": "narrative_chunk", "text": "partial text..."}
{"type": "narrative_end"}
{"type": "suggestions", "actions": ["Action 1", "Action 2"]}
{"type": "image", "url": "/assets/scene.jpg", "caption": "..."}
{"type": "state_update", "field": "hp", "value": 25}
{"type": "state_update", "field": "inventory", "action": "add", "item": {...}}
{"type": "quest_update", "quest": {...}}
{"type": "level_up", "new_level": 3, "choices_needed": {...}}
{"type": "error", "message": "..."}
```

### Custom Close Codes
- 4001: Auth failed
- 4002: Campaign not found
- 4003: Session expired

## Common Pitfalls

1. **No HTTP headers in browser WebSocket** — can't use `Authorization: Bearer` header. Pass JWT as query parameter instead.

2. **Don't block the event loop** — ALL operations inside the handler must be async. Use `async for` for LLM streaming, `await` for DB calls.

3. **WebSocketDisconnect is expected** — always wrap the receive loop in try/except WebSocketDisconnect. Clean up campaign state on disconnect.

4. **HTTPException doesn't work** — in WebSocket handlers, use `WebSocketException` or `websocket.close(code=4001)` instead.

5. **Single connection per campaign** — DM1 is solo-player, so one WebSocket per active campaign. The ConnectionManager maps campaign_id → WebSocket.

6. **Reconnection** — client should implement exponential backoff reconnection. On reconnect, re-authenticate and the server loads the last checkpoint.
