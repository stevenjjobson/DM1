from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from dm1.config.settings import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def get_database() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_db]
        await _ensure_indexes(_db)
    return _db


async def close_database():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


async def _ensure_indexes(db: AsyncIOMotorDatabase):
    await db.users.create_index("email", unique=True)
    await db.campaigns.create_index("user_id")
    await db.campaigns.create_index([("user_id", 1), ("status", 1)])
    await db.cost_records.create_index([("user_id", 1), ("timestamp", -1)])
    await db.cost_records.create_index([("campaign_id", 1), ("timestamp", -1)])
