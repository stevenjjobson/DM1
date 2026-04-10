"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useCampaignStore, type Campaign } from "@/stores/campaign-store";

function CampaignCard({ campaign, onDelete, onArchive, onDuplicate }: {
  campaign: Campaign;
  onDelete: (id: string) => void;
  onArchive: (id: string) => void;
  onDuplicate: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const router = useRouter();

  const toneLabels: Record<string, string> = {
    epic_fantasy: "Epic Fantasy",
    dark_gritty: "Dark & Gritty",
    lighthearted: "Lighthearted",
    horror: "Horror",
    mystery: "Mystery",
    custom: "Custom",
  };

  return (
    <div
      className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:border-amber-600 transition-colors cursor-pointer relative"
      onClick={() => router.push(`/campaign/${campaign.id}/game`)}
    >
      <div className="flex justify-between items-start">
        <div className="flex items-start gap-3">
          {campaign.portrait_url ? (
            <img src={campaign.portrait_url} alt="" className="w-10 h-10 rounded-full object-cover border border-amber-700 shrink-0" />
          ) : (
            <div className="w-10 h-10 rounded-full bg-neutral-700 border border-neutral-600 flex items-center justify-center text-sm text-neutral-400 shrink-0">
              {campaign.name.charAt(0)}
            </div>
          )}
          <div>
            <h3 className="text-lg font-semibold text-white">{campaign.name}</h3>
            <p className="text-sm text-neutral-400 mt-1">
              {toneLabels[campaign.settings.tone] || campaign.settings.tone}
              {campaign.current_turn > 0 && ` · Turn ${campaign.current_turn}`}
            </p>
            <p className="text-xs text-neutral-500 mt-2">
              {campaign.status === "creating" ? "Setting up..." : `Last played ${campaign.last_played_at ? new Date(campaign.last_played_at).toLocaleDateString() : "never"}`}
            </p>
          </div>
        </div>

        <button
          onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
          className="text-neutral-400 hover:text-white p-1"
        >
          &#8942;
        </button>
      </div>

      {menuOpen && (
        <div className="absolute right-2 top-12 bg-neutral-900 border border-neutral-700 rounded-md shadow-lg z-10 py-1 min-w-[140px]">
          <button onClick={(e) => { e.stopPropagation(); onDuplicate(campaign.id); setMenuOpen(false); }}
            className="block w-full text-left px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800">
            Duplicate
          </button>
          <button onClick={(e) => { e.stopPropagation(); onArchive(campaign.id); setMenuOpen(false); }}
            className="block w-full text-left px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800">
            Archive
          </button>
          <button onClick={(e) => { e.stopPropagation(); onDelete(campaign.id); setMenuOpen(false); }}
            className="block w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-neutral-800">
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout, _hasHydrated } = useAuthStore();
  const { campaigns, isLoading, fetchCampaigns, createCampaign, deleteCampaign, archiveCampaign, duplicateCampaign } = useCampaignStore();

  useEffect(() => {
    if (!_hasHydrated) return; // Wait for localStorage to load
    if (!user) {
      router.push("/login");
      return;
    }
    fetchCampaigns();
  }, [user, _hasHydrated, router, fetchCampaigns]);

  const handleNewCampaign = () => {
    router.push("/campaign/new");
  };

  if (!_hasHydrated || !user) return null;

  return (
    <div className="min-h-screen bg-neutral-950">
      <header className="border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-amber-500">DungeonMasterONE</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-neutral-400">{user.display_name}</span>
          <button
            onClick={() => router.push("/settings")}
            className="text-neutral-500 hover:text-neutral-300 text-lg"
            title="Settings"
          >
            &#9881;
          </button>
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="text-xs text-neutral-500 hover:text-red-400 transition-colors"
            title="Sign out"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-white">Your Adventures</h2>
          <button
            onClick={handleNewCampaign}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-medium rounded-md transition-colors"
          >
            + New Adventure
          </button>
        </div>

        {isLoading ? (
          <div className="text-center py-12 text-neutral-500">Loading campaigns...</div>
        ) : campaigns.length === 0 ? (
          <div className="text-center py-16 border-2 border-dashed border-neutral-700 rounded-lg">
            <p className="text-neutral-400 text-lg mb-4">No adventures yet</p>
            <button
              onClick={handleNewCampaign}
              className="px-6 py-3 bg-amber-600 hover:bg-amber-500 text-white font-medium rounded-md transition-colors"
            >
              Start Your First Adventure
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {campaigns.map((campaign) => (
              <CampaignCard
                key={campaign.id}
                campaign={campaign}
                onDelete={deleteCampaign}
                onArchive={archiveCampaign}
                onDuplicate={duplicateCampaign}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
