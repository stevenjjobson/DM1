"use client";

import { useState } from "react";
import type { GameMessage } from "@/stores/game-store";

export function ChatMessage({ message }: { message: GameMessage }) {
  const [imageExpanded, setImageExpanded] = useState(false);

  // Image message — lazy-loaded scene illustration
  if (message.role === "image" && message.imageUrl) {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const fullUrl = `${apiBase}${message.imageUrl}`;

    return (
      <div className="flex justify-center mb-4">
        <div
          className="max-w-[90%] rounded-lg overflow-hidden border border-neutral-700 cursor-pointer transition-transform hover:scale-[1.02]"
          onClick={() => setImageExpanded(!imageExpanded)}
        >
          <img
            src={fullUrl}
            alt={message.text}
            className={`w-full ${imageExpanded ? "max-h-[80vh]" : "max-h-64"} object-cover transition-all`}
            loading="lazy"
          />
          {message.text && (
            <div className="px-3 py-2 bg-neutral-800 text-xs text-neutral-400 italic">
              {message.text}
            </div>
          )}
        </div>
      </div>
    );
  }

  // DM or Player message
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
