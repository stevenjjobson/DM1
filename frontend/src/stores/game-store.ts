import { create } from "zustand";

export type GameMessage = {
  id: string;
  role: "dm" | "player";
  text: string;
  timestamp: number;
};

type GameState = {
  messages: GameMessage[];
  suggestions: string[];
  isLoading: boolean;
  turnNumber: number;
  wsConnected: boolean;

  addDMMessage: (text: string) => void;
  addPlayerMessage: (text: string) => void;
  setSuggestions: (actions: string[]) => void;
  setLoading: (loading: boolean) => void;
  setTurnNumber: (turn: number) => void;
  setWsConnected: (connected: boolean) => void;
  clearMessages: () => void;
};

export const useGameStore = create<GameState>((set) => ({
  messages: [],
  suggestions: [],
  isLoading: false,
  turnNumber: 0,
  wsConnected: false,

  addDMMessage: (text) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "dm", text, timestamp: Date.now() },
      ],
    })),

  addPlayerMessage: (text) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "player", text, timestamp: Date.now() },
      ],
    })),

  setSuggestions: (actions) => set({ suggestions: actions }),
  setLoading: (loading) => set({ isLoading: loading }),
  setTurnNumber: (turn) => set({ turnNumber: turn }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
  clearMessages: () => set({ messages: [], suggestions: [], turnNumber: 0 }),
}));
