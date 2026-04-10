"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

type CostSummary = {
  month: string;
  total_usd: number;
  cap_usd: number;
  percent_used: number;
  by_service: Record<string, { cost: number; calls: number }>;
};

type LLMStatus = {
  active_provider: string;
  cost_cap_reached: boolean;
  gemini: { available: boolean };
  lm_studio: { available: boolean; model: { id: string } | null };
};

export default function SettingsPage() {
  const router = useRouter();
  const { user, accessToken, logout } = useAuthStore();
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [llmStatus, setLLMStatus] = useState<LLMStatus | null>(null);
  const [theme, setTheme] = useState("dark");
  const [capUsd, setCapUsd] = useState(10);

  useEffect(() => {
    if (!user || !accessToken) {
      router.push("/login");
      return;
    }

    api<CostSummary>("/settings/cost-summary", { token: accessToken })
      .then(setCostSummary)
      .catch(() => {});
    api<LLMStatus>("/settings/llm-status", { token: accessToken })
      .then(setLLMStatus)
      .catch(() => {});
    api<{ spending_cap_usd?: number }>("/settings/preferences", { token: accessToken })
      .then((prefs) => {
        if (prefs.spending_cap_usd) setCapUsd(prefs.spending_cap_usd);
      })
      .catch(() => {});
  }, [user, accessToken, router]);

  const saveCap = async () => {
    if (!accessToken) return;
    await api("/settings/spending-cap?cap_usd=" + capUsd, { method: "POST", token: accessToken });
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-neutral-950">
      <header className="border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
        <button onClick={() => router.push("/dashboard")} className="text-neutral-400 hover:text-white text-sm">
          &larr; Dashboard
        </button>
        <h1 className="text-xl font-bold text-amber-500">Settings</h1>
        <div className="w-20" />
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-8">
        {/* AI Providers */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">AI Providers</h2>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-neutral-300">Gemini (Cloud)</span>
              <span className={`text-sm px-2 py-0.5 rounded ${
                llmStatus?.gemini.available ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
              }`}>
                {llmStatus?.gemini.available ? "Connected" : "Unavailable"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-neutral-300">LM Studio (Local)</span>
              <span className={`text-sm px-2 py-0.5 rounded ${
                llmStatus?.lm_studio.available ? "bg-green-900/50 text-green-400" : "bg-neutral-700 text-neutral-400"
              }`}>
                {llmStatus?.lm_studio.available
                  ? `Connected: ${llmStatus.lm_studio.model?.id || "loaded"}`
                  : "Not running"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-neutral-300">Active Provider</span>
              <span className="text-sm text-amber-500 font-medium">
                {llmStatus?.active_provider === "gemini" ? "Cloud (Gemini)" : "Local (LM Studio)"}
              </span>
            </div>
          </div>
        </section>

        {/* Cost Dashboard */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">Cost Dashboard</h2>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-4">
            {costSummary ? (
              <>
                <div className="flex justify-between">
                  <span className="text-neutral-300">Month</span>
                  <span className="text-white">{costSummary.month}</span>
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-neutral-300">Spend</span>
                    <span className="text-white">${costSummary.total_usd.toFixed(4)} / ${costSummary.cap_usd}</span>
                  </div>
                  <div className="w-full bg-neutral-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        costSummary.percent_used > 80 ? "bg-red-500" :
                        costSummary.percent_used > 50 ? "bg-amber-500" : "bg-green-500"
                      }`}
                      style={{ width: `${Math.min(100, costSummary.percent_used)}%` }}
                    />
                  </div>
                  <div className="text-xs text-neutral-500 mt-1">{costSummary.percent_used}% of monthly cap</div>
                </div>
                {Object.keys(costSummary.by_service).length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs text-neutral-500 font-semibold">By Service</div>
                    {Object.entries(costSummary.by_service).map(([service, data]) => (
                      <div key={service} className="flex justify-between text-sm">
                        <span className="text-neutral-400 capitalize">{service}</span>
                        <span className="text-neutral-300">${data.cost.toFixed(4)} ({data.calls} calls)</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-neutral-500">Loading cost data...</div>
            )}

            <div className="border-t border-neutral-700 pt-3">
              <label className="block text-sm text-neutral-300 mb-1">Monthly Spending Cap ($)</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={capUsd}
                  onChange={(e) => setCapUsd(parseFloat(e.target.value) || 0)}
                  className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-1.5 text-white text-sm"
                />
                <button
                  onClick={saveCap}
                  className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Account */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">Account</h2>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
            <div className="flex justify-between">
              <span className="text-neutral-300">Email</span>
              <span className="text-white">{user.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-300">Display Name</span>
              <span className="text-white">{user.display_name}</span>
            </div>
            <div className="border-t border-neutral-700 pt-3">
              <button
                onClick={() => { logout(); router.push("/login"); }}
                className="px-4 py-2 bg-red-900/50 hover:bg-red-900 text-red-300 text-sm rounded"
              >
                Sign Out
              </button>
            </div>
          </div>
        </section>

        {/* Attribution */}
        <section className="text-center text-xs text-neutral-600 pb-8">
          DungeonMasterONE uses content from the Systems Reference Document 5.1,
          licensed under Creative Commons Attribution 4.0 International License.
        </section>
      </main>
    </div>
  );
}
