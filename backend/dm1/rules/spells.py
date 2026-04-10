"""
Spell engine for DungeonMasterONE.

Handles spell slot tracking, casting validation, concentration management,
and rest recovery. Pure logic — no database calls.
"""


class SpellSlotTracker:
    """Tracks spell slot usage for a character.

    Slots are stored as {level: {"max": int, "current": int}}.
    """

    def __init__(self, slots: dict[int, dict[str, int]] | None = None):
        self.slots = slots or {}

    @classmethod
    def from_class_level(cls, class_index: str, level: int) -> "SpellSlotTracker":
        """Create a slot tracker from SRD class/level data."""
        from dm1.rules.srd_repository import SRDRepository
        srd = SRDRepository.get()
        slot_data = srd.spell_slots_for_class_level(class_index, level)
        slots = {lvl: {"max": count, "current": count} for lvl, count in slot_data.items()}
        return cls(slots)

    def can_cast(self, spell_level: int) -> bool:
        """Check if a spell of the given level can be cast."""
        if spell_level == 0:
            return True  # Cantrips always castable
        slot = self.slots.get(spell_level)
        return slot is not None and slot["current"] > 0

    def can_upcast(self, spell_level: int, at_level: int) -> bool:
        """Check if a spell can be cast at a higher level."""
        if at_level < spell_level:
            return False
        return self.can_cast(at_level)

    def use_slot(self, level: int) -> bool:
        """Expend a spell slot. Returns False if no slot available."""
        if level == 0:
            return True
        slot = self.slots.get(level)
        if not slot or slot["current"] <= 0:
            return False
        slot["current"] -= 1
        return True

    def recover_long_rest(self):
        """Recover all spell slots (long rest)."""
        for slot in self.slots.values():
            slot["current"] = slot["max"]

    def recover_short_rest_warlock(self):
        """Recover all pact magic slots (warlock short rest)."""
        self.recover_long_rest()  # Warlocks recover all on short rest

    def remaining(self, level: int) -> int:
        slot = self.slots.get(level)
        return slot["current"] if slot else 0

    def max_slots(self, level: int) -> int:
        slot = self.slots.get(level)
        return slot["max"] if slot else 0

    def to_dict(self) -> dict:
        return {str(k): v for k, v in self.slots.items()}

    def total_remaining(self) -> int:
        return sum(s["current"] for s in self.slots.values())

    def total_max(self) -> int:
        return sum(s["max"] for s in self.slots.values())


class ConcentrationTracker:
    """Tracks concentration on a single spell."""

    def __init__(self):
        self.active_spell: str | None = None

    def begin_concentration(self, spell_name: str) -> str | None:
        """Start concentrating on a spell. Returns the name of the spell
        that was dropped (if any), or None if no prior concentration."""
        dropped = self.active_spell
        self.active_spell = spell_name
        return dropped

    def break_concentration(self) -> str | None:
        """Break concentration (damage, incapacitated, etc.).
        Returns the spell that ended."""
        ended = self.active_spell
        self.active_spell = None
        return ended

    def is_concentrating(self) -> bool:
        return self.active_spell is not None

    def concentration_save_dc(self, damage_taken: int) -> int:
        """Calculate the DC for a concentration save after taking damage.
        DC = max(10, damage / 2)."""
        return max(10, damage_taken // 2)


def validate_spell_cast(
    spell_data: dict,
    caster_level: int,
    class_index: str,
    slots: SpellSlotTracker,
    cast_at_level: int | None = None,
) -> dict:
    """Validate whether a spell can be cast.

    Returns: {"valid": bool, "reason": str, "slot_level": int}
    """
    spell_level = spell_data.get("level", 0)
    target_level = cast_at_level or spell_level

    # Cantrips always valid
    if spell_level == 0:
        return {"valid": True, "reason": "Cantrip — no slot needed", "slot_level": 0}

    # Check class has this spell
    spell_classes = [c.get("index") for c in spell_data.get("classes", [])]
    if class_index not in spell_classes:
        return {"valid": False, "reason": f"This spell is not on the {class_index} spell list", "slot_level": target_level}

    # Check upcast validity
    if target_level < spell_level:
        return {"valid": False, "reason": f"Cannot cast a level {spell_level} spell at level {target_level}", "slot_level": target_level}

    # Check slot availability
    if not slots.can_cast(target_level):
        return {"valid": False, "reason": f"No level {target_level} spell slots remaining", "slot_level": target_level}

    return {"valid": True, "reason": "Spell can be cast", "slot_level": target_level}
