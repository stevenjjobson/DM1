---
name: srd-data-patterns
description: "D&D 5e SRD data patterns for DungeonMasterONE rule engine — JSON schemas, content inventory, Pydantic models, lookup patterns"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/rules/` (rule engine)
- Building `dm1/rules/srd_models.py` or `dm1/rules/srd_repository.py`
- Loading and parsing SRD JSON files from `srd-data/`
- Working on character creation validation (legal race/class/spell/equipment combos)
- Implementing spell lookups, equipment properties, or monster stat blocks
- Debugging SRD data edge cases

## Data Source

**Repository:** `github.com/5e-bits/5e-database` → `src/2014/5e-SRD-*.json`
**License:** CC-BY-4.0 (include attribution in app)
**Files:** 25 JSON files, committed into DM1 at `srd-data/`

## Key Entity Schemas

### Universal Pattern (all entities)
```json
{"index": "fireball", "name": "Fireball", "url": "/api/2014/spells/fireball"}
```
Cross-references use: `{"index": "...", "name": "...", "url": "..."}`

### Race (9 races)
Key fields: `speed`, `ability_bonuses[{ability_score: APIRef, bonus: int}]`, `size`, `starting_proficiencies`, `traits`, `subraces`
Only 4 subraces: Hill Dwarf, High Elf, Lightfoot Halfling, Rock Gnome

### Class (12 classes)
Key fields: `hit_die`, `proficiency_choices`, `saving_throws`, `starting_equipment[{equipment: APIRef, quantity: int}]`, `starting_equipment_options`, `spellcasting` (optional)
Only 1 subclass per class in SRD

### Spell (318 spells)
Key fields: `level` (0=cantrip), `school`, `casting_time`, `range`, `components["V","S","M"]`, `material`, `duration`, `concentration`, `ritual`, `damage`, `classes[]`
**Highly variable** — not all spells have `damage`, `dc`, `attack_type`, or `area_of_effect`

### Equipment (polymorphic — ~240 items)
Check `equipment_category.index` to determine subtype:
- Weapons: `weapon_category`, `weapon_range`, `damage`, `properties`
- Armor: `armor_category`, `armor_class`, `str_minimum`, `stealth_disadvantage`
- Gear: `gear_category`
- Tools: `tool_category`

### Levels (~240 records, 12 classes × 20 levels)
Key fields: `level`, `prof_bonus`, `features[]`, `class_specific{}`, `spellcasting{cantrips_known, spell_slots_level_1..9}`

## Key Reference Tables

```python
# Ability modifier
modifier = (score - 10) // 2

# Proficiency bonus
prof_bonus = (level - 1) // 4 + 2

# XP thresholds
XP_BY_LEVEL = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000,
    7: 23000, 8: 34000, 9: 48000, 10: 64000, 11: 85000, 12: 100000,
    13: 120000, 14: 140000, 15: 165000, 16: 195000, 17: 225000,
    18: 265000, 19: 305000, 20: 355000}
```

## DM1 Integration Pattern

### SRD Repository Singleton
```python
class SRDRepository:
    _instance = None
    
    def __init__(self, data_dir: str = "srd-data"):
        self.races = self._load("5e-SRD-Races.json", Race)
        self.classes = self._load("5e-SRD-Classes.json", CharacterClass)
        self.spells = self._load("5e-SRD-Spells.json", Spell)
        self.equipment = self._load("5e-SRD-Equipment.json", Equipment)
        # ... all 25 files
    
    def get_race(self, index: str) -> Race: ...
    def get_class(self, index: str) -> CharacterClass: ...
    def get_spell(self, index: str) -> Spell: ...
    def spells_for_class(self, class_index: str, max_level: int) -> list[Spell]: ...
    def starting_equipment(self, class_index: str) -> list[EquipmentEntry]: ...
```

### Pydantic Model Tips
```python
from pydantic import BaseModel, Field

class CharacterClass(BaseModel):
    index: str
    name: str
    hit_die: int
    class_field: str = Field(alias="class")  # Python keyword conflict!
    
class Spell(BaseModel):
    index: str
    name: str
    level: int  # 0 = cantrip
    components: list[str]  # ["V", "S", "M"]
    concentration: bool
    damage: dict | None = None  # Not all spells have damage!
```

## What's NOT in the SRD

- Only 1 background (Acolyte), 1 feat (Grappler), 1 subclass per class
- No Aasimar, Firbolg, Warforged, Tabaxi, etc.
- No Great Weapon Master, Sharpshooter, Lucky, War Caster
- No Beholder, Mind Flayer (Product Identity)
- ~318 of 500+ total spells

## Common Pitfalls

1. **Equipment is polymorphic** — weapon/armor/gear/tool have different fields. Discriminate on `equipment_category.index`.
2. **`desc` is always an array** — even single paragraphs: `["text"]`
3. **`class` keyword conflict** — use `Field(alias="class")` in Pydantic
4. **Damage dice are strings** — need a parser for "2d6", "1d8+3", "8d6"
5. **Monster `armor_class` is a list** — some have multiple AC entries
6. **Spell fields highly variable** — always use `Optional` / `| None` for damage, dc, area_of_effect
7. **Cross-references by index** — always kebab-case, never display name
8. **Only 1 subclass per class** — UI must handle this gracefully (don't show "choose subclass" when there's only one option)
