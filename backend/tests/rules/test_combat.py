"""Tests for the combat engine."""

from dm1.rules.combat import (
    attack_roll,
    calculate_ac,
    check_hit,
    damage_roll,
    death_save,
    roll_initiative,
    saving_throw,
)


def test_roll_initiative():
    for _ in range(50):
        init = roll_initiative(14)  # DEX 14, modifier +2
        assert init >= 3  # 1 + 2
        assert init <= 22  # 20 + 2


def test_attack_roll():
    result = attack_roll(ability_score=16, level=1, is_proficient=True)
    assert "roll" in result
    assert "modifier" in result
    assert "total" in result
    assert result["modifier"] == 5  # +3 (STR mod) + 2 (prof)
    assert result["total"] == result["roll"] + result["modifier"]


def test_attack_roll_advantage():
    result = attack_roll(ability_score=14, level=1, advantage=True)
    assert result["advantage_rolls"] is not None
    assert len(result["advantage_rolls"]) == 2
    assert result["roll"] == max(result["advantage_rolls"])


def test_damage_roll():
    result = damage_roll("1d8", damage_modifier=3)
    assert result["total"] >= 4  # 1 + 3
    assert result["total"] <= 11  # 8 + 3
    assert len(result["rolls"]) == 1


def test_damage_roll_critical():
    result = damage_roll("1d8", critical=True)
    assert len(result["rolls"]) == 2  # Doubled dice on crit


def test_check_hit():
    assert check_hit(15, 13) is True
    assert check_hit(12, 13) is False
    assert check_hit(13, 13) is True  # Equal = hit
    assert check_hit(1, 25, critical_hit=True) is True  # Crit always hits


def test_saving_throw():
    result = saving_throw(ability_score=14, dc=12, level=1)
    assert "success" in result
    assert isinstance(result["success"], bool)


def test_death_save():
    result = death_save()
    assert result["roll"] >= 1
    assert result["roll"] <= 20
    assert result["result"] in ("critical_success", "critical_failure", "success", "failure")


def test_calculate_ac():
    # No armor, DEX 14 (+2)
    assert calculate_ac(armor_ac=10, dex_score=14) == 12
    # Chain mail (AC 16, max DEX 0) + shield
    assert calculate_ac(armor_ac=16, dex_score=14, max_dex_bonus=0, shield=True) == 18
    # Leather (AC 11, unlimited DEX), DEX 16 (+3)
    assert calculate_ac(armor_ac=11, dex_score=16) == 14
