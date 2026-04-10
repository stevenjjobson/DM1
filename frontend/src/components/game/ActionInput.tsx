"use client";

import { useState, useRef, useEffect } from "react";

export function ActionInput({
  onSubmit,
  disabled,
}: {
  onSubmit: (action: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setText("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 px-4 py-3 border-t border-neutral-800">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder={disabled ? "Waiting for DM..." : "What do you do?"}
        className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-neutral-700 text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
      >
        Send
      </button>
    </form>
  );
}
