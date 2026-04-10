"""Tests for the rule enforcer (combat + skill check mechanics)."""

from dm1.agents.rule_enforcer import (
    _get_weapon_damage,
    _match_monster,
    build_mechanics_context,
    process_combat_action,
    process_skill_action,
)


WIZARD_ATTRS = {
    "abilities": {"strength": 8, "dexterity": 14, "constitution": 12,
                  "intelligence": 16, "wisdom": 10, "charisma": 13},
    "level": 1,
    "proficiencies": ["arcana", "investigation"],
    "equipment": [
        {"name": "Quarterstaff", "index": "quarterstaff", "quantity": 1},
    ],
}

FIGHTER_ATTRS = {
    "abilities": {"strength": 16, "dexterity": 12, "constitution": 14,
                  "intelligence": 10, "wisdom": 13, "charisma": 8},
    "level": 1,
    "proficiencies": ["athletics", "perception"],
    "equipment": [
        {"name": "Longsword", "index": "longsword", "quantity": 1},
        {"name": "Shield", "index": "shield", "quantity": 1},
    ],
}


def test_match_monster_goblin():
    name, ac, hp, dmg = _match_monster("I attack the goblin")
    assert name == "goblin"
    assert ac == 15
    assert hp == 7


def test_match_monster_dragon():
    """Dragon isn't in the table, should return generic enemy."""
    name, ac, hp, dmg = _match_monster("I attack the dragon")
    assert name == "enemy"
    assert ac == 13


def test_match_monster_skeleton():
    name, ac, hp, dmg = _match_monster("I strike the skeleton with my sword")
    assert name == "skeleton"
    assert ac == 13
    assert hp == 13


def test_match_monster_ogre():
    name, ac, hp, dmg = _match_monster("I shoot an arrow at the ogre")
    assert name == "ogre"
    assert ac == 11
    assert hp == 59


def test_get_weapon_damage_longsword():
    assert _get_weapon_damage(FIGHTER_ATTRS) == "1d8"


def test_get_weapon_damage_quarterstaff():
    assert _get_weapon_damage(WIZARD_ATTRS) == "1d6"


def test_get_weapon_damage_no_weapon():
    assert _get_weapon_damage({"equipment": []}) == "1d8"  # default


def test_combat_action_melee():
    result = process_combat_action("I attack the goblin with my sword", FIGHTER_ATTRS)
    assert result is not None
    assert result["type"] == "attack"
    assert result["enemy"] == "goblin"
    assert result["target_ac"] == 15
    assert result["enemy_hp"] == 7
    assert "roll" in result
    assert "modifier" in result
    # Fighter with STR 16: modifier should be +3 (ability) + 2 (prof) = +5
    assert result["modifier"] == 5


def test_combat_action_ranged():
    result = process_combat_action("I shoot an arrow at the wolf", FIGHTER_ATTRS)
    assert result is not None
    assert result["enemy"] == "wolf"
    # Ranged should use DEX (12 → +1 mod + 2 prof = +3)
    assert result["modifier"] == 3


def test_combat_action_not_combat():
    result = process_combat_action("I open the door", FIGHTER_ATTRS)
    assert result is None


def test_skill_check_perception():
    result = process_skill_action("I search the dark corridor", WIZARD_ATTRS)
    assert result is not None
    assert result["type"] == "skill_check"
    assert result["skill"] == "perception"
    assert result["dc"] == 12  # standard DC


def test_skill_check_hard_dc():
    result = process_skill_action("I investigate the hidden trap", WIZARD_ATTRS)
    assert result is not None
    assert result["dc"] == 15  # hard DC from "hidden" keyword


def test_skill_check_easy_dc():
    result = process_skill_action("I look at the obvious trail nearby", WIZARD_ATTRS)
    assert result is not None
    assert result["dc"] == 10  # easy DC from "obvious" + "nearby"


def test_skill_check_proficient():
    # Wizard is proficient in arcana
    result = process_skill_action("I use arcana to identify the glowing rune", WIZARD_ATTRS)
    assert result is not None
    assert result["skill"] == "arcana"
    # INT 16 = +3 mod + 2 prof = +5
    assert result["modifier"] == 5


def test_skill_check_not_proficient():
    # Wizard is NOT proficient in athletics
    result = process_skill_action("I climb the wall", WIZARD_ATTRS)
    assert result is not None
    assert result["skill"] == "athletics"
    # STR 8 = -1 mod, no prof = -1
    assert result["modifier"] == -1


def test_build_mechanics_context_attack():
    ctx = build_mechanics_context("I attack the skeleton", FIGHTER_ATTRS)
    assert ctx.startswith("MECHANICS:")
    assert "skeleton" in ctx
    assert "AC 13" in ctx


def test_build_mechanics_context_skill():
    ctx = build_mechanics_context("I search the room", WIZARD_ATTRS)
    assert ctx.startswith("MECHANICS:")
    assert "Perception" in ctx


def test_build_mechanics_context_no_mechanics():
    ctx = build_mechanics_context("I talk to the innkeeper", FIGHTER_ATTRS)
    assert ctx == ""
