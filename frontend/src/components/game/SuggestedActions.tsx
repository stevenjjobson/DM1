"use client";

export function SuggestedActions({
  actions,
  onSelect,
  disabled,
}: {
  actions: string[];
  onSelect: (action: string) => void;
  disabled: boolean;
}) {
  if (actions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2">
      {actions.map((action, i) => (
        <button
          key={i}
          onClick={() => onSelect(action)}
          disabled={disabled}
          className="px-3 py-1.5 text-sm bg-neutral-800 border border-neutral-600 text-neutral-200 rounded-full hover:bg-neutral-700 hover:border-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {action}
        </button>
      ))}
    </div>
  );
}
