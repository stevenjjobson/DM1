"""
Combat engine for DungeonMasterONE.

Handles initiative, attack rolls, damage, death saves, and conditions.
Pure logic — no database or LLM calls.
"""

from dm1.rules.dice import (
    ability_modifier,
    is_critical_hit,
    is_critical_miss,
    proficiency_bonus,
    roll_d20,
    roll_notation,
)


def roll_initiative(dex_score: int) -> int:
    """Roll initiative (d20 + DEX modifier)."""
    return roll_d20() + ability_modifier(dex_score)


def attack_roll(
    ability_score: int,
    level: int,
    is_proficient: bool = True,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """Make an attack roll.

    Returns: {
        "roll": int (d20 result),
        "modifier": int,
        "total": int,
        "critical_hit": bool,
        "critical_miss": bool,
        "advantage_rolls": [int, int] or None,
    }
    """
    mod = ability_modifier(ability_score)
    if is_proficient:
        mod += proficiency_bonus(level)

    if advantage and not disadvantage:
        from dm1.rules.dice import roll_with_advantage
        d20_result, r1, r2 = roll_with_advantage()
        adv_rolls = [r1, r2]
    elif disadvantage and not advantage:
        from dm1.rules.dice import roll_with_disadvantage
        d20_result, r1, r2 = roll_with_disadvantage()
        adv_rolls = [r1, r2]
    else:
        d20_result = roll_d20()
        adv_rolls = None

    return {
        "roll": d20_result,
        "modifier": mod,
        "total": d20_result + mod,
        "critical_hit": is_critical_hit(d20_result),
        "critical_miss": is_critical_miss(d20_result),
        "advantage_rolls": adv_rolls,
    }


def damage_roll(
    notation: str,
    critical: bool = False,
    damage_modifier: int = 0,
) -> dict:
    """Roll damage.

    On a critical hit, damage dice are doubled (modifier not doubled).

    Returns: {"total": int, "rolls": list[int], "modifier": int, "critical": bool}
    """
    from dm1.rules.dice import parse_dice_notation, roll_dice

    count, sides, notation_mod = parse_dice_notation(notation)
    total_mod = notation_mod + damage_modifier

    if critical:
        count *= 2  # Double the dice on crit

    rolls = roll_dice(count, sides)
    total = sum(rolls) + total_mod

    return {
        "total": max(0, total),
        "rolls": rolls,
        "modifier": total_mod,
        "critical": critical,
    }


def saving_throw(
    ability_score: int,
    dc: int,
    level: int = 1,
    is_proficient: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """Make a saving throw against a DC.

    Returns: {"roll": int, "modifier": int, "total": int, "success": bool}
    """
    result = attack_roll(ability_score, level, is_proficient, advantage, disadvantage)
    return {
        "roll": result["roll"],
        "modifier": result["modifier"],
        "total": result["total"],
        "success": result["total"] >= dc,
        "advantage_rolls": result["advantage_rolls"],
    }


def death_save() -> dict:
    """Make a death saving throw.

    Natural 20: regain 1 HP (critical success)
    Natural 1: counts as two failures
    >= 10: success
    < 10: failure

    Returns: {"roll": int, "result": str, "successes": int, "failures": int}
    """
    d20 = roll_d20()

    if d20 == 20:
        return {"roll": d20, "result": "critical_success", "successes": 0, "failures": 0}
    elif d20 == 1:
        return {"roll": d20, "result": "critical_failure", "successes": 0, "failures": 2}
    elif d20 >= 10:
        return {"roll": d20, "result": "success", "successes": 1, "failures": 0}
    else:
        return {"roll": d20, "result": "failure", "successes": 0, "failures": 1}


def check_hit(attack_total: int, target_ac: int, critical_hit: bool = False) -> bool:
    """Determine if an attack hits.

    Critical hits always hit regardless of AC.
    """
    if critical_hit:
        return True
    return attack_total >= target_ac


def calculate_ac(
    armor_ac: int = 10,
    dex_score: int = 10,
    max_dex_bonus: int | None = None,
    shield: bool = False,
) -> int:
    """Calculate Armor Class.

    armor_ac: Base AC from armor (10 for unarmored)
    dex_score: DEX ability score
    max_dex_bonus: Maximum DEX bonus from armor (None = unlimited for light/no armor)
    shield: +2 AC if shield equipped
    """
    dex_mod = ability_modifier(dex_score)
    if max_dex_bonus is not None:
        dex_mod = min(dex_mod, max_dex_bonus)

    ac = armor_ac + dex_mod
    if shield:
        ac += 2
    return ac
