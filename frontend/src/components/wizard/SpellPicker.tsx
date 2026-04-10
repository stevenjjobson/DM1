"use client";

import { useEffect, useState } from "react";
import { useWizardStore } from "@/stores/wizard-store";
import { api } from "@/lib/api";

type SpellSummary = {
  index: string;
  name: string;
  level: number;
  school: string;
  casting_time: string;
  range: string;
  components: string[];
  duration: string;
  concentration: boolean;
  ritual: boolean;
  desc: string[];
  classes: string[];
};

export function SpellPicker({
  classIndex,
  cantripsMax,
  spellsMax,
  casterType,
}: {
  classIndex: string;
  cantripsMax: number;
  spellsMax: number;
  casterType: "known" | "prepared";
}) {
  const { selectedCantrips, selectedSpells, toggleCantrip, toggleSpell } = useWizardStore();
  const [cantrips, setCantrips] = useState<SpellSummary[]>([]);
  const [spells, setSpells] = useState<SpellSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api<SpellSummary[]>(`/srd/classes/${classIndex}/spells?max_level=1`)
      .then((data) => {
        setCantrips(data.filter((s) => s.level === 0));
        setSpells(data.filter((s) => s.level === 1));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [classIndex]);

  if (loading) {
    return <div className="text-sm text-neutral-500 py-4">Loading spells...</div>;
  }

  const cantripLabel = casterType === "prepared" ? "Prepare" : "Learn";

  return (
    <div className="space-y-6 mt-6 border-t border-neutral-700 pt-6">
      {/* Cantrips */}
      {cantripsMax > 0 && cantrips.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-neutral-300 mb-2">
            Cantrips ({selectedCantrips.length}/{cantripsMax})
          </label>
          <div className="grid grid-cols-2 gap-2">
            {cantrips.map((spell) => {
              const selected = selectedCantrips.includes(spell.index);
              const atLimit = selectedCantrips.length >= cantripsMax && !selected;
              return (
                <button
                  key={spell.index}
                  onClick={() => !atLimit && toggleCantrip(spell.index)}
                  disabled={atLimit}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    selected
                      ? "border-amber-500 bg-amber-900/20"
                      : atLimit
                        ? "border-neutral-800 bg-neutral-900 opacity-40 cursor-not-allowed"
                        : "border-neutral-700 bg-neutral-800 hover:border-neutral-600"
                  }`}
                >
                  <div className="font-medium text-white text-sm">{spell.name}</div>
                  <div className="text-xs text-neutral-400 mt-0.5">
                    {spell.school} &middot; {spell.casting_time}
                  </div>
                  <div className="text-xs text-neutral-500 mt-1 line-clamp-2">
                    {spell.desc[0]?.split(".")[0]}.
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Level 1 Spells */}
      {spellsMax > 0 && spells.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-neutral-300 mb-2">
            Level 1 Spells &mdash; {cantripLabel} ({selectedSpells.length}/{spellsMax})
          </label>
          <div className="grid grid-cols-2 gap-2">
            {spells.map((spell) => {
              const selected = selectedSpells.includes(spell.index);
              const atLimit = selectedSpells.length >= spellsMax && !selected;
              return (
                <button
                  key={spell.index}
                  onClick={() => !atLimit && toggleSpell(spell.index)}
                  disabled={atLimit}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    selected
                      ? "border-amber-500 bg-amber-900/20"
                      : atLimit
                        ? "border-neutral-800 bg-neutral-900 opacity-40 cursor-not-allowed"
                        : "border-neutral-700 bg-neutral-800 hover:border-neutral-600"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-white text-sm">{spell.name}</span>
                    {spell.concentration && (
                      <span className="text-[10px] text-amber-500 font-semibold">C</span>
                    )}
                    {spell.ritual && (
                      <span className="text-[10px] text-blue-400 font-semibold">R</span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-400 mt-0.5">
                    {spell.school} &middot; {spell.range} &middot; {spell.components.join(", ")}
                  </div>
                  <div className="text-xs text-neutral-500 mt-1 line-clamp-2">
                    {spell.desc[0]?.split(".")[0]}.
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
