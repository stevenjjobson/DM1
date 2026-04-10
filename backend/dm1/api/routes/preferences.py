"""
Settings and cost management API for DungeonMasterONE.

Tracks API usage costs, spending caps, and user preferences.
"""

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from dm1.api.database import get_database
from dm1.api.middleware.auth import get_current_user_id
from dm1.providers.llm.router import get_llm_router

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/cost-summary")
async def get_cost_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get current month's cost summary by service category."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Aggregate costs from this month
    pipeline = [
        {"$match": {"user_id": user_id, "timestamp": {"$gte": month_start}}},
        {"$group": {
            "_id": "$service",
            "total_cost": {"$sum": "$estimated_cost_usd"},
            "total_calls": {"$sum": 1},
        }},
    ]
    cursor = db.cost_records.aggregate(pipeline)
    by_service = {doc["_id"]: {"cost": doc["total_cost"], "calls": doc["total_calls"]} async for doc in cursor}

    total = sum(s["cost"] for s in by_service.values())

    # Get spending cap
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    cap = user.get("spending_cap_usd", 10.0) if user else 10.0

    return {
        "month": now.strftime("%Y-%m"),
        "total_usd": round(total, 4),
        "cap_usd": cap,
        "percent_used": round((total / cap * 100) if cap > 0 else 0, 1),
        "by_service": by_service,
    }


@router.post("/spending-cap")
async def set_spending_cap(
    cap_usd: float,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Set the monthly spending cap."""
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"spending_cap_usd": max(0, cap_usd)}},
    )
    return {"cap_usd": max(0, cap_usd)}


@router.get("/llm-status")
async def get_llm_status(user_id: str = Depends(get_current_user_id)):
    """Get LLM provider availability status."""
    router = get_llm_router()
    return await router.get_status()


@router.get("/preferences")
async def get_preferences(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get user preferences."""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return {}
    return {
        "theme": user.get("theme", "dark"),
        "font_size": user.get("font_size", "medium"),
        "auto_narrate": user.get("auto_narrate", False),
        "spending_cap_usd": user.get("spending_cap_usd", 10.0),
        "ai_provider_preference": user.get("ai_provider_preference", "auto"),
    }


@router.patch("/preferences")
async def update_preferences(
    preferences: dict,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Update user preferences."""
    allowed = {"theme", "font_size", "auto_narrate", "spending_cap_usd", "ai_provider_preference"}
    updates = {k: v for k, v in preferences.items() if k in allowed}
    if updates:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    return updates
