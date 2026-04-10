"""
Inventory engine for DungeonMasterONE.

Handles encumbrance, attunement, and carrying capacity. Pure logic.
"""

from dm1.rules.dice import ability_modifier


def carrying_capacity(strength_score: int) -> float:
    """Maximum carrying capacity in pounds. STR × 15."""
    return strength_score * 15.0


def is_encumbered(total_weight: float, strength_score: int) -> bool:
    """Check if encumbered (carrying > STR × 5)."""
    return total_weight > strength_score * 5.0


def is_heavily_encumbered(total_weight: float, strength_score: int) -> bool:
    """Check if heavily encumbered (carrying > STR × 10)."""
    return total_weight > strength_score * 10.0


def is_over_capacity(total_weight: float, strength_score: int) -> bool:
    """Check if over carrying capacity (carrying > STR × 15)."""
    return total_weight > carrying_capacity(strength_score)


MAX_ATTUNEMENT = 3


def can_attune(current_attuned: int) -> bool:
    """Check if character can attune to another item. Max 3."""
    return current_attuned < MAX_ATTUNEMENT


def calculate_total_weight(items: list[dict]) -> float:
    """Calculate total weight of items.

    Each item dict should have 'weight' and optionally 'quantity'.
    """
    total = 0.0
    for item in items:
        weight = item.get("weight", 0.0)
        quantity = item.get("quantity", 1)
        total += weight * quantity
    return total


def encumbrance_status(total_weight: float, strength_score: int) -> str:
    """Get the encumbrance status as a string.

    Returns: "normal", "encumbered", "heavily_encumbered", or "over_capacity"
    """
    if is_over_capacity(total_weight, strength_score):
        return "over_capacity"
    if is_heavily_encumbered(total_weight, strength_score):
        return "heavily_encumbered"
    if is_encumbered(total_weight, strength_score):
        return "encumbered"
    return "normal"
