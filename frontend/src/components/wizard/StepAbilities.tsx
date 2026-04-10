"use client";

import { useWizardStore, type AbilityScores } from "@/stores/wizard-store";

const ABILITIES: (keyof AbilityScores)[] = [
  "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma",
];

const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8];

const LABELS: Record<string, string> = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

function modifier(score: number): string {
  const mod = Math.floor((score - 10) / 2);
  return mod >= 0 ? `+${mod}` : `${mod}`;
}

export function StepAbilities() {
  const { abilities, scoreMethod, updateAbility, updateField } = useWizardStore();

  const applyStandardArray = () => {
    updateField("scoreMethod", "standard");
    ABILITIES.forEach((ability, i) => updateAbility(ability, STANDARD_ARRAY[i]));
  };

  const rollScores = () => {
    updateField("scoreMethod", "roll");
    ABILITIES.forEach((ability) => {
      // 4d6 drop lowest
      const rolls = Array.from({ length: 4 }, () => Math.floor(Math.random() * 6) + 1);
      rolls.sort((a, b) => b - a);
      updateAbility(ability, rolls[0] + rolls[1] + rolls[2]);
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">Character Name</label>
        <input
          type="text"
          value={useWizardStore.getState().characterName}
          onChange={(e) => updateField("characterName", e.target.value)}
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          placeholder="Aldric Stormborn"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-3">Ability Score Method</label>
        <div className="flex gap-2 mb-4">
          <button
            onClick={applyStandardArray}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              scoreMethod === "standard" ? "border-amber-500 bg-amber-900/20 text-white" : "border-neutral-700 text-neutral-400 hover:text-white"
            }`}
          >
            Standard Array
          </button>
          <button
            onClick={rollScores}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              scoreMethod === "roll" ? "border-amber-500 bg-amber-900/20 text-white" : "border-neutral-700 text-neutral-400 hover:text-white"
            }`}
          >
            Roll 4d6
          </button>
          <button
            onClick={() => updateField("scoreMethod", "pointbuy")}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              scoreMethod === "pointbuy" ? "border-amber-500 bg-amber-900/20 text-white" : "border-neutral-700 text-neutral-400 hover:text-white"
            }`}
          >
            Point Buy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {ABILITIES.map((ability) => (
          <div key={ability} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 text-center">
            <div className="text-xs text-neutral-400 font-semibold">{LABELS[ability]}</div>
            <div className="text-2xl font-bold text-white mt-1">{abilities[ability]}</div>
            <div className="text-sm text-amber-500">{modifier(abilities[ability])}</div>
            {scoreMethod === "pointbuy" && (
              <div className="flex justify-center gap-2 mt-2">
                <button
                  onClick={() => updateAbility(ability, Math.max(8, abilities[ability] - 1))}
                  className="w-6 h-6 rounded bg-neutral-700 text-white text-sm hover:bg-neutral-600"
                >
                  -
                </button>
                <button
                  onClick={() => updateAbility(ability, Math.min(15, abilities[ability] + 1))}
                  className="w-6 h-6 rounded bg-neutral-700 text-white text-sm hover:bg-neutral-600"
                >
                  +
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
