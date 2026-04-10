"""
Rule Enforcer for DungeonMasterONE.

Processes player actions that have mechanical outcomes (attacks, spell casts,
skill checks) and provides the Narrator with pre-computed results to weave
into the narrative.

The rule engine is deterministic code — the LLM only narrates the outcome,
it doesn't calculate it.
"""

import logging
import random
from typing import Any

from dm1.rules.combat import attack_roll, check_hit, damage_roll, saving_throw
from dm1.rules.dice import ability_modifier, proficiency_bonus, roll_d20
from dm1.rules.skills import skill_check, SKILL_ABILITIES

logger = logging.getLogger(__name__)


# Curated monster stat blocks for level 1-5 encounters.
# Each entry: (name_keywords, ac, hp, damage_dice, challenge_rating)
MONSTER_TABLE = [
    # CR 0-1/4
    (["rat", "rats"], 10, 1, "1d1", 0),
    (["bat", "bats"], 12, 1, "1d1", 0),
    (["goblin", "goblins"], 15, 7, "1d6+2", 0.25),
    (["kobold", "kobolds"], 12, 5, "1d4+2", 0.125),
    (["skeleton", "skeletons"], 13, 13, "1d6+2", 0.25),
    (["zombie", "zombies"], 8, 22, "1d6+1", 0.25),
    # CR 1/2-1
    (["orc", "orcs"], 13, 15, "1d12+3", 0.5),
    (["hobgoblin", "hobgoblins"], 18, 11, "1d8+1", 0.5),
    (["gnoll", "gnolls"], 15, 22, "1d8+2", 0.5),
    (["bandit", "bandits", "thief", "thug"], 12, 11, "1d8+1", 0.125),
    (["wolf", "wolves"], 13, 11, "2d4+2", 0.25),
    (["spider", "spiders", "giant spider"], 14, 26, "1d8+3", 1),
    (["bugbear", "bugbears"], 16, 27, "2d8+2", 1),
    # CR 2-3
    (["ogre", "ogres"], 11, 59, "2d8+4", 2),
    (["ghoul", "ghouls"], 12, 22, "2d6+2", 1),
    (["minotaur"], 14, 76, "2d12+4", 3),
    (["owlbear"], 13, 59, "1d10+4", 3),
    (["werewolf"], 12, 58, "2d4+3", 3),
    # Generic fallbacks by action context
    (["creature", "monster", "beast", "enemy", "foe"], 13, 20, "1d8+2", 1),
]


def _match_monster(action: str) -> tuple[str, int, int, str]:
    """Match a monster from the action text. Returns (name, ac, hp, damage_dice)."""
    action_lower = action.lower()
    for keywords, ac, hp, dmg, _cr in MONSTER_TABLE:
        if any(kw in action_lower for kw in keywords):
            return keywords[0], ac, hp, dmg
    # Default: a generic enemy appropriate for low-level play
    return "enemy", 13, 15, "1d6+2"


def _get_weapon_damage(character_attrs: dict) -> str:
    """Get damage dice from the character's equipment, defaulting to 1d8."""
    equipment = character_attrs.get("equipment", [])
    # Check for known weapon types
    weapon_damage = {
        "longsword": "1d8", "greatsword": "2d6", "shortsword": "1d6",
        "rapier": "1d8", "scimitar": "1d6", "dagger": "1d4",
        "greataxe": "1d12", "handaxe": "1d6", "battleaxe": "1d8",
        "warhammer": "1d8", "mace": "1d6", "quarterstaff": "1d6",
        "longbow": "1d8", "shortbow": "1d6", "light-crossbow": "1d8",
    }
    for item in equipment:
        idx = item.get("index", "").lower()
        if idx in weapon_damage:
            return weapon_damage[idx]
    return "1d8"


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
        is_ranged = any(kw in action_lower for kw in ["shoot", "bow", "arrow", "throw", "dart"])
        if is_ranged:
            attack_ability = abilities.get("dexterity", 10)

        result = attack_roll(attack_ability, level, is_proficient=True)

        # Match enemy from action text for dynamic AC
        enemy_name, target_ac, enemy_hp, enemy_dmg = _match_monster(action)

        hit = check_hit(result["total"], target_ac, result["critical_hit"])

        outcome = {
            "type": "attack",
            "roll": result["roll"],
            "modifier": result["modifier"],
            "total": result["total"],
            "target_ac": target_ac,
            "enemy": enemy_name,
            "enemy_hp": enemy_hp,
            "hit": hit,
            "critical_hit": result["critical_hit"],
            "critical_miss": result["critical_miss"],
        }

        if hit:
            weapon_dice = _get_weapon_damage(character_attrs)
            dmg = damage_roll(weapon_dice, critical=result["critical_hit"],
                              damage_modifier=ability_modifier(attack_ability))
            outcome["damage"] = dmg["total"]
            outcome["damage_rolls"] = dmg["rolls"]
            outcome["weapon_dice"] = weapon_dice

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

    # Context-sensitive DCs: easy=10, medium=12, hard=15
    hard_keywords = ["trap", "lock", "ancient", "magical", "hidden", "secret", "dangerous"]
    easy_keywords = ["simple", "basic", "obvious", "nearby", "around"]

    for skill_name, keywords in skill_triggers.items():
        if any(kw in action_lower for kw in keywords):
            dc = 12
            if any(kw in action_lower for kw in hard_keywords):
                dc = 15
            elif any(kw in action_lower for kw in easy_keywords):
                dc = 10
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
            enemy = combat.get("enemy", "enemy")
            parts = [f"Attack vs {enemy} (AC {combat['target_ac']}, HP {combat.get('enemy_hp', '?')}): "
                     f"roll {combat['roll']} + {combat['modifier']} = {combat['total']}"]
            if combat["critical_hit"]:
                parts.append("CRITICAL HIT!")
            elif combat["critical_miss"]:
                parts.append("CRITICAL MISS!")
            elif combat["hit"]:
                weapon = combat.get("weapon_dice", "1d8")
                parts.append(f"Hit! Damage: {combat['damage']} ({weapon}+{combat['modifier']})")
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
