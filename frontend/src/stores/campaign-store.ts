import { create } from "zustand";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "./auth-store";

type CampaignSettings = {
  tone: string;
  length: string;
  leveling_mode: string;
  combat_emphasis: number;
  mature_themes: boolean;
  world_setting: string;
};

export type Campaign = {
  id: string;
  name: string;
  status: string;
  settings: CampaignSettings;
  current_turn: number;
  character_id: string | null;
  created_at: string;
  updated_at: string;
  last_played_at: string | null;
};

type CampaignState = {
  campaigns: Campaign[];
  isLoading: boolean;
  error: string | null;

  fetchCampaigns: () => Promise<void>;
  createCampaign: (name: string, settings?: Partial<CampaignSettings>) => Promise<Campaign | null>;
  deleteCampaign: (id: string) => Promise<void>;
  archiveCampaign: (id: string) => Promise<void>;
  duplicateCampaign: (id: string) => Promise<void>;
};

export const useCampaignStore = create<CampaignState>((set) => ({
  campaigns: [],
  isLoading: false,
  error: null,

  fetchCampaigns: async () => {
    const token = useAuthStore.getState().accessToken;
    set({ isLoading: true, error: null });
    try {
      const data = await api<{ campaigns: Campaign[]; total: number }>("/campaigns", { token });
      set({ campaigns: data.campaigns, isLoading: false });
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Failed to load campaigns", isLoading: false });
    }
  },

  createCampaign: async (name, settings) => {
    const token = useAuthStore.getState().accessToken;
    try {
      const campaign = await api<Campaign>("/campaigns", {
        method: "POST",
        body: { name, settings: settings || {} },
        token,
      });
      set((s) => ({ campaigns: [campaign, ...s.campaigns] }));
      return campaign;
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Failed to create campaign" });
      return null;
    }
  },

  deleteCampaign: async (id) => {
    const token = useAuthStore.getState().accessToken;
    try {
      await api(`/campaigns/${id}`, { method: "DELETE", token });
      set((s) => ({ campaigns: s.campaigns.filter((c) => c.id !== id) }));
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Failed to delete campaign" });
    }
  },

  archiveCampaign: async (id) => {
    const token = useAuthStore.getState().accessToken;
    try {
      await api(`/campaigns/${id}/archive`, { method: "POST", token });
      set((s) => ({ campaigns: s.campaigns.filter((c) => c.id !== id) }));
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Failed to archive campaign" });
    }
  },

  duplicateCampaign: async (id) => {
    const token = useAuthStore.getState().accessToken;
    try {
      const campaign = await api<Campaign>(`/campaigns/${id}/duplicate`, { method: "POST", token });
      set((s) => ({ campaigns: [campaign, ...s.campaigns] }));
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Failed to duplicate campaign" });
    }
  },
}));
