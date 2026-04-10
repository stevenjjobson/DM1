"""Test fixtures for API integration tests.

Uses a real MongoDB instance if MONGODB_URI is set in the environment,
otherwise uses mongomock-motor for in-memory testing.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from dm1.api.main import create_app


# ---------------------------------------------------------------------------
# Minimal in-memory MongoDB mock (no external dependencies)
# ---------------------------------------------------------------------------

class MockCollection:
    """Simple in-memory MongoDB collection mock for testing."""

    def __init__(self):
        self._docs = []
        self._counter = 0

    async def insert_one(self, doc: dict):
        from bson import ObjectId
        self._counter += 1
        doc_id = ObjectId()
        doc["_id"] = doc_id
        self._docs.append(dict(doc))
        result = MagicMock()
        result.inserted_id = doc_id
        return result

    def _match_filter(self, doc: dict, filter_dict: dict) -> bool:
        for key, value in filter_dict.items():
            doc_val = doc.get(key)
            if isinstance(value, dict):
                # Handle MongoDB operators
                for op, op_val in value.items():
                    if op == "$ne" and doc_val == op_val:
                        return False
                    elif op == "$in" and doc_val not in op_val:
                        return False
                    elif op == "$exists" and (key in doc) != op_val:
                        return False
            elif doc_val != value:
                return False
        return True

    async def find_one(self, filter_dict: dict):
        for doc in self._docs:
            if self._match_filter(doc, filter_dict):
                return dict(doc)
        return None

    async def update_one(self, filter_dict: dict, update: dict):
        for doc in self._docs:
            if self._match_filter(doc, filter_dict):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$push" in update:
                    for k, v in update["$push"].items():
                        doc.setdefault(k, []).append(v)
                result = MagicMock()
                result.modified_count = 1
                return result
        result = MagicMock()
        result.modified_count = 0
        return result

    async def delete_one(self, filter_dict: dict):
        for i, doc in enumerate(self._docs):
            if self._match_filter(doc, filter_dict):
                self._docs.pop(i)
                result = MagicMock()
                result.deleted_count = 1
                return result
        result = MagicMock()
        result.deleted_count = 0
        return result

    def find(self, filter_dict: dict = None):
        results = []
        for doc in self._docs:
            if filter_dict is None or self._match_filter(doc, filter_dict):
                results.append(dict(doc))
        return MockCursor(results)

    async def create_index(self, *args, **kwargs):
        pass


class MockCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        if length:
            return self._docs[:length]
        return self._docs

    def __aiter__(self):
        return MockCursorIter(self._docs)


class MockCursorIter:
    def __init__(self, docs):
        self._docs = iter(docs)

    async def __anext__(self):
        try:
            return next(self._docs)
        except StopIteration:
            raise StopAsyncIteration


class MockDatabase:
    def __init__(self):
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]

    def __getitem__(self, name):
        return getattr(self, name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db():
    """Fresh in-memory mock database for each test."""
    return MockDatabase()


@pytest_asyncio.fixture
async def client(mock_db) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with mocked database."""

    async def override_get_database():
        return mock_db

    with patch("dm1.api.database.get_database", override_get_database), \
         patch("dm1.api.database._db", mock_db), \
         patch("dm1.api.database._ensure_indexes", AsyncMock()):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a test user and return auth headers."""
    await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "display_name": "Test Hero",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123",
    })
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
