"""Integration tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "securepass123",
        "display_name": "New Hero",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["display_name"] == "New Hero"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "dupe@example.com",
        "password": "securepass123",
        "display_name": "First User",
    })
    resp = await client.post("/api/auth/register", json={
        "email": "dupe@example.com",
        "password": "securepass123",
        "display_name": "Second User",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "short@example.com",
        "password": "short",
        "display_name": "Short Pass",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "securepass123",
        "display_name": "Bad Email",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    # Register first
    await client.post("/api/auth/register", json={
        "email": "login@example.com",
        "password": "securepass123",
        "display_name": "Login User",
    })
    # Login
    resp = await client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "wrongpw@example.com",
        "password": "securepass123",
        "display_name": "Wrong PW User",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "email": "ghost@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test Hero"


@pytest.mark.asyncio
async def test_get_me_no_auth(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    # Register and login
    await client.post("/api/auth/register", json={
        "email": "refresh@example.com",
        "password": "securepass123",
        "display_name": "Refresh User",
    })
    login_resp = await client.post("/api/auth/login", json={
        "email": "refresh@example.com",
        "password": "securepass123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    resp = await client.post(f"/api/auth/refresh?refresh_token={refresh_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
