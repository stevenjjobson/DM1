"""
Skills engine for DungeonMasterONE.

Handles ability checks, skill checks, passive checks, and contested checks.
Pure logic — no database calls.
"""

from dm1.rules.dice import ability_modifier, proficiency_bonus, roll_d20

# Skill → ability mapping (SRD)
SKILL_ABILITIES = {
    "acrobatics": "dexterity",
    "animal-handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight-of-hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}


def ability_check(
    ability_score: int,
    dc: int,
    level: int = 1,
    proficient: bool = False,
    expertise: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """Make an ability check against a DC.

    Returns: {"roll": int, "modifier": int, "total": int, "success": bool}
    """
    mod = ability_modifier(ability_score)
    if proficient:
        prof = proficiency_bonus(level)
        mod += prof * 2 if expertise else prof

    if advantage and not disadvantage:
        from dm1.rules.dice import roll_with_advantage
        d20, r1, r2 = roll_with_advantage()
    elif disadvantage and not advantage:
        from dm1.rules.dice import roll_with_disadvantage
        d20, r1, r2 = roll_with_disadvantage()
    else:
        d20 = roll_d20()

    total = d20 + mod
    return {
        "roll": d20,
        "modifier": mod,
        "total": total,
        "success": total >= dc,
    }


def skill_check(
    skill_index: str,
    ability_scores: dict[str, int],
    dc: int,
    level: int = 1,
    proficient_skills: list[str] | None = None,
    expertise_skills: list[str] | None = None,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """Make a skill check.

    skill_index: e.g., "perception", "stealth"
    ability_scores: {"strength": 14, "dexterity": 16, ...}
    """
    ability_name = SKILL_ABILITIES.get(skill_index, "strength")
    ability_score = ability_scores.get(ability_name, 10)

    proficient = skill_index in (proficient_skills or [])
    expertise = skill_index in (expertise_skills or [])

    result = ability_check(
        ability_score=ability_score,
        dc=dc,
        level=level,
        proficient=proficient,
        expertise=expertise,
        advantage=advantage,
        disadvantage=disadvantage,
    )
    result["skill"] = skill_index
    result["ability"] = ability_name
    return result


def passive_check(
    ability_score: int,
    level: int = 1,
    proficient: bool = False,
    expertise: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
) -> int:
    """Calculate passive check score (10 + modifier).

    Advantage adds +5, disadvantage subtracts -5.
    """
    mod = ability_modifier(ability_score)
    if proficient:
        prof = proficiency_bonus(level)
        mod += prof * 2 if expertise else prof

    base = 10 + mod
    if advantage:
        base += 5
    if disadvantage:
        base -= 5
    return base


def passive_perception(
    wisdom_score: int,
    level: int = 1,
    proficient: bool = False,
) -> int:
    """Convenience function for passive Perception."""
    return passive_check(wisdom_score, level, proficient)


def contested_check(
    actor_ability_score: int,
    opponent_ability_score: int,
    actor_level: int = 1,
    opponent_level: int = 1,
    actor_proficient: bool = False,
    opponent_proficient: bool = False,
) -> dict:
    """Make a contested ability check (actor vs opponent).

    Returns: {"actor_total": int, "opponent_total": int, "winner": "actor"|"opponent"|"tie"}
    """
    actor = ability_check(actor_ability_score, dc=0, level=actor_level, proficient=actor_proficient)
    opponent = ability_check(opponent_ability_score, dc=0, level=opponent_level, proficient=opponent_proficient)

    if actor["total"] > opponent["total"]:
        winner = "actor"
    elif opponent["total"] > actor["total"]:
        winner = "opponent"
    else:
        winner = "tie"

    return {
        "actor_total": actor["total"],
        "actor_roll": actor["roll"],
        "opponent_total": opponent["total"],
        "opponent_roll": opponent["roll"],
        "winner": winner,
    }
