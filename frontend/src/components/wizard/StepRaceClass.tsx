"use client";

import { useEffect, useState } from "react";
import { useWizardStore } from "@/stores/wizard-store";
import { api } from "@/lib/api";
import { SpellPicker } from "./SpellPicker";

type RaceSummary = {
  index: string;
  name: string;
  speed: number;
  size: string;
  ability_bonuses: { ability: string; bonus: number }[];
  traits: string[];
};

type ClassSummary = {
  index: string;
  name: string;
  hit_die: number;
  saving_throws: string[];
  has_spellcasting: boolean;
};

type SpellcastingConfig = {
  has_spellcasting: boolean;
  cantrips_known: number;
  spells_known: number | null;
  spell_slots: Record<string, number>;
  caster_type: "known" | "prepared" | "none";
};

export function StepRaceClass() {
  const { raceIndex, classIndex, abilities, updateField, clearSpells } = useWizardStore();
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [spellConfig, setSpellConfig] = useState<SpellcastingConfig | null>(null);

  useEffect(() => {
    api<RaceSummary[]>("/srd/races").then(setRaces).catch(() => {});
    api<ClassSummary[]>("/srd/classes").then(setClasses).catch(() => {});
  }, []);

  // Fetch spellcasting config when class changes
  useEffect(() => {
    if (!classIndex) {
      setSpellConfig(null);
      return;
    }
    clearSpells();
    api<SpellcastingConfig>(`/srd/classes/${classIndex}/spellcasting`)
      .then(setSpellConfig)
      .catch(() => setSpellConfig(null));
  }, [classIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // For prepared casters (cleric/druid), compute spells from WIS modifier
  const computedSpellsMax = spellConfig?.spells_known
    ?? (spellConfig?.caster_type === "prepared"
      ? Math.max(1, Math.floor((abilities.wisdom - 10) / 2) + 1)
      : 0);

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-3">Choose Your Race</label>
        <div className="grid grid-cols-3 gap-2">
          {races.map((race) => (
            <button
              key={race.index}
              onClick={() => updateField("raceIndex", race.index)}
              className={`p-3 rounded-lg border text-left transition-colors ${
                raceIndex === race.index
                  ? "border-amber-500 bg-amber-900/20"
                  : "border-neutral-700 bg-neutral-800 hover:border-neutral-600"
              }`}
            >
              <div className="font-medium text-white text-sm">{race.name}</div>
              <div className="text-xs text-neutral-400 mt-1">
                {race.ability_bonuses.map((b) => `${b.ability.toUpperCase()} +${b.bonus}`).join(", ")}
              </div>
              <div className="text-xs text-neutral-500">Speed {race.speed}</div>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-3">Choose Your Class</label>
        <div className="grid grid-cols-3 gap-2">
          {classes.map((cls) => (
            <button
              key={cls.index}
              onClick={() => updateField("classIndex", cls.index)}
              className={`p-3 rounded-lg border text-left transition-colors ${
                classIndex === cls.index
                  ? "border-amber-500 bg-amber-900/20"
                  : "border-neutral-700 bg-neutral-800 hover:border-neutral-600"
              }`}
            >
              <div className="font-medium text-white text-sm">{cls.name}</div>
              <div className="text-xs text-neutral-400 mt-1">
                Hit Die: d{cls.hit_die}
                {cls.has_spellcasting && " · Spellcaster"}
              </div>
              <div className="text-xs text-neutral-500">
                Saves: {cls.saving_throws.map((s) => s.toUpperCase()).join(", ")}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Spell Selection (for caster classes) */}
      {spellConfig && spellConfig.has_spellcasting && spellConfig.caster_type !== "none" && (
        <SpellPicker
          classIndex={classIndex}
          cantripsMax={spellConfig.cantrips_known}
          spellsMax={computedSpellsMax}
          casterType={spellConfig.caster_type as "known" | "prepared"}
        />
      )}
    </div>
  );
}
