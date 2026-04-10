"""Tests for the dice engine."""

from dm1.rules.dice import (
    STANDARD_ARRAY,
    ability_modifier,
    is_critical_hit,
    is_critical_miss,
    level_for_xp,
    parse_dice_notation,
    proficiency_bonus,
    roll,
    roll_ability_scores_4d6,
    roll_dice,
    roll_notation,
    validate_point_buy,
    xp_for_next_level,
)


def test_roll_single_die():
    for _ in range(100):
        result = roll(20)
        assert 1 <= result <= 20


def test_roll_dice_count():
    results = roll_dice(4, 6)
    assert len(results) == 4
    assert all(1 <= r <= 6 for r in results)


def test_ability_modifier():
    assert ability_modifier(10) == 0
    assert ability_modifier(11) == 0
    assert ability_modifier(12) == 1
    assert ability_modifier(8) == -1
    assert ability_modifier(1) == -5
    assert ability_modifier(20) == 5
    assert ability_modifier(16) == 3


def test_proficiency_bonus():
    assert proficiency_bonus(1) == 2
    assert proficiency_bonus(4) == 2
    assert proficiency_bonus(5) == 3
    assert proficiency_bonus(9) == 4
    assert proficiency_bonus(13) == 5
    assert proficiency_bonus(17) == 6
    assert proficiency_bonus(20) == 6


def test_parse_dice_notation():
    assert parse_dice_notation("d20") == (1, 20, 0)
    assert parse_dice_notation("2d6") == (2, 6, 0)
    assert parse_dice_notation("1d8+3") == (1, 8, 3)
    assert parse_dice_notation("4d6-1") == (4, 6, -1)
    assert parse_dice_notation("8d6") == (8, 6, 0)


def test_roll_notation():
    total, rolls, mod = roll_notation("2d6+3")
    assert len(rolls) == 2
    assert all(1 <= r <= 6 for r in rolls)
    assert total == sum(rolls) + 3
    assert mod == 3


def test_ability_scores_4d6():
    scores = roll_ability_scores_4d6()
    assert len(scores) == 6
    assert all(3 <= s <= 18 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_standard_array():
    assert STANDARD_ARRAY == [15, 14, 13, 12, 10, 8]


def test_validate_point_buy():
    # Valid: all 10s = 6 * 2 = 12 points
    assert validate_point_buy({"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})

    # Valid: standard point buy spread
    assert validate_point_buy({"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8})

    # Invalid: score out of range
    assert not validate_point_buy({"str": 16, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
    assert not validate_point_buy({"str": 7, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})

    # Invalid: over budget
    assert not validate_point_buy({"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 15, "cha": 15})


def test_critical_hit():
    assert is_critical_hit(20) is True
    assert is_critical_hit(19) is False


def test_critical_miss():
    assert is_critical_miss(1) is True
    assert is_critical_miss(2) is False


def test_level_for_xp():
    assert level_for_xp(0) == 1
    assert level_for_xp(299) == 1
    assert level_for_xp(300) == 2
    assert level_for_xp(900) == 3
    assert level_for_xp(355000) == 20


def test_xp_for_next_level():
    assert xp_for_next_level(1) == 300
    assert xp_for_next_level(19) == 355000
    assert xp_for_next_level(20) == 0  # Max level
