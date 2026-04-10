"""Integration tests for campaign CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_campaign(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/campaigns", json={
        "name": "The Lost Mine",
        "settings": {"tone": "epic_fantasy", "combat_emphasis": 0.5},
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "The Lost Mine"
    assert data["status"] == "creating"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_campaign_no_auth(client: AsyncClient):
    resp = await client.post("/api/campaigns", json={
        "name": "No Auth Campaign",
        "settings": {"tone": "epic_fantasy"},
    })
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_campaigns(client: AsyncClient, auth_headers: dict):
    # Create two campaigns
    await client.post("/api/campaigns", json={
        "name": "Campaign One",
        "settings": {"tone": "dark_gritty"},
    }, headers=auth_headers)
    await client.post("/api/campaigns", json={
        "name": "Campaign Two",
        "settings": {"tone": "lighthearted"},
    }, headers=auth_headers)

    resp = await client.get("/api/campaigns", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [c["name"] for c in data["campaigns"]]
    assert "Campaign One" in names
    assert "Campaign Two" in names


@pytest.mark.asyncio
async def test_get_campaign(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/campaigns", json={
        "name": "Get Test",
        "settings": {"tone": "mystery"},
    }, headers=auth_headers)
    campaign_id = create_resp.json()["id"]

    resp = await client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_get_campaign_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/campaigns/000000000000000000000000", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_campaign(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/campaigns", json={
        "name": "Delete Me",
        "settings": {"tone": "horror"},
    }, headers=auth_headers)
    campaign_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code in (200, 204)

    # Verify deleted
    resp = await client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archive_campaign(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/campaigns", json={
        "name": "Archive Me",
        "settings": {"tone": "epic_fantasy"},
    }, headers=auth_headers)
    campaign_id = create_resp.json()["id"]

    resp = await client.post(f"/api/campaigns/{campaign_id}/archive", headers=auth_headers)
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "archived"
