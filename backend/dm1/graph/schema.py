"""
Knowledge graph schema for DungeonMasterONE.

Defines all node types, edge types, and their properties. This schema maps
to Graphiti's EntityNode labels and EntityEdge names. All game state lives
in Neo4j via Graphiti — this module is the canonical type reference.

See: architecture.md "Knowledge Graph Schema" section.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Node Types (Graphiti EntityNode labels)
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    CHARACTER = "Character"
    NPC = "NPC"
    ITEM = "Item"
    SPELL = "Spell"
    LOCATION = "Location"
    QUEST = "Quest"
    OBJECTIVE = "Objective"
    EVENT = "Event"
    CREATURE = "Creature"
    SESSION = "Session"


class AbilityScores(BaseModel):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class SpellSlots(BaseModel):
    """Spell slots by level. Key = level (1-9), value = {max, current}."""
    slots: dict[int, dict[str, int]] = {}

    def use_slot(self, level: int) -> bool:
        if level not in self.slots or self.slots[level]["current"] <= 0:
            return False
        self.slots[level]["current"] -= 1
        return True

    def recover_all(self):
        for level in self.slots:
            self.slots[level]["current"] = self.slots[level]["max"]

    def recover_short_rest(self, warlock: bool = False):
        if warlock:
            self.recover_all()


class CharacterAttributes(BaseModel):
    """Attributes stored on a Character EntityNode."""
    race: str = ""
    char_class: str = ""  # 'class' is a Python keyword
    subclass: str = ""
    level: int = 1
    xp: int = 0
    hp: int = 0
    max_hp: int = 0
    temp_hp: int = 0
    ac: int = 10
    speed: int = 30
    proficiency_bonus: int = 2
    abilities: AbilityScores = AbilityScores()
    spell_slots: SpellSlots = SpellSlots()
    hit_dice_total: int = 1
    hit_dice_current: int = 1
    hit_die_type: str = "d8"
    death_save_successes: int = 0
    death_save_failures: int = 0
    conditions: list[str] = []
    proficiencies: list[str] = []
    languages: list[str] = []
    background: str = ""
    alignment: str = ""
    backstory: str = ""
    binding_contract: dict = {}  # Visual appearance JSON for image generation


class NPCAttributes(BaseModel):
    """Attributes stored on an NPC EntityNode."""
    race: str = ""
    role: str = ""  # innkeeper, merchant, quest_giver, villain, etc.
    personality: str = ""
    motivations: list[str] = []
    fears: list[str] = []
    opinion_of_player: int = 0  # -100 to 100
    is_hostile: bool = False
    binding_contract: dict = {}  # Visual appearance for image generation


class ItemAttributes(BaseModel):
    """Attributes stored on an Item EntityNode."""
    item_type: str = ""  # weapon, armor, potion, scroll, quest_item, misc
    weight: float = 0.0
    value_gp: float = 0.0
    magical: bool = False
    attunement_required: bool = False
    equipped: bool = False
    quantity: int = 1
    properties: list[str] = []  # finesse, versatile, heavy, etc.
    damage: str = ""  # "1d8 slashing"
    armor_class: Optional[int] = None
    description: str = ""


class SpellAttributes(BaseModel):
    """Attributes stored on a Spell EntityNode."""
    level: int = 0  # 0 = cantrip
    school: str = ""
    casting_time: str = ""
    spell_range: str = ""
    components: list[str] = []  # ["V", "S", "M"]
    material: str = ""
    duration: str = ""
    concentration: bool = False
    ritual: bool = False
    description: str = ""
    damage: str = ""  # "8d6 fire"


class LocationAttributes(BaseModel):
    """Attributes stored on a Location EntityNode."""
    location_type: str = ""  # city, dungeon, tavern, forest, cave, etc.
    description: str = ""
    discovered_at_turn: Optional[int] = None


class QuestAttributes(BaseModel):
    """Attributes stored on a Quest EntityNode."""
    status: str = "active"  # active, completed, failed
    quest_confidence: float = 1.0
    description: str = ""
    reward: str = ""


class ObjectiveAttributes(BaseModel):
    """Attributes stored on an Objective EntityNode."""
    status: str = "active"  # active, completed, failed
    description: str = ""
    progress: str = ""


class EventAttributes(BaseModel):
    """Attributes stored on an Event EntityNode."""
    event_type: str = ""  # combat, npc_interaction, exploration, discovery, rest, level_up
    turn_number: int = 0
    description: str = ""


class CreatureAttributes(BaseModel):
    """Attributes stored on a Creature EntityNode."""
    challenge_rating: float = 0.0
    hp: int = 0
    ac: int = 10
    xp_value: int = 0
    abilities: AbilityScores = AbilityScores()
    attacks: list[dict] = []
    description: str = ""


class SessionAttributes(BaseModel):
    """Attributes stored on a Session EntityNode."""
    session_number: int = 0
    started_at: str = ""
    ended_at: str = ""
    summary: str = ""


# ---------------------------------------------------------------------------
# Edge Types (Graphiti EntityEdge names)
# ---------------------------------------------------------------------------

class EdgeType(str, Enum):
    """All relationship types in the knowledge graph.

    Temporal edges have valid_at/invalid_at managed by Graphiti.
    Static edges don't change over time.
    """
    # Temporal edges (valid_at / invalid_at tracked)
    OWNED_BY = "OWNED_BY"           # Item → Character/NPC
    EQUIPPED_BY = "EQUIPPED_BY"     # Item → Character
    LOCATED_AT = "LOCATED_AT"       # Character/NPC/Item → Location
    ALLIED_WITH = "ALLIED_WITH"     # NPC → NPC/Character
    HOSTILE_TO = "HOSTILE_TO"       # NPC → NPC/Character
    KNOWS_SPELL = "KNOWS_SPELL"     # Character → Spell
    HAS_PREPARED = "HAS_PREPARED"   # Character → Spell

    # Static edges (no temporal validity)
    CONNECTED_TO = "CONNECTED_TO"   # Location → Location
    GIVEN_BY = "GIVEN_BY"           # Quest → NPC
    HAS_OBJECTIVE = "HAS_OBJECTIVE" # Quest → Objective
    PARTICIPATED_IN = "PARTICIPATED_IN"  # Character/NPC → Event
    OCCURRED_AT = "OCCURRED_AT"     # Event → Location
    TRIGGERED_BY = "TRIGGERED_BY"   # Event → Event (causal chain)


TEMPORAL_EDGES = {
    EdgeType.OWNED_BY,
    EdgeType.EQUIPPED_BY,
    EdgeType.LOCATED_AT,
    EdgeType.ALLIED_WITH,
    EdgeType.HOSTILE_TO,
    EdgeType.KNOWS_SPELL,
    EdgeType.HAS_PREPARED,
}

STATIC_EDGES = {
    EdgeType.CONNECTED_TO,
    EdgeType.GIVEN_BY,
    EdgeType.HAS_OBJECTIVE,
    EdgeType.PARTICIPATED_IN,
    EdgeType.OCCURRED_AT,
    EdgeType.TRIGGERED_BY,
}


# ---------------------------------------------------------------------------
# Attribute type mapping for node creation
# ---------------------------------------------------------------------------

NODE_ATTRIBUTE_TYPES: dict[NodeType, type[BaseModel]] = {
    NodeType.CHARACTER: CharacterAttributes,
    NodeType.NPC: NPCAttributes,
    NodeType.ITEM: ItemAttributes,
    NodeType.SPELL: SpellAttributes,
    NodeType.LOCATION: LocationAttributes,
    NodeType.QUEST: QuestAttributes,
    NodeType.OBJECTIVE: ObjectiveAttributes,
    NodeType.EVENT: EventAttributes,
    NodeType.CREATURE: CreatureAttributes,
    NodeType.SESSION: SessionAttributes,
}
