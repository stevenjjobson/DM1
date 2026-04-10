import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, ApiError } from "@/lib/api";

type User = {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
};

type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

type AuthState = {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  error: string | null;

  register: (email: string, password: string, displayName: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<boolean>;
  clearError: () => void;
};

export const useAuthStore = create<AuthState>()(persist((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isLoading: false,
  error: null,

  register: async (email, password, displayName) => {
    set({ isLoading: true, error: null });
    try {
      await api<User>("/auth/register", {
        method: "POST",
        body: { email, password, display_name: displayName },
      });
      // Auto-login after registration
      await get().login(email, password);
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Registration failed", isLoading: false });
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await api<TokenPair>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      const user = await api<User>("/auth/me", { token: tokens.access_token });
      set({
        user,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        isLoading: false,
      });
    } catch (e) {
      set({ error: e instanceof ApiError ? e.detail : "Login failed", isLoading: false });
    }
  },

  logout: () => {
    set({ user: null, accessToken: null, refreshToken: null, error: null });
  },

  refresh: async () => {
    const { refreshToken } = get();
    if (!refreshToken) return false;
    try {
      const tokens = await api<TokenPair>(`/auth/refresh?refresh_token=${refreshToken}`, {
        method: "POST",
      });
      const user = await api<User>("/auth/me", { token: tokens.access_token });
      set({ user, accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
      return true;
    } catch {
      set({ user: null, accessToken: null, refreshToken: null });
      return false;
    }
  },

  clearError: () => set({ error: null }),
}), {
  name: "dm1-auth",
  partialize: (state) => ({
    user: state.user,
    accessToken: state.accessToken,
    refreshToken: state.refreshToken,
  }),
}));
