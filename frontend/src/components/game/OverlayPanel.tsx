"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

function CharacterPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/character`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Character Sheet</h3>
      {data ? (
        <div className="space-y-2">
          <div className="text-white font-medium">{data.name}</div>
          <div className="text-sm text-neutral-400">Turn {data.current_turn}</div>
          {data.graph_facts?.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-neutral-500 font-semibold">Known Facts</div>
              {data.graph_facts.map((f: any, i: number) => (
                <div key={i} className="text-xs text-neutral-400 bg-neutral-800 rounded px-2 py-1">
                  {f.fact}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-neutral-500">Loading...</div>
      )}
    </div>
  );
}

function InventoryPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/inventory`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Inventory</h3>
      {data?.items?.length > 0 ? (
        <div className="space-y-1">
          {data.items.map((item: any, i: number) => (
            <div key={i} className="flex justify-between items-center bg-neutral-800 rounded px-3 py-2">
              <span className="text-sm text-neutral-200">{item.fact}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-neutral-500">Your inventory is empty. Acquire items during your adventure.</div>
      )}
    </div>
  );
}

function SpellbookPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/spellbook`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Spellbook</h3>
      {data?.spells?.length > 0 ? (
        <div className="space-y-1">
          {data.spells.map((spell: any, i: number) => (
            <div key={i} className="bg-neutral-800 rounded px-3 py-2">
              <span className="text-sm text-neutral-200">{spell.fact}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-neutral-500">No spells known. Spellcasting classes learn spells as they level up.</div>
      )}
    </div>
  );
}

function QuestPanel({ campaignId }: { campaignId: string }) {
  const { accessToken } = useAuthStore();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (accessToken) {
      api(`/gamestate/${campaignId}/quests`, { token: accessToken }).then(setData).catch(() => {});
    }
  }, [campaignId, accessToken]);

  return (
    <div className="space-y-3">
      <h3 className="text-amber-500 font-semibold">Quest Log</h3>
      {data?.quests?.length > 0 ? (
        <div className="space-y-1">
          {data.quests.map((quest: any, i: number) => (
            <div key={i} className="bg-neutral-800 rounded px-3 py-2">
              <span className="text-sm text-neutral-200">{quest.fact}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-neutral-500">No active quests. Explore the world to discover quests.</div>
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
        <div className="flex justify-between items-center mb-4">
          <div />
          <button onClick={onClose} className="text-neutral-400 hover:text-white text-sm">
            Close &times;
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
