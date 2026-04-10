"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

function modifier(score: number): string {
  const mod = Math.floor((score - 10) / 2);
  return mod >= 0 ? `+${mod}` : `${mod}`;
}

type CharacterData = {
  name: string; race: string; class: string; level: number;
  hp: number; max_hp: number; ac: number; speed: number;
  proficiency_bonus: number; xp: number;
  abilities: Record<string, number>;
  modifiers: Record<string, number>;
  conditions: string[];
  proficiencies: string[];
  background: string;
  graph_context: { fact: string; type: string }[];
};

function CharacterPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<CharacterData | null>(null);

  useEffect(() => {
    if (accessToken) {
      api<CharacterData>(`/gamestate/${campaignId}/character`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  if (!data) return <div className="text-sm text-neutral-500">Loading...</div>;

  const ABILITY_LABELS: Record<string, string> = {
    strength: "STR", dexterity: "DEX", constitution: "CON",
    intelligence: "INT", wisdom: "WIS", charisma: "CHA",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-neutral-700 rounded-full flex items-center justify-center text-xl">
          🎭
        </div>
        <div>
          <h3 className="text-lg font-bold text-white">{data.name}</h3>
          <p className="text-sm text-neutral-400">{data.race} {data.class} · Level {data.level}</p>
        </div>
      </div>

      {/* HP / AC / Speed */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-neutral-800 rounded-lg p-2 text-center">
          <div className="text-xs text-neutral-500">HP</div>
          <div className="text-lg font-bold text-red-400">{data.hp}/{data.max_hp}</div>
        </div>
        <div className="bg-neutral-800 rounded-lg p-2 text-center">
          <div className="text-xs text-neutral-500">AC</div>
          <div className="text-lg font-bold text-blue-400">{data.ac}</div>
        </div>
        <div className="bg-neutral-800 rounded-lg p-2 text-center">
          <div className="text-xs text-neutral-500">Speed</div>
          <div className="text-lg font-bold text-green-400">{data.speed}ft</div>
        </div>
      </div>

      {/* Abilities */}
      {Object.keys(data.abilities).length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-2">Abilities</div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1">
            {Object.entries(data.abilities).map(([key, score]) => (
              <div key={key} className="bg-neutral-800 rounded p-1.5 text-center">
                <div className="text-[10px] text-neutral-500">{ABILITY_LABELS[key] || key}</div>
                <div className="text-sm font-bold text-white">{score}</div>
                <div className="text-[10px] text-amber-500">{modifier(score)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conditions */}
      {data.conditions.length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1">Conditions</div>
          <div className="flex flex-wrap gap-1">
            {data.conditions.map((c) => (
              <span key={c} className="px-2 py-0.5 bg-red-900/30 border border-red-800 text-red-300 rounded text-xs">{c}</span>
            ))}
          </div>
        </div>
      )}

      {/* Context from Graph */}
      {data.graph_context.length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1">World Knowledge</div>
          <div className="space-y-1">
            {data.graph_context.map((f, i) => (
              <div key={i} className="text-xs text-neutral-400 bg-neutral-800 rounded px-2 py-1">{f.fact}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InventoryPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<{ items: { name: string; quantity: number; source: string }[]; total: number } | null>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/inventory`, { token: accessToken }).then(setData as any).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Inventory {data ? `(${data.total})` : ""}</h3>
      {data && data.items.length > 0 ? (
        <div className="space-y-1">
          {data.items.map((item, i) => (
            <div key={i} className="flex items-center justify-between bg-neutral-800 rounded px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-neutral-500">{item.source === "found" ? "✨" : "📦"}</span>
                <span className="text-sm text-neutral-200">{item.name}</span>
              </div>
              {item.quantity > 1 && (
                <span className="text-xs text-neutral-500">x{item.quantity}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-neutral-500 py-4 text-center">
          Your pack is empty. Acquire items during your adventure.
        </div>
      )}
    </div>
  );
}

type SpellEntry = { index: string; name: string; level: number; school: string };
type SpellbookData = {
  cantrips: SpellEntry[];
  spells: SpellEntry[];
  spell_slots: Record<string, { max: number; current: number }>;
  total: number;
};

function SpellbookPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<SpellbookData | null>(null);

  useEffect(() => {
    if (accessToken) {
      api<SpellbookData>(`/gamestate/${campaignId}/spellbook`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Spellbook</h3>

      {/* Spell Slots */}
      {data?.spell_slots && Object.keys(data.spell_slots).length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-2">Spell Slots</div>
          <div className="flex gap-3">
            {Object.entries(data.spell_slots).map(([level, slots]) => (
              <div key={level} className="text-center">
                <div className="text-[10px] text-neutral-500">Lvl {level}</div>
                <div className="flex gap-0.5 mt-1">
                  {Array.from({ length: slots.max }).map((_, i) => (
                    <div
                      key={i}
                      className={`w-3 h-3 rounded-full ${
                        i < slots.current ? "bg-amber-500" : "bg-neutral-700"
                      }`}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cantrips */}
      {data && data.cantrips.length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1">Cantrips</div>
          <div className="space-y-1">
            {data.cantrips.map((spell) => (
              <div key={spell.index} className="bg-neutral-800 rounded px-3 py-2 flex items-center justify-between">
                <span className="text-sm text-amber-300">{spell.name}</span>
                <span className="text-[10px] text-neutral-500">{spell.school}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leveled Spells */}
      {data && data.spells.length > 0 ? (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1">Spells</div>
          <div className="space-y-1">
            {data.spells.map((spell, i) => (
              <div key={spell.index || i} className="bg-neutral-800 rounded px-3 py-2 flex items-center justify-between">
                <span className="text-sm text-neutral-200">{spell.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-neutral-500">{spell.school}</span>
                  {spell.level > 0 && <span className="text-[10px] text-neutral-600">Lvl {spell.level}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : data && data.cantrips.length === 0 ? (
        <div className="text-sm text-neutral-500 py-4 text-center">
          No spells known yet.
        </div>
      ) : null}
    </div>
  );
}

function QuestPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<{ active: { fact: string }[]; completed: { fact: string }[] } | null>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/quests`, { token: accessToken }).then(setData as any).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Quest Log</h3>

      {data && data.active.length > 0 ? (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1">Active Quests</div>
          <div className="space-y-1">
            {data.active.map((q, i) => (
              <div key={i} className="bg-neutral-800 rounded px-3 py-2 flex items-start gap-2">
                <span className="text-amber-500 mt-0.5">◆</span>
                <span className="text-sm text-neutral-200">{q.fact}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-sm text-neutral-500 py-4 text-center">
          No active quests. Explore the world to discover adventures.
        </div>
      )}

      {data && data.completed.length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 font-semibold mb-1 mt-4">Completed</div>
          <div className="space-y-1">
            {data.completed.map((q, i) => (
              <div key={i} className="bg-neutral-800/50 rounded px-3 py-2 flex items-start gap-2 opacity-60">
                <span className="text-green-500 mt-0.5">✓</span>
                <span className="text-sm text-neutral-400">{q.fact}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function OverlayPanel({
  panel,
  campaignId,
  onClose,
}: {
  panel: string;
  campaignId: string;
  onClose: () => void;
}) {
  return (
    <div className="absolute inset-x-0 bottom-0 top-16 bg-neutral-900/95 backdrop-blur-sm z-20 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-4">
        <div className="flex justify-end mb-4">
          <button onClick={onClose} className="text-neutral-400 hover:text-white text-sm px-2 py-1">
            Close ✕
          </button>
        </div>

        {panel === "character" && <CharacterPanel campaignId={campaignId} />}
        {panel === "inventory" && <InventoryPanel campaignId={campaignId} />}
        {panel === "spellbook" && <SpellbookPanel campaignId={campaignId} />}
        {panel === "quests" && <QuestPanel campaignId={campaignId} />}
      </div>
    </div>
  );
}
