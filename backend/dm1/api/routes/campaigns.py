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
    return CampaignResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        status=doc["status"],
        settings=doc["settings"],
        current_turn=doc.get("current_turn", 0),
        character_id=doc.get("character_id"),
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
    result = await db.campaigns.delete_one({"_id": ObjectId(campaign_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")


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
