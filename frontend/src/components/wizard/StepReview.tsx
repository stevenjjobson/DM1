"use client";

import { useWizardStore } from "@/stores/wizard-store";

function modifier(score: number): string {
  const mod = Math.floor((score - 10) / 2);
  return mod >= 0 ? `+${mod}` : `${mod}`;
}

const LABELS: Record<string, string> = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

export function StepReview() {
  const state = useWizardStore();

  const raceName = state.raceIndex.charAt(0).toUpperCase() + state.raceIndex.slice(1).replace("-", " ");
  const className = state.classIndex.charAt(0).toUpperCase() + state.classIndex.slice(1);

  return (
    <div className="space-y-6">
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
        <h3 className="text-lg font-bold text-amber-500">{state.characterName || "Unnamed Adventurer"}</h3>
        <p className="text-neutral-300 mt-1">{raceName} {className}</p>
        <p className="text-xs text-neutral-500 mt-1">Campaign: {state.campaignName} · {state.tone.replace("_", " ")}</p>
      </div>

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-2">Ability Scores</h4>
        <div className="grid grid-cols-6 gap-2">
          {Object.entries(state.abilities).map(([ability, score]) => (
            <div key={ability} className="bg-neutral-800 border border-neutral-700 rounded p-2 text-center">
              <div className="text-xs text-neutral-400">{LABELS[ability]}</div>
              <div className="text-lg font-bold text-white">{score}</div>
              <div className="text-xs text-amber-500">{modifier(score)}</div>
            </div>
          ))}
        </div>
      </div>

      {state.selectedSpells.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-neutral-300 mb-2">Selected Spells</h4>
          <div className="flex flex-wrap gap-2">
            {state.selectedSpells.map((spell) => (
              <span key={spell} className="px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-xs text-neutral-300">
                {spell.replace(/-/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {state.backstory && (
        <div>
          <h4 className="text-sm font-medium text-neutral-300 mb-2">Backstory</h4>
          <p className="text-sm text-neutral-400 bg-neutral-800 border border-neutral-700 rounded-lg p-3">
            {state.backstory}
          </p>
        </div>
      )}

      {Object.keys(state.appearance).length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-neutral-300 mb-2">Appearance</h4>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(state.appearance).filter(([, v]) => v).map(([key, value]) => (
              <div key={key} className="text-xs">
                <span className="text-neutral-500 capitalize">{key}:</span>{" "}
                <span className="text-neutral-300">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
