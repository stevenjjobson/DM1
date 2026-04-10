"""Tests for the skills engine."""

from dm1.rules.skills import (
    SKILL_ABILITIES,
    ability_check,
    contested_check,
    passive_check,
    passive_perception,
    skill_check,
)


def test_ability_check():
    result = ability_check(ability_score=14, dc=12, level=1, proficient=True)
    assert "roll" in result
    assert "success" in result
    assert result["modifier"] == 4  # +2 (ability) + 2 (prof)


def test_ability_check_expertise():
    result = ability_check(ability_score=14, dc=12, level=1, proficient=True, expertise=True)
    assert result["modifier"] == 6  # +2 (ability) + 4 (double prof)


def test_skill_check():
    abilities = {"strength": 14, "dexterity": 16, "constitution": 12,
                 "intelligence": 10, "wisdom": 13, "charisma": 8}
    result = skill_check(
        skill_index="stealth",
        ability_scores=abilities,
        dc=12,
        level=1,
        proficient_skills=["stealth"],
    )
    assert result["skill"] == "stealth"
    assert result["ability"] == "dexterity"
    assert result["modifier"] == 5  # +3 (DEX) + 2 (prof)


def test_passive_check():
    # WIS 16 (+3), proficient, level 1 (+2)
    passive = passive_check(ability_score=16, level=1, proficient=True)
    assert passive == 15  # 10 + 3 + 2


def test_passive_with_advantage():
    passive = passive_check(ability_score=10, advantage=True)
    assert passive == 15  # 10 + 0 + 5


def test_passive_perception():
    pp = passive_perception(wisdom_score=14, level=1, proficient=True)
    assert pp == 14  # 10 + 2 + 2


def test_contested_check():
    result = contested_check(
        actor_ability_score=16,
        opponent_ability_score=12,
    )
    assert "actor_total" in result
    assert "opponent_total" in result
    assert result["winner"] in ("actor", "opponent", "tie")


def test_skill_ability_mapping():
    assert SKILL_ABILITIES["stealth"] == "dexterity"
    assert SKILL_ABILITIES["perception"] == "wisdom"
    assert SKILL_ABILITIES["athletics"] == "strength"
    assert SKILL_ABILITIES["persuasion"] == "charisma"
    assert SKILL_ABILITIES["arcana"] == "intelligence"
