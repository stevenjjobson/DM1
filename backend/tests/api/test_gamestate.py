"""Integration tests for gamestate endpoints (character sheet, inventory, spellbook, quests)."""

import pytest
from bson import ObjectId
from httpx import AsyncClient


async def _create_campaign_with_character(client: AsyncClient, auth_headers: dict, mock_db) -> str:
    """Helper: create a campaign with character_attrs pre-populated (simulates post-genesis state)."""
    # Create campaign via API
    resp = await client.post("/api/campaigns", json={
        "name": "Test Campaign",
        "settings": {"tone": "epic_fantasy"},
    }, headers=auth_headers)
    campaign_id = resp.json()["id"]

    # Manually set character_attrs in the DB (simulates what character creation does)
    character_attrs = {
        "name": "Testharion",
        "race": "Elf",
        "char_class": "Wizard",
        "level": 1,
        "xp": 0,
        "hp": 7,
        "max_hp": 7,
        "ac": 12,
        "speed": 30,
        "proficiency_bonus": 2,
        "abilities": {
            "strength": 8, "dexterity": 14, "constitution": 12,
            "intelligence": 16, "wisdom": 10, "charisma": 13,
        },
        "proficiencies": ["arcana", "investigation"],
        "background": "sage",
        "backstory": "A wandering scholar.",
        "conditions": [],
        "equipment": [
            {"name": "Quarterstaff", "index": "quarterstaff", "quantity": 1},
            {"name": "Component Pouch", "index": "component-pouch", "quantity": 1},
            {"name": "Gold Pieces", "index": "gp", "quantity": 15},
        ],
        "known_cantrips": ["fire-bolt", "mage-hand", "prestidigitation"],
        "known_spells": ["magic-missile", "shield", "mage-armor", "find-familiar", "sleep", "thunderwave"],
        "spell_slots": {
            "1": {"max": 2, "current": 2},
        },
    }

    await mock_db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {
            "status": "active",
            "character_id": "test-char-uuid",
            "character_attrs": character_attrs,
            "current_turn": 3,
        }},
    )

    return campaign_id


@pytest.mark.asyncio
async def test_get_character_sheet(client: AsyncClient, auth_headers: dict, mock_db):
    campaign_id = await _create_campaign_with_character(client, auth_headers, mock_db)

    resp = await client.get(f"/api/gamestate/{campaign_id}/character", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Testharion"
    assert data["race"] == "Elf"
    assert data["class"] == "Wizard"
    assert data["level"] == 1
    assert data["hp"] == 7
    assert data["max_hp"] == 7
    assert data["ac"] == 12
    assert data["abilities"]["intelligence"] == 16
    assert data["proficiency_bonus"] == 2


@pytest.mark.asyncio
async def test_get_character_sheet_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/gamestate/000000000000000000000000/character", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_inventory(client: AsyncClient, auth_headers: dict, mock_db):
    campaign_id = await _create_campaign_with_character(client, auth_headers, mock_db)

    resp = await client.get(f"/api/gamestate/{campaign_id}/inventory", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [i["name"] for i in data["items"]]
    assert "Quarterstaff" in names
    assert "Component Pouch" in names
    assert data["gold"] == 15  # Gold tracked separately


@pytest.mark.asyncio
async def test_get_spellbook(client: AsyncClient, auth_headers: dict, mock_db):
    campaign_id = await _create_campaign_with_character(client, auth_headers, mock_db)

    resp = await client.get(f"/api/gamestate/{campaign_id}/spellbook", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Should have cantrips from character creation
    assert len(data["cantrips"]) == 3
    cantrip_names = [c["name"] for c in data["cantrips"]]
    assert "Fire Bolt" in cantrip_names
    assert "Mage Hand" in cantrip_names

    # Should have leveled spells
    assert len(data["spells"]) == 6
    spell_names = [s["name"] for s in data["spells"]]
    assert "Magic Missile" in spell_names
    assert "Shield" in spell_names

    # Should have spell slots
    assert "1" in data["spell_slots"]
    assert data["spell_slots"]["1"]["max"] == 2


@pytest.mark.asyncio
async def test_get_quests_suppressed_early(client: AsyncClient, auth_headers: dict, mock_db):
    """Quests should be suppressed before turn 2."""
    resp = await client.post("/api/campaigns", json={
        "name": "Quest Test",
        "settings": {"tone": "epic_fantasy"},
    }, headers=auth_headers)
    campaign_id = resp.json()["id"]

    await mock_db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {"status": "active", "current_turn": 1}},
    )

    resp = await client.get(f"/api/gamestate/{campaign_id}/quests", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] == []
    assert data["completed"] == []
