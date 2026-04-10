"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useGameStore } from "@/stores/game-store";
import { api, ApiError } from "@/lib/api";
import { GameWebSocket } from "@/lib/ws";
import { ChatMessage } from "@/components/game/ChatMessage";
import { SuggestedActions } from "@/components/game/SuggestedActions";
import { ActionInput } from "@/components/game/ActionInput";
import { BottomNav } from "@/components/game/BottomNav";
import { OverlayPanel } from "@/components/game/OverlayPanel";

type StartResponse = {
  opening_narration: string;
  starting_location: string;
  locations_created: number;
  npcs_created: number;
  quests_created: number;
  character_uuid: string;
};

type TurnResponse = {
  turn: number;
  narrative: string;
  suggested_actions: string[];
  action_type: string;
};

export default function GamePage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;
  const { user, accessToken, _hasHydrated } = useAuthStore();
  const {
    messages,
    suggestions,
    isLoading,
    wsConnected,
    addDMMessage,
    addPlayerMessage,
    addImage,
    startDMStream,
    appendToLastDM,
    setSuggestions,
    setLoading,
    setTurnNumber,
    setWsConnected,
    clearMessages,
  } = useGameStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<GameWebSocket | null>(null);
  const [campaignName, setCampaignName] = useState("Adventure");
  const [initialized, setInitialized] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);

  const togglePanel = (panel: string) => {
    setActivePanel(activePanel === panel ? null : panel);
  };

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initialize campaign on mount
  useEffect(() => {
    if (!_hasHydrated) return; // Wait for localStorage to load
    if (!user || !accessToken) {
      router.push("/login");
      return;
    }

    // Check if messages were pre-populated by the wizard (opening narration)
    const hasPrePopulated = useGameStore.getState().messages.length > 0;

    const init = async () => {
      try {
        // Fetch campaign details
        const campaign = await api<{
          id: string;
          name: string;
          status: string;
          current_turn: number;
        }>(`/campaigns/${campaignId}`, { token: accessToken });

        setCampaignName(campaign.name);
        setTurnNumber(campaign.current_turn);

        if (campaign.status === "creating") {
          // Need to start the campaign (genesis) — shouldn't normally happen
          // since the wizard calls /character/create which runs genesis
          clearMessages();
          setLoading(true);
          addDMMessage("*The world stirs to life...*\n\nGenerating your adventure. This may take a moment.");

          const result = await api<StartResponse>(
            `/gameplay/${campaignId}/start`,
            { method: "POST", token: accessToken }
          );

          clearMessages();
          addDMMessage(result.opening_narration);
          setSuggestions(["Look around", "Talk to someone nearby", "Explore the area"]);
          setInitialized(true);
          setLoading(false);
        } else if (campaign.status === "active") {
          if (hasPrePopulated) {
            // Wizard pre-populated opening narration — use it directly
            setInitialized(true);
          } else if (campaign.current_turn === 0) {
            // Brand new adventure with no opening narration — ask DM to set the scene
            clearMessages();
            setLoading(true);
            try {
              const result = await api<TurnResponse>(
                `/gameplay/${campaignId}/turn?action=${encodeURIComponent("Describe where I am and set the scene for my adventure.")}`,
                { method: "POST", token: accessToken }
              );
              addDMMessage(result.narrative);
              setSuggestions(result.suggested_actions);
              setTurnNumber(result.turn);
            } catch {
              addDMMessage("*The world takes shape around you...*\n\nYour adventure awaits. What would you like to do?");
              setSuggestions(["Look around", "Talk to someone nearby", "Explore the area"]);
            }
            setLoading(false);
            setInitialized(true);
          } else {
            // Returning to existing adventure — get AI recap
            clearMessages();
            setLoading(true);
            try {
              const recap = await api<{ recap: string; turn: number }>(
                `/gameplay/${campaignId}/recap`,
                { token: accessToken }
              );
              addDMMessage(`*When we last left off...*\n\n${recap.recap}`);
              setTurnNumber(recap.turn);
            } catch {
              addDMMessage("*You return to your adventure...*\n\nWelcome back. What would you like to do?");
            }
            setSuggestions(["Look around", "Check my inventory", "Continue where I left off"]);
            setLoading(false);
            setInitialized(true);
          }
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          router.push("/dashboard");
        } else {
          addDMMessage("Something went wrong connecting to the adventure. Please try again.");
        }
        setLoading(false);
      }
    };

    init();

    return () => {
      wsRef.current?.disconnect();
      wsRef.current = null;
    };
  }, [campaignId, user, accessToken, _hasHydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  // Connect WebSocket after initialization
  useEffect(() => {
    if (!initialized || !accessToken) return;

    const ws = new GameWebSocket(campaignId, accessToken, {
      onNarrativeChunk: (text) => appendToLastDM(text),
      onNarrativeEnd: () => setLoading(false),
      onSuggestions: (actions) => setSuggestions(actions),
      onTurnComplete: (turn) => setTurnNumber(turn),
      onImage: (url, caption) => addImage(url, caption),
      onError: (msg) => {
        addDMMessage(`*Something went wrong: ${msg}*`);
        setLoading(false);
      },
      onConnectionChange: (connected) => setWsConnected(connected),
    });

    wsRef.current = ws;
    ws.connect();

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [initialized, campaignId, accessToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleActionWs = (action: string) => {
    addPlayerMessage(action);
    setSuggestions([]);
    setLoading(true);
    startDMStream();
    wsRef.current!.sendAction(action);
  };

  const handleActionRest = async (action: string) => {
    addPlayerMessage(action);
    setSuggestions([]);
    setLoading(true);

    try {
      const result = await api<TurnResponse>(
        `/gameplay/${campaignId}/turn?action=${encodeURIComponent(action)}`,
        { method: "POST", token: accessToken }
      );

      addDMMessage(result.narrative);
      setSuggestions(result.suggested_actions);
      setTurnNumber(result.turn);
    } catch {
      addDMMessage(
        "*The threads of fate twist unexpectedly...*\n\nSomething went wrong. Please try your action again."
      );
      setSuggestions(["Try again", "Look around", "Do something else"]);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = (action: string) => {
    if (!accessToken || isLoading) return;
    if (wsConnected && wsRef.current) {
      handleActionWs(action);
    } else {
      handleActionRest(action);
    }
  };

  if (!_hasHydrated || !user) return null;

  return (
    <div className="flex flex-col h-screen bg-neutral-950">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 shrink-0">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-neutral-400 hover:text-white text-sm"
        >
          &larr; Back
        </button>
        <h1 className="text-amber-500 font-semibold">{campaignName}</h1>
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-500" : "bg-neutral-600"}`} />
          {useGameStore.getState().turnNumber > 0 &&
            `Turn ${useGameStore.getState().turnNumber}`}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3">
              <div className="text-xs text-amber-500 font-semibold mb-1">Dungeon Master</div>
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Actions */}
      <SuggestedActions
        actions={suggestions}
        onSelect={handleAction}
        disabled={isLoading}
      />

      {/* Input */}
      <ActionInput onSubmit={handleAction} disabled={isLoading} />

      {/* Bottom Nav */}
      <BottomNav activePanel={activePanel} onToggle={togglePanel} />

      {/* Overlay Panel */}
      {activePanel && (
        <OverlayPanel
          panel={activePanel}
          campaignId={campaignId}
          onClose={() => setActivePanel(null)}
        />
      )}
    </div>
  );
}
