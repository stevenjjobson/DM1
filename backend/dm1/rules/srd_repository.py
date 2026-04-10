"""
SRD Data Repository for DungeonMasterONE.

Loads D&D 5e SRD JSON files at startup and provides typed lookup methods.
All game rules reference this repository for races, classes, spells,
equipment, etc.

Data source: github.com/5e-bits/5e-database (CC-BY-4.0)
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve SRD data directory — works both locally and in Docker
_local_path = Path(__file__).parent.parent.parent.parent / "srd-data"
_docker_path = Path("/app/srd-data")
SRD_DATA_DIR = _local_path if _local_path.exists() else _docker_path


class SRDRepository:
    """Singleton repository for D&D 5e SRD data."""

    _instance: "SRDRepository | None" = None

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or SRD_DATA_DIR
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._index: dict[str, dict[str, dict[str, Any]]] = {}
        self._load_all()

    @classmethod
    def get(cls, data_dir: Path | None = None) -> "SRDRepository":
        if cls._instance is None:
            cls._instance = cls(data_dir)
        return cls._instance

    def _load_all(self):
        """Load all SRD JSON files and build indexes."""
        files = {
            "ability_scores": "5e-SRD-Ability-Scores.json",
            "backgrounds": "5e-SRD-Backgrounds.json",
            "classes": "5e-SRD-Classes.json",
            "conditions": "5e-SRD-Conditions.json",
            "damage_types": "5e-SRD-Damage-Types.json",
            "equipment_categories": "5e-SRD-Equipment-Categories.json",
            "equipment": "5e-SRD-Equipment.json",
            "features": "5e-SRD-Features.json",
            "languages": "5e-SRD-Languages.json",
            "levels": "5e-SRD-Levels.json",
            "magic_schools": "5e-SRD-Magic-Schools.json",
            "proficiencies": "5e-SRD-Proficiencies.json",
            "races": "5e-SRD-Races.json",
            "skills": "5e-SRD-Skills.json",
            "spells": "5e-SRD-Spells.json",
            "subclasses": "5e-SRD-Subclasses.json",
            "subraces": "5e-SRD-Subraces.json",
            "traits": "5e-SRD-Traits.json",
            "weapon_properties": "5e-SRD-Weapon-Properties.json",
        }

        for key, filename in files.items():
            filepath = self._data_dir / filename
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._data[key] = data
                    # Build index by 'index' field
                    self._index[key] = {item["index"]: item for item in data}
                logger.debug(f"Loaded {len(data)} entries from {filename}")
            else:
                logger.warning(f"SRD file not found: {filepath}")
                self._data[key] = []
                self._index[key] = {}

        total = sum(len(v) for v in self._data.values())
        logger.info(f"SRD Repository loaded: {total} entries across {len(self._data)} categories")

    # -----------------------------------------------------------------------
    # Lookup Methods
    # -----------------------------------------------------------------------

    def get_race(self, index: str) -> dict[str, Any] | None:
        return self._index.get("races", {}).get(index)

    def list_races(self) -> list[dict[str, Any]]:
        return self._data.get("races", [])

    def get_class(self, index: str) -> dict[str, Any] | None:
        return self._index.get("classes", {}).get(index)

    def list_classes(self) -> list[dict[str, Any]]:
        return self._data.get("classes", [])

    def get_spell(self, index: str) -> dict[str, Any] | None:
        return self._index.get("spells", {}).get(index)

    def list_spells(self) -> list[dict[str, Any]]:
        return self._data.get("spells", [])

    def spells_for_class(self, class_index: str, max_level: int = 9) -> list[dict[str, Any]]:
        """Get all spells available to a class up to a given level."""
        return [
            spell for spell in self._data.get("spells", [])
            if spell.get("level", 0) <= max_level
            and any(
                c.get("index") == class_index
                for c in spell.get("classes", [])
            )
        ]

    def cantrips_for_class(self, class_index: str) -> list[dict[str, Any]]:
        return self.spells_for_class(class_index, max_level=0)

    def get_equipment(self, index: str) -> dict[str, Any] | None:
        return self._index.get("equipment", {}).get(index)

    def list_equipment(self) -> list[dict[str, Any]]:
        return self._data.get("equipment", [])

    def weapons(self) -> list[dict[str, Any]]:
        return [
            e for e in self._data.get("equipment", [])
            if e.get("equipment_category", {}).get("index") == "weapon"
        ]

    def armor(self) -> list[dict[str, Any]]:
        return [
            e for e in self._data.get("equipment", [])
            if e.get("equipment_category", {}).get("index") == "armor"
        ]

    def get_background(self, index: str) -> dict[str, Any] | None:
        return self._index.get("backgrounds", {}).get(index)

    def list_backgrounds(self) -> list[dict[str, Any]]:
        return self._data.get("backgrounds", [])

    def get_skill(self, index: str) -> dict[str, Any] | None:
        return self._index.get("skills", {}).get(index)

    def list_skills(self) -> list[dict[str, Any]]:
        return self._data.get("skills", [])

    def get_condition(self, index: str) -> dict[str, Any] | None:
        return self._index.get("conditions", {}).get(index)

    def list_conditions(self) -> list[dict[str, Any]]:
        return self._data.get("conditions", [])

    def get_subclass(self, index: str) -> dict[str, Any] | None:
        return self._index.get("subclasses", {}).get(index)

    def get_subrace(self, index: str) -> dict[str, Any] | None:
        return self._index.get("subraces", {}).get(index)

    def subraces_for_race(self, race_index: str) -> list[dict[str, Any]]:
        race = self.get_race(race_index)
        if not race:
            return []
        subrace_refs = race.get("subraces", [])
        return [
            sr for sr in self._data.get("subraces", [])
            if sr["index"] in {ref["index"] for ref in subrace_refs}
        ]

    def get_feature(self, index: str) -> dict[str, Any] | None:
        return self._index.get("features", {}).get(index)

    def features_for_class(self, class_index: str, level: int = 1) -> list[dict[str, Any]]:
        """Get class features up to a given level."""
        return [
            f for f in self._data.get("features", [])
            if f.get("class", {}).get("index") == class_index
            and f.get("level", 1) <= level
        ]

    def get_level_data(self, class_index: str, level: int) -> dict[str, Any] | None:
        """Get the level progression data for a class at a specific level.

        Filters out subclass-specific entries to return the base class data.
        """
        for entry in self._data.get("levels", []):
            if (entry.get("class", {}).get("index") == class_index
                    and entry.get("level") == level
                    and entry.get("subclass") is None):
                return entry
        return None

    def get_trait(self, index: str) -> dict[str, Any] | None:
        return self._index.get("traits", {}).get(index)

    def traits_for_race(self, race_index: str) -> list[dict[str, Any]]:
        race = self.get_race(race_index)
        if not race:
            return []
        trait_refs = race.get("traits", [])
        return [
            t for t in self._data.get("traits", [])
            if t["index"] in {ref["index"] for ref in trait_refs}
        ]

    def spell_slots_for_class_level(self, class_index: str, level: int) -> dict[int, int]:
        """Get spell slots by spell level for a class at a given character level.

        Returns: {1: 4, 2: 3, 3: 2} meaning 4 first-level slots, 3 second-level, etc.
        """
        level_data = self.get_level_data(class_index, level)
        if not level_data or "spellcasting" not in level_data:
            return {}

        spellcasting = level_data["spellcasting"]
        slots = {}
        for i in range(1, 10):
            key = f"spell_slots_level_{i}"
            if key in spellcasting and spellcasting[key] > 0:
                slots[i] = spellcasting[key]
        return slots

    def starting_equipment(self, class_index: str) -> list[dict[str, Any]]:
        """Get the starting equipment for a class."""
        cls = self.get_class(class_index)
        if not cls:
            return []
        return cls.get("starting_equipment", [])
