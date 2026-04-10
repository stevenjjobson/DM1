"""
Rule Enforcer for DungeonMasterONE.

Processes player actions that have mechanical outcomes (attacks, spell casts,
skill checks) and provides the Narrator with pre-computed results to weave
into the narrative.

The rule engine is deterministic code — the LLM only narrates the outcome,
it doesn't calculate it.
"""

import logging
from typing import Any

from dm1.rules.combat import attack_roll, check_hit, damage_roll, saving_throw
from dm1.rules.dice import ability_modifier, proficiency_bonus, roll_d20
from dm1.rules.skills import skill_check, SKILL_ABILITIES

logger = logging.getLogger(__name__)


def process_combat_action(
    action: str,
    character_attrs: dict,
) -> dict[str, Any] | None:
    """Process a combat action and return mechanical results.

    Returns None if the action isn't a combat action.
    Returns a dict with the mechanical outcome for the narrator.
    """
    action_lower = action.lower()

    abilities = character_attrs.get("abilities", {})
    level = character_attrs.get("level", 1)

    # Attack action
    if any(kw in action_lower for kw in ["attack", "strike", "hit", "swing", "slash", "stab", "shoot"]):
        # Default to STR-based melee attack
        attack_ability = abilities.get("strength", 10)
        if any(kw in action_lower for kw in ["shoot", "bow", "arrow", "throw", "dart"]):
            attack_ability = abilities.get("dexterity", 10)

        result = attack_roll(attack_ability, level, is_proficient=True)
        target_ac = 13  # Default enemy AC — will be dynamic with real combat

        hit = check_hit(result["total"], target_ac, result["critical_hit"])

        outcome = {
            "type": "attack",
            "roll": result["roll"],
            "modifier": result["modifier"],
            "total": result["total"],
            "target_ac": target_ac,
            "hit": hit,
            "critical_hit": result["critical_hit"],
            "critical_miss": result["critical_miss"],
        }

        if hit:
            dmg = damage_roll("1d8", critical=result["critical_hit"],
                              damage_modifier=ability_modifier(attack_ability))
            outcome["damage"] = dmg["total"]
            outcome["damage_rolls"] = dmg["rolls"]

        return outcome

    # Spell cast
    if any(kw in action_lower for kw in ["cast", "spell"]):
        return {
            "type": "spell_cast",
            "note": "Spell casting detected — slot tracking via Archivist",
        }

    return None


def process_skill_action(
    action: str,
    character_attrs: dict,
) -> dict[str, Any] | None:
    """Process an action that might involve a skill check.

    Returns None if no skill check is needed.
    """
    action_lower = action.lower()
    abilities = character_attrs.get("abilities", {})
    level = character_attrs.get("level", 1)
    proficient_skills = character_attrs.get("proficiencies", [])

    # Map actions to skills
    skill_triggers = {
        "perception": ["look", "search", "notice", "spot", "observe", "listen", "hear"],
        "investigation": ["investigate", "examine", "inspect", "study", "analyze"],
        "stealth": ["sneak", "hide", "creep", "stealth", "quietly"],
        "persuasion": ["persuade", "convince", "negotiate", "charm"],
        "intimidation": ["intimidate", "threaten", "scare"],
        "deception": ["lie", "deceive", "bluff", "trick"],
        "athletics": ["climb", "jump", "swim", "push", "grapple", "lift"],
        "acrobatics": ["dodge", "tumble", "balance", "flip"],
        "arcana": ["arcana", "magical", "identify spell"],
        "medicine": ["heal", "stabilize", "treat", "bandage"],
        "survival": ["track", "forage", "navigate", "survive"],
    }

    for skill_name, keywords in skill_triggers.items():
        if any(kw in action_lower for kw in keywords):
            dc = 12  # Default DC — will be dynamic with real encounter design
            result = skill_check(
                skill_index=skill_name,
                ability_scores=abilities,
                dc=dc,
                level=level,
                proficient_skills=proficient_skills,
            )
            return {
                "type": "skill_check",
                "skill": skill_name,
                "ability": result.get("ability", ""),
                "roll": result["roll"],
                "modifier": result["modifier"],
                "total": result["total"],
                "dc": dc,
                "success": result["success"],
            }

    return None


def build_mechanics_context(action: str, character_attrs: dict) -> str:
    """Build a mechanics context string for the narrator.

    If the action involves dice rolls, returns a string like:
    "MECHANICS: Attack roll: 15 + 5 = 20 vs AC 13 — Hit! Damage: 11 (1d8+3)"

    If no mechanics apply, returns empty string.
    """
    # Check combat
    combat = process_combat_action(action, character_attrs)
    if combat:
        if combat["type"] == "attack":
            parts = [f"Attack roll: {combat['roll']} + {combat['modifier']} = {combat['total']} vs AC {combat['target_ac']}"]
            if combat["critical_hit"]:
                parts.append("CRITICAL HIT!")
            elif combat["critical_miss"]:
                parts.append("CRITICAL MISS!")
            elif combat["hit"]:
                parts.append(f"Hit! Damage: {combat['damage']} ({combat['damage_rolls']})")
            else:
                parts.append("Miss!")
            return "MECHANICS: " + " — ".join(parts)

    # Check skill
    skill = process_skill_action(action, character_attrs)
    if skill:
        result_word = "Success" if skill["success"] else "Failure"
        return (
            f"MECHANICS: {skill['skill'].replace('-', ' ').title()} check "
            f"({skill['ability'].upper()}): {skill['roll']} + {skill['modifier']} = {skill['total']} "
            f"vs DC {skill['dc']} — {result_word}!"
        )

    return ""
