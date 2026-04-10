"""
Gameplay API routes for DungeonMasterONE.

REST endpoint for starting a campaign (genesis) and a WebSocket
endpoint for real-time gameplay turns with streaming narrative.
"""

import json
import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

import asyncio

from dm1.agents.genesis import generate_world, populate_knowledge_graph
from dm1.agents.narrator import generate_narrative_stream, parse_suggestions
from dm1.agents.orchestrator import run_turn
from dm1.agents.visual_director import generate_scene_async
from dm1.api.auth import decode_token
from dm1.api.database import get_database
from dm1.api.middleware.auth import get_current_user_id
from dm1.models.campaign import CampaignStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gameplay", tags=["gameplay"])


# ---------------------------------------------------------------------------
# Campaign Start (Genesis)
# ---------------------------------------------------------------------------

@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Initialize a campaign: generate world, populate knowledge graph, return opening narration."""
    # Verify campaign exists and belongs to user
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign["status"] != CampaignStatus.CREATING:
        raise HTTPException(status_code=400, detail="Campaign already started")

    settings = campaign["settings"]

    default_attrs = {
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "hp": 12,
        "max_hp": 12,
        "ac": 16,
        "speed": 30,
        "proficiency_bonus": 2,
        "abilities": {"strength": 15, "dexterity": 13, "constitution": 14,
                      "intelligence": 10, "wisdom": 12, "charisma": 8},
        "equipment": [
            {"name": "Chain Mail", "index": "chain-mail", "quantity": 1},
            {"name": "Longsword", "index": "longsword", "quantity": 1},
            {"name": "Shield", "index": "shield", "quantity": 1},
            {"name": "Handaxe", "index": "handaxe", "quantity": 2},
            {"name": "Explorer's Pack", "index": "explorers-pack", "quantity": 1},
            {"name": "Gold Pieces", "index": "gp", "quantity": 15},
        ],
    }

    # Generate world
    world = await generate_world(
        campaign_name=campaign["name"],
        tone=settings.get("tone", "epic_fantasy"),
        character_name="The Adventurer",  # Placeholder until character builder
        character_class="Fighter",
        character_race="Human",
        world_setting=settings.get("world_setting", "surprise_me"),
    )

    # Populate knowledge graph
    created = await populate_knowledge_graph(
        world=world,
        campaign_id=campaign_id,
        character_name="The Adventurer",
        character_attributes=default_attrs,
    )

    # Update campaign status — store attrs as fallback for overlay display
    from datetime import datetime, timezone
    await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {
            "status": CampaignStatus.ACTIVE,
            "character_id": created["character_uuid"],
            "character_attrs": default_attrs,
            "current_turn": 0,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    return {
        "opening_narration": world.opening_narration,
        "starting_location": world.starting_location,
        "locations_created": len(created["locations"]),
        "npcs_created": len(created["npcs"]),
        "quests_created": len(created["quests"]),
        "character_uuid": created["character_uuid"],
    }


# ---------------------------------------------------------------------------
# Gameplay Turn (REST — non-streaming, simpler for testing)
# ---------------------------------------------------------------------------

@router.post("/{campaign_id}/turn")
async def play_turn(
    campaign_id: str,
    action: str = "",
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Execute a single gameplay turn (non-streaming). Use for testing."""
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign["status"] != CampaignStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Campaign not active")

    turn_number = campaign.get("current_turn", 0) + 1

    # Run the full orchestrator pipeline
    result = await run_turn(campaign_id, action, turn_number)

    # Update campaign turn counter
    from datetime import datetime, timezone
    await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {"current_turn": turn_number, "updated_at": datetime.now(timezone.utc), "last_played_at": datetime.now(timezone.utc)}},
    )

    return {
        "turn": turn_number,
        "narrative": result["narrative"],
        "suggested_actions": result["suggested_actions"],
        "action_type": result["action_type"],
    }


# ---------------------------------------------------------------------------
# WebSocket Gameplay (streaming)
# ---------------------------------------------------------------------------

@router.websocket("/ws/{campaign_id}")
async def gameplay_websocket(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time gameplay with streaming narrative.

    Client connects with: ws://host/api/gameplay/ws/{campaign_id}?token=JWT

    Client sends: {"type": "action", "text": "I search the room"}
    Server sends:
      - {"type": "narrative_chunk", "text": "partial text..."}
      - {"type": "narrative_end"}
      - {"type": "suggestions", "actions": ["a1", "a2", "a3"]}
      - {"type": "turn_complete", "turn": 5}
      - {"type": "error", "message": "..."}
    """
    # Authenticate
    token_data = decode_token(token)
    if token_data is None or token_data.type != "access":
        raise WebSocketException(code=4001)

    user_id = token_data.sub

    # Verify campaign
    db = await get_database()
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise WebSocketException(code=4002)

    await websocket.accept()
    logger.info(f"WebSocket connected: campaign={campaign_id} user={user_id}")

    try:
        while True:
            # Receive player action
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            if message.get("type") != "action":
                await websocket.send_json({"type": "error", "message": f"Unknown message type: {message.get('type')}"})
                continue

            player_action = message.get("text", "").strip()
            if not player_action:
                await websocket.send_json({"type": "error", "message": "Empty action"})
                continue

            # Increment turn
            turn_number = campaign.get("current_turn", 0) + 1

            # Run the full pipeline (non-streaming for Phase 1C — streaming added later)
            try:
                result = await run_turn(campaign_id, player_action, turn_number)

                # Send narrative as a single chunk (streaming upgrade in future)
                await websocket.send_json({
                    "type": "narrative_chunk",
                    "text": result["narrative"],
                })
                await websocket.send_json({"type": "narrative_end"})

                # Send suggestions
                await websocket.send_json({
                    "type": "suggestions",
                    "actions": result["suggested_actions"],
                })

                # Update turn counter
                from datetime import datetime, timezone
                await db.campaigns.update_one(
                    {"_id": ObjectId(campaign_id)},
                    {"$set": {
                        "current_turn": turn_number,
                        "updated_at": datetime.now(timezone.utc),
                        "last_played_at": datetime.now(timezone.utc),
                    }},
                )
                campaign["current_turn"] = turn_number

                await websocket.send_json({"type": "turn_complete", "turn": turn_number})

                # Fire lazy image generation (non-blocking)
                async def on_image_ready(cid: str, filename: str):
                    try:
                        await websocket.send_json({
                            "type": "image",
                            "url": f"/api/assets/campaigns/{cid}/{filename}",
                            "caption": player_action,
                        })
                    except Exception:
                        pass  # WebSocket may have closed

                campaign_tone = campaign.get("settings", {}).get("tone", "epic_fantasy")
                asyncio.create_task(
                    generate_scene_async(
                        narrative_text=result["narrative"],
                        campaign_id=campaign_id,
                        campaign_tone=campaign_tone,
                        on_image_ready=on_image_ready,
                    )
                )

            except Exception as e:
                logger.error(f"Turn processing failed: {e}")
                await websocket.send_json({"type": "error", "message": "Failed to process your action. Try again."})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: campaign={campaign_id}")
