"""
Dice engine for DungeonMasterONE.

All dice rolling mechanics — d4 through d20, advantage/disadvantage,
4d6-drop-lowest for ability scores, critical hits. Pure logic, no
external dependencies.
"""

import random
import re


def roll(sides: int) -> int:
    """Roll a single die with the given number of sides."""
    return random.randint(1, sides)


def roll_dice(count: int, sides: int) -> list[int]:
    """Roll multiple dice. Returns the list of individual results."""
    return [roll(sides) for _ in range(count)]


def roll_d20() -> int:
    return roll(20)


def roll_with_advantage() -> tuple[int, int, int]:
    """Roll 2d20, take the higher. Returns (result, roll1, roll2)."""
    r1, r2 = roll(20), roll(20)
    return max(r1, r2), r1, r2


def roll_with_disadvantage() -> tuple[int, int, int]:
    """Roll 2d20, take the lower. Returns (result, roll1, roll2)."""
    r1, r2 = roll(20), roll(20)
    return min(r1, r2), r1, r2


def roll_ability_scores_4d6() -> list[int]:
    """Roll 4d6-drop-lowest for all 6 ability scores.

    Returns a list of 6 scores (highest to lowest).
    """
    scores = []
    for _ in range(6):
        rolls = roll_dice(4, 6)
        rolls.sort(reverse=True)
        scores.append(sum(rolls[:3]))  # Drop lowest
    scores.sort(reverse=True)
    return scores


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

POINT_BUY_COSTS = {
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9,
}
POINT_BUY_BUDGET = 27


def validate_point_buy(scores: dict[str, int]) -> bool:
    """Validate that ability scores fit within the 27-point budget.

    scores: {"strength": 15, "dexterity": 10, ...}
    """
    if len(scores) != 6:
        return False
    total_cost = 0
    for score in scores.values():
        if score < 8 or score > 15:
            return False
        total_cost += POINT_BUY_COSTS.get(score, 999)
    return total_cost <= POINT_BUY_BUDGET


def ability_modifier(score: int) -> int:
    """Calculate the ability modifier for a given score."""
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Calculate proficiency bonus for a given level."""
    return (level - 1) // 4 + 2


def parse_dice_notation(notation: str) -> tuple[int, int, int]:
    """Parse dice notation like '2d6+3' into (count, sides, modifier).

    Supports: 'd20', '2d6', '1d8+3', '4d6-1', '8d6'
    """
    notation = notation.strip().lower()
    match = re.match(r"(\d*)d(\d+)([+-]\d+)?", notation)
    if not match:
        raise ValueError(f"Invalid dice notation: {notation}")

    count = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    return count, sides, modifier


def roll_notation(notation: str) -> tuple[int, list[int], int]:
    """Roll dice from notation string. Returns (total, individual_rolls, modifier)."""
    count, sides, modifier = parse_dice_notation(notation)
    rolls = roll_dice(count, sides)
    total = sum(rolls) + modifier
    return total, rolls, modifier


def is_critical_hit(roll_value: int) -> bool:
    """Check if a d20 roll is a natural 20 (critical hit)."""
    return roll_value == 20


def is_critical_miss(roll_value: int) -> bool:
    """Check if a d20 roll is a natural 1 (critical miss)."""
    return roll_value == 1


# XP thresholds by level (SRD)
XP_BY_LEVEL = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000,
    7: 23000, 8: 34000, 9: 48000, 10: 64000, 11: 85000,
    12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}


def level_for_xp(xp: int) -> int:
    """Determine the character level for a given XP total."""
    for level in range(20, 0, -1):
        if xp >= XP_BY_LEVEL[level]:
            return level
    return 1


def xp_for_next_level(current_level: int) -> int:
    """XP needed to reach the next level."""
    if current_level >= 20:
        return 0
    return XP_BY_LEVEL[current_level + 1]
