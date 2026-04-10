from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from dm1.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from dm1.api.database import get_database
from dm1.api.middleware.auth import get_current_user_id
from dm1.models.user import TokenPair, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    existing = await db.users.find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.now(timezone.utc)
    user_doc = {
        "email": body.email,
        "display_name": body.display_name,
        "hashed_password": hash_password(body.password),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.users.insert_one(user_doc)
    return UserResponse(
        id=str(result.inserted_id),
        email=body.email,
        display_name=body.display_name,
        created_at=now,
    )


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin, db: AsyncIOMotorDatabase = Depends(get_database)):
    user = await db.users.find_one({"email": body.email})
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user_id = str(user["_id"])
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(refresh_token: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    token_data = decode_token(refresh_token)
    if token_data is None or token_data.type != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await db.users.find_one({"_id": ObjectId(token_data.sub)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_id = str(user["_id"])
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        display_name=user["display_name"],
        created_at=user["created_at"],
    )
