"""
SRD data API endpoints for DungeonMasterONE.

Serves D&D 5e SRD data to the frontend for the character creation wizard.
No auth required — SRD data is public (CC-BY-4.0).
"""

from fastapi import APIRouter

from dm1.rules.srd_repository import SRDRepository

router = APIRouter(prefix="/srd", tags=["srd"])


def _summarize_race(race: dict) -> dict:
    return {
        "index": race["index"],
        "name": race["name"],
        "speed": race["speed"],
        "size": race.get("size", "Medium"),
        "ability_bonuses": [
            {"ability": ab["ability_score"]["index"], "bonus": ab["bonus"]}
            for ab in race.get("ability_bonuses", [])
        ],
        "languages": [lang["name"] for lang in race.get("languages", [])],
        "traits": [t["name"] for t in race.get("traits", [])],
        "subraces": [sr["index"] for sr in race.get("subraces", [])],
    }


def _summarize_class(cls: dict) -> dict:
    return {
        "index": cls["index"],
        "name": cls["name"],
        "hit_die": cls["hit_die"],
        "saving_throws": [st["index"] for st in cls.get("saving_throws", [])],
        "proficiencies": [p["name"] for p in cls.get("proficiencies", [])],
        "has_spellcasting": "spellcasting" in cls,
        "subclasses": [sc["index"] for sc in cls.get("subclasses", [])],
    }


def _summarize_spell(spell: dict) -> dict:
    result = {
        "index": spell["index"],
        "name": spell["name"],
        "level": spell["level"],
        "school": spell.get("school", {}).get("name", ""),
        "casting_time": spell.get("casting_time", ""),
        "range": spell.get("range", ""),
        "components": spell.get("components", []),
        "duration": spell.get("duration", ""),
        "concentration": spell.get("concentration", False),
        "ritual": spell.get("ritual", False),
        "desc": spell.get("desc", []),
        "classes": [c["index"] for c in spell.get("classes", [])],
    }
    if "damage" in spell:
        result["damage"] = spell["damage"]
    if "heal_at_slot_level" in spell:
        result["healing"] = True
    return result


@router.get("/races")
async def list_races():
    srd = SRDRepository.get()
    return [_summarize_race(r) for r in srd.list_races()]


@router.get("/races/{index}")
async def get_race(index: str):
    srd = SRDRepository.get()
    race = srd.get_race(index)
    if not race:
        return {"error": "Race not found"}
    result = _summarize_race(race)
    # Include full traits for detail view
    result["trait_details"] = [
        {"name": t["name"], "desc": t.get("desc", [])}
        for t in srd.traits_for_race(index)
    ]
    result["subrace_details"] = [
        {
            "index": sr["index"],
            "name": sr["name"],
            "ability_bonuses": [
                {"ability": ab["ability_score"]["index"], "bonus": ab["bonus"]}
                for ab in sr.get("ability_bonuses", [])
            ],
            "desc": sr.get("desc", ""),
        }
        for sr in srd.subraces_for_race(index)
    ]
    return result


@router.get("/classes")
async def list_classes():
    srd = SRDRepository.get()
    return [_summarize_class(c) for c in srd.list_classes()]


@router.get("/classes/{index}")
async def get_class(index: str):
    srd = SRDRepository.get()
    cls = srd.get_class(index)
    if not cls:
        return {"error": "Class not found"}
    result = _summarize_class(cls)
    # Level 1 features
    result["features"] = [
        {"name": f["name"], "desc": f.get("desc", []), "level": f.get("level", 1)}
        for f in srd.features_for_class(index, level=1)
    ]
    # Spell slots at level 1 (if spellcaster)
    result["spell_slots"] = srd.spell_slots_for_class_level(index, 1)
    # Starting equipment options
    result["starting_equipment"] = cls.get("starting_equipment", [])
    result["starting_equipment_options"] = cls.get("starting_equipment_options", [])
    return result


@router.get("/classes/{index}/spells")
async def get_class_spells(index: str, max_level: int = 1):
    srd = SRDRepository.get()
    spells = srd.spells_for_class(index, max_level=max_level)
    return [_summarize_spell(s) for s in spells]


@router.get("/spells")
async def list_spells(class_index: str | None = None, max_level: int = 9):
    srd = SRDRepository.get()
    if class_index:
        spells = srd.spells_for_class(class_index, max_level=max_level)
    else:
        spells = [s for s in srd.list_spells() if s["level"] <= max_level]
    return [_summarize_spell(s) for s in spells]


@router.get("/skills")
async def list_skills():
    srd = SRDRepository.get()
    return [
        {
            "index": s["index"],
            "name": s["name"],
            "ability": s.get("ability_score", {}).get("index", ""),
        }
        for s in srd.list_skills()
    ]


@router.get("/backgrounds")
async def list_backgrounds():
    srd = SRDRepository.get()
    return [
        {
            "index": b["index"],
            "name": b["name"],
            "starting_proficiencies": [p["name"] for p in b.get("starting_proficiencies", [])],
            "feature": b.get("feature", {}),
        }
        for b in srd.list_backgrounds()
    ]


@router.get("/equipment")
async def list_equipment(category: str | None = None):
    srd = SRDRepository.get()
    equipment = srd.list_equipment()
    if category:
        equipment = [e for e in equipment if e.get("equipment_category", {}).get("index") == category]
    return [
        {
            "index": e["index"],
            "name": e["name"],
            "category": e.get("equipment_category", {}).get("index", ""),
            "cost": e.get("cost", {}),
            "weight": e.get("weight", 0),
        }
        for e in equipment
    ]
