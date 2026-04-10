"use client";

type NavItem = {
  id: string;
  label: string;
  icon: string;
};

const NAV_ITEMS: NavItem[] = [
  { id: "character", label: "Character", icon: "🎭" },
  { id: "inventory", label: "Inventory", icon: "📦" },
  { id: "spellbook", label: "Spells", icon: "📖" },
  { id: "quests", label: "Quests", icon: "🗺️" },
];

export function BottomNav({
  activePanel,
  onToggle,
}: {
  activePanel: string | null;
  onToggle: (panel: string) => void;
}) {
  return (
    <div className="flex justify-around border-t border-neutral-800 bg-neutral-900 py-1">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          onClick={() => onToggle(item.id)}
          className={`flex flex-col items-center py-1 px-3 text-xs transition-colors ${
            activePanel === item.id
              ? "text-amber-500"
              : "text-neutral-500 hover:text-neutral-300"
          }`}
        >
          <span className="text-lg">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
}
