"use client";

import { useWizardStore } from "@/stores/wizard-store";

const TONES = [
  { value: "epic_fantasy", label: "Epic Fantasy", desc: "Grand quests, ancient magic, legendary heroes" },
  { value: "dark_gritty", label: "Dark & Gritty", desc: "Moral ambiguity, scarce magic, harsh consequences" },
  { value: "lighthearted", label: "Lighthearted", desc: "Fun, quirky NPCs, low stakes" },
  { value: "horror", label: "Horror", desc: "Creeping dread, hidden horrors" },
  { value: "mystery", label: "Mystery", desc: "Intrigue, clues, a central mystery" },
];

export function StepTone() {
  const { campaignName, tone, combatEmphasis, updateField } = useWizardStore();

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">Campaign Name</label>
        <input
          type="text"
          value={campaignName}
          onChange={(e) => updateField("campaignName", e.target.value)}
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          placeholder="The Lost Mines of Phandelver"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-3">Campaign Tone</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {TONES.map((t) => (
            <button
              key={t.value}
              onClick={() => updateField("tone", t.value)}
              className={`text-left p-3 rounded-lg border transition-colors ${
                tone === t.value
                  ? "border-amber-500 bg-amber-900/20"
                  : "border-neutral-700 bg-neutral-800 hover:border-neutral-600"
              }`}
            >
              <div className="font-medium text-white">{t.label}</div>
              <div className="text-xs text-neutral-400 mt-1">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-2">
          Combat vs Roleplay: {combatEmphasis < 0.3 ? "Roleplay-heavy" : combatEmphasis > 0.7 ? "Combat-heavy" : "Balanced"}
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={combatEmphasis}
          onChange={(e) => updateField("combatEmphasis", parseFloat(e.target.value))}
          className="w-full accent-amber-500"
        />
        <div className="flex justify-between text-xs text-neutral-500">
          <span>Roleplay</span>
          <span>Combat</span>
        </div>
      </div>
    </div>
  );
}
