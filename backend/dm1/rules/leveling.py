"""
Leveling engine for DungeonMasterONE.

Handles XP tracking, level-up detection, HP calculation, and
new feature/ability unlocking. Pure logic.
"""

from dm1.rules.dice import (
    XP_BY_LEVEL,
    ability_modifier,
    level_for_xp,
    proficiency_bonus,
    roll,
    xp_for_next_level,
)


def should_level_up(current_level: int, current_xp: int) -> bool:
    """Check if a character should level up based on XP."""
    return level_for_xp(current_xp) > current_level


def hp_on_level_up(
    hit_die_sides: int,
    constitution_score: int,
    take_average: bool = False,
) -> int:
    """Calculate HP gained on level up.

    take_average: if True, use (hit_die / 2 + 1) instead of rolling.
    Minimum 1 HP gained regardless of CON modifier.
    """
    con_mod = ability_modifier(constitution_score)

    if take_average:
        roll_result = hit_die_sides // 2 + 1
    else:
        roll_result = roll(hit_die_sides)

    return max(1, roll_result + con_mod)


def hp_at_level_1(hit_die_sides: int, constitution_score: int) -> int:
    """Calculate starting HP at level 1. Max hit die + CON modifier."""
    return hit_die_sides + ability_modifier(constitution_score)


def level_up_summary(
    class_index: str,
    new_level: int,
) -> dict:
    """Get a summary of what a character gains at a new level.

    Returns: {
        "level": int,
        "proficiency_bonus": int,
        "features": list,
        "asi": bool (ability score improvement available),
        "new_spell_slots": dict,
    }
    """
    from dm1.rules.srd_repository import SRDRepository
    srd = SRDRepository.get()

    features = srd.features_for_class(class_index, new_level)
    level_features = [f for f in features if f.get("level") == new_level]

    # ASI at levels 4, 8, 12, 16, 19 for most classes
    asi_levels = {4, 8, 12, 16, 19}
    # Fighter gets extra at 6, 14
    if class_index == "fighter":
        asi_levels.update({6, 14})
    # Rogue gets extra at 10
    if class_index == "rogue":
        asi_levels.add(10)

    new_slots = srd.spell_slots_for_class_level(class_index, new_level)
    old_slots = srd.spell_slots_for_class_level(class_index, new_level - 1) if new_level > 1 else {}

    gained_slots = {}
    for lvl, count in new_slots.items():
        old_count = old_slots.get(lvl, 0)
        if count > old_count:
            gained_slots[lvl] = count - old_count

    return {
        "level": new_level,
        "proficiency_bonus": proficiency_bonus(new_level),
        "features": [{"name": f["name"], "desc": f.get("desc", [])} for f in level_features],
        "asi": new_level in asi_levels,
        "new_spell_slots": gained_slots,
        "xp_for_next": xp_for_next_level(new_level),
    }
