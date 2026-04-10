"""Integration tests for SRD data endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_races(client: AsyncClient):
    resp = await client.get("/api/srd/races")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 9
    names = [r["name"] for r in data]
    assert "Human" in names
    assert "Elf" in names
    assert "Dwarf" in names


@pytest.mark.asyncio
async def test_get_race(client: AsyncClient):
    resp = await client.get("/api/srd/races/elf")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Elf"
    assert data["speed"] == 30
    assert any(b["ability"] == "dex" for b in data["ability_bonuses"])


@pytest.mark.asyncio
async def test_list_classes(client: AsyncClient):
    resp = await client.get("/api/srd/classes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 12
    wizard = next(c for c in data if c["index"] == "wizard")
    assert wizard["has_spellcasting"] is True
    assert wizard["hit_die"] == 6
    fighter = next(c for c in data if c["index"] == "fighter")
    assert fighter["has_spellcasting"] is False


@pytest.mark.asyncio
async def test_get_class_spellcasting_wizard(client: AsyncClient):
    resp = await client.get("/api/srd/classes/wizard/spellcasting")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_spellcasting"] is True
    assert data["cantrips_known"] == 3
    assert data["spells_known"] == 6
    assert data["caster_type"] == "prepared"
    assert "1" in data["spell_slots"]


@pytest.mark.asyncio
async def test_get_class_spellcasting_bard(client: AsyncClient):
    resp = await client.get("/api/srd/classes/bard/spellcasting")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_spellcasting"] is True
    assert data["cantrips_known"] == 2
    assert data["spells_known"] == 4
    assert data["caster_type"] == "known"


@pytest.mark.asyncio
async def test_get_class_spellcasting_fighter(client: AsyncClient):
    resp = await client.get("/api/srd/classes/fighter/spellcasting")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_spellcasting"] is False


@pytest.mark.asyncio
async def test_get_class_spellcasting_paladin_level1(client: AsyncClient):
    resp = await client.get("/api/srd/classes/paladin/spellcasting?level=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_spellcasting"] is False  # No spellcasting at level 1


@pytest.mark.asyncio
async def test_get_class_spells(client: AsyncClient):
    resp = await client.get("/api/srd/classes/wizard/spells?max_level=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 10  # Wizard has many spells
    cantrips = [s for s in data if s["level"] == 0]
    level1 = [s for s in data if s["level"] == 1]
    assert len(cantrips) > 5
    assert len(level1) > 10
    # Check spell structure
    spell = data[0]
    assert "name" in spell
    assert "school" in spell
    assert "components" in spell


@pytest.mark.asyncio
async def test_list_spells(client: AsyncClient):
    resp = await client.get("/api/srd/spells?max_level=0")
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["level"] == 0 for s in data)


@pytest.mark.asyncio
async def test_list_skills(client: AsyncClient):
    resp = await client.get("/api/srd/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 18
    names = [s["name"] for s in data]
    assert "Perception" in names
    assert "Stealth" in names


@pytest.mark.asyncio
async def test_list_backgrounds(client: AsyncClient):
    resp = await client.get("/api/srd/backgrounds")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(b["index"] == "acolyte" for b in data)


@pytest.mark.asyncio
async def test_list_equipment(client: AsyncClient):
    resp = await client.get("/api/srd/equipment")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 50
