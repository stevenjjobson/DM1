"""Tests for the spell engine."""

from dm1.rules.spells import ConcentrationTracker, SpellSlotTracker, validate_spell_cast


def test_spell_slot_tracker_basic():
    tracker = SpellSlotTracker({
        1: {"max": 4, "current": 4},
        2: {"max": 3, "current": 3},
    })
    assert tracker.can_cast(1) is True
    assert tracker.can_cast(3) is False  # No level 3 slots
    assert tracker.can_cast(0) is True  # Cantrips always


def test_use_slot():
    tracker = SpellSlotTracker({1: {"max": 2, "current": 2}})
    assert tracker.use_slot(1) is True
    assert tracker.remaining(1) == 1
    assert tracker.use_slot(1) is True
    assert tracker.remaining(1) == 0
    assert tracker.use_slot(1) is False  # No slots left


def test_cantrip_no_slot():
    tracker = SpellSlotTracker({})
    assert tracker.use_slot(0) is True  # Cantrips don't use slots


def test_recover_long_rest():
    tracker = SpellSlotTracker({
        1: {"max": 4, "current": 1},
        2: {"max": 3, "current": 0},
    })
    tracker.recover_long_rest()
    assert tracker.remaining(1) == 4
    assert tracker.remaining(2) == 3


def test_concentration_tracker():
    ct = ConcentrationTracker()
    assert ct.is_concentrating() is False

    dropped = ct.begin_concentration("Bless")
    assert dropped is None
    assert ct.is_concentrating() is True
    assert ct.active_spell == "Bless"

    # Starting new concentration drops the old one
    dropped = ct.begin_concentration("Hold Person")
    assert dropped == "Bless"
    assert ct.active_spell == "Hold Person"

    ended = ct.break_concentration()
    assert ended == "Hold Person"
    assert ct.is_concentrating() is False


def test_concentration_save_dc():
    ct = ConcentrationTracker()
    assert ct.concentration_save_dc(10) == 10  # Max of 10 or damage/2
    assert ct.concentration_save_dc(30) == 15  # 30/2 = 15
    assert ct.concentration_save_dc(5) == 10  # Floor of 10


def test_total_slots():
    tracker = SpellSlotTracker({
        1: {"max": 4, "current": 2},
        2: {"max": 3, "current": 3},
    })
    assert tracker.total_max() == 7
    assert tracker.total_remaining() == 5
