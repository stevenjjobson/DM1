"use client";

import type { GameMessage } from "@/stores/game-store";

export function ChatMessage({ message }: { message: GameMessage }) {
  const isDM = message.role === "dm";

  return (
    <div className={`flex ${isDM ? "justify-start" : "justify-end"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isDM
            ? "bg-neutral-800 border border-neutral-700 text-neutral-100"
            : "bg-amber-900/40 border border-amber-800/50 text-amber-50"
        }`}
      >
        {isDM && (
          <div className="text-xs text-amber-500 font-semibold mb-1">Dungeon Master</div>
        )}
        <div className={`whitespace-pre-wrap leading-relaxed ${isDM ? "font-serif" : ""}`}>
          {message.text}
        </div>
      </div>
    </div>
  );
}
