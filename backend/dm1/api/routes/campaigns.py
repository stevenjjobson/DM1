from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from dm1.api.database import get_database
from dm1.api.middleware.auth import get_current_user_id
from dm1.models.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatus,
    CampaignUpdate,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _doc_to_response(doc: dict) -> CampaignResponse:
    portrait = doc.get("portrait_filename")
    campaign_id = str(doc["_id"])
    return CampaignResponse(
        id=campaign_id,
        name=doc["name"],
        status=doc["status"],
        settings=doc["settings"],
        current_turn=doc.get("current_turn", 0),
        character_id=doc.get("character_id"),
        portrait_url=f"/api/assets/campaigns/{campaign_id}/{portrait}" if portrait else None,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        last_played_at=doc.get("last_played_at"),
    )


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cursor = db.campaigns.find({"user_id": user_id, "status": {"$ne": "archived"}}).sort("updated_at", -1)
    docs = await cursor.to_list(length=100)
    return CampaignListResponse(
        campaigns=[_doc_to_response(d) for d in docs],
        total=len(docs),
    )


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "name": body.name,
        "status": CampaignStatus.CREATING,
        "settings": body.settings.model_dump(),
        "current_turn": 0,
        "character_id": None,
        "created_at": now,
        "updated_at": now,
        "last_played_at": None,
    }
    result = await db.campaigns.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return _doc_to_response(doc)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id), "user_id": user_id},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    doc = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    return _doc_to_response(doc)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    await db.campaigns.delete_one({"_id": ObjectId(campaign_id)})

    # Cleanup graph nodes and Qdrant collection in background
    import asyncio
    asyncio.create_task(_cleanup_campaign_assets(campaign_id))


async def _cleanup_campaign_assets(campaign_id: str):
    """Background task: remove Qdrant collection, graph edges, and images for a campaign."""
    import logging
    logger = logging.getLogger(__name__)

    # 1. Delete Qdrant vector collection
    try:
        from dm1.providers.embedding.vector_db import delete_campaign_collection
        await delete_campaign_collection(campaign_id)
        logger.info(f"Deleted Qdrant collection for campaign {campaign_id}")
    except Exception as e:
        logger.warning(f"Failed to delete Qdrant collection for {campaign_id}: {e}")

    # 2. Note: knowledge graph edges with this group_id become orphaned
    # Graphiti doesn't support bulk delete by group_id yet — edges will
    # not appear in searches since no campaign references them
    logger.info(f"Campaign {campaign_id} graph edges orphaned (no bulk delete in Graphiti)")

    # 3. Delete generated images
    try:
        import shutil
        from pathlib import Path
        for base in [Path("/app/assets/campaigns"), Path(__file__).parent.parent.parent.parent / "assets" / "campaigns"]:
            campaign_dir = base / campaign_id
            if campaign_dir.exists():
                shutil.rmtree(campaign_dir)
                logger.info(f"Deleted asset directory: {campaign_dir}")
                break
    except Exception as e:
        logger.warning(f"Failed to delete assets for {campaign_id}: {e}")


@router.post("/cleanup-orphans")
async def cleanup_orphaned_assets(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Find and remove orphaned Qdrant collections and asset directories.

    Orphans are campaign data that exists in Qdrant or the filesystem
    but has no corresponding campaign document in MongoDB.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Get all campaign IDs that still exist for this user
    cursor = db.campaigns.find({"user_id": user_id})
    active_ids = set()
    async for doc in cursor:
        active_ids.add(str(doc["_id"]))

    cleaned = {"qdrant_collections": 0, "asset_dirs": 0}

    # Clean orphaned Qdrant collections
    try:
        from dm1.providers.embedding.vector_db import get_qdrant, delete_campaign_collection
        client = await get_qdrant()
        collections = await client.get_collections()
        for col in collections.collections:
            if col.name.startswith("campaign_"):
                cid = col.name.replace("campaign_", "")
                if cid not in active_ids:
                    await delete_campaign_collection(cid)
                    cleaned["qdrant_collections"] += 1
                    logger.info(f"Cleaned orphan Qdrant collection: {col.name}")
    except Exception as e:
        logger.warning(f"Qdrant orphan cleanup failed: {e}")

    # Clean orphaned asset directories
    try:
        from pathlib import Path
        import shutil
        for base in [Path("/app/assets/campaigns"), Path(__file__).parent.parent.parent.parent / "assets" / "campaigns"]:
            if base.exists():
                for campaign_dir in base.iterdir():
                    if campaign_dir.is_dir() and campaign_dir.name not in active_ids:
                        shutil.rmtree(campaign_dir)
                        cleaned["asset_dirs"] += 1
                        logger.info(f"Cleaned orphan asset dir: {campaign_dir.name}")
                break
    except Exception as e:
        logger.warning(f"Asset orphan cleanup failed: {e}")

    return {"cleaned": cleaned, "active_campaigns": len(active_ids)}


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id), "user_id": user_id},
        {"$set": {"status": CampaignStatus.ARCHIVED, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    doc = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    return _doc_to_response(doc)


@router.post("/{campaign_id}/duplicate", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    original = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "name": f"{original['name']} (Copy)",
        "status": CampaignStatus.CREATING,
        "settings": original["settings"],
        "current_turn": 0,
        "character_id": None,
        "created_at": now,
        "updated_at": now,
        "last_played_at": None,
    }
    result = await db.campaigns.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)
