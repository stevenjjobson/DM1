"""Tests for the SRD data repository."""

from dm1.rules.srd_repository import SRDRepository


def test_load_all_data():
    srd = SRDRepository.get()
    assert len(srd.list_races()) == 9
    assert len(srd.list_classes()) == 12
    assert len(srd.list_spells()) >= 318
    assert len(srd.list_skills()) == 18


def test_get_race():
    srd = SRDRepository.get()
    elf = srd.get_race("elf")
    assert elf is not None
    assert elf["name"] == "Elf"
    assert elf["speed"] == 30


def test_get_class():
    srd = SRDRepository.get()
    fighter = srd.get_class("fighter")
    assert fighter is not None
    assert fighter["name"] == "Fighter"
    assert fighter["hit_die"] == 10


def test_get_spell():
    srd = SRDRepository.get()
    fireball = srd.get_spell("fireball")
    assert fireball is not None
    assert fireball["name"] == "Fireball"
    assert fireball["level"] == 3
    assert "V" in fireball["components"]
    assert "S" in fireball["components"]


def test_spells_for_class():
    srd = SRDRepository.get()
    wizard_spells = srd.spells_for_class("wizard", max_level=1)
    assert len(wizard_spells) > 0
    assert all(s["level"] <= 1 for s in wizard_spells)


def test_cantrips_for_class():
    srd = SRDRepository.get()
    wizard_cantrips = srd.cantrips_for_class("wizard")
    assert len(wizard_cantrips) > 0
    assert all(s["level"] == 0 for s in wizard_cantrips)


def test_weapons():
    srd = SRDRepository.get()
    weapons = srd.weapons()
    assert len(weapons) > 0
    longsword = next((w for w in weapons if w["index"] == "longsword"), None)
    assert longsword is not None


def test_spell_slots_for_class_level():
    srd = SRDRepository.get()
    # Wizard at level 1: 2 first-level slots
    slots = srd.spell_slots_for_class_level("wizard", 1)
    assert 1 in slots
    assert slots[1] == 2

    # Wizard at level 5: should have 3rd level slots
    slots_5 = srd.spell_slots_for_class_level("wizard", 5)
    assert 3 in slots_5


def test_subraces():
    srd = SRDRepository.get()
    dwarf_subraces = srd.subraces_for_race("dwarf")
    assert len(dwarf_subraces) >= 1
    assert any(sr["index"] == "hill-dwarf" for sr in dwarf_subraces)


def test_features_for_class():
    srd = SRDRepository.get()
    fighter_features = srd.features_for_class("fighter", level=1)
    assert len(fighter_features) >= 1


def test_starting_equipment():
    srd = SRDRepository.get()
    # Fighter has starting_equipment_options (choices) rather than fixed equipment
    fighter = srd.get_class("fighter")
    assert fighter is not None
    options = fighter.get("starting_equipment_options", [])
    assert len(options) > 0  # Fighter has equipment choice options
