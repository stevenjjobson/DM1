"use client";

import { useState } from "react";
import { useWizardStore } from "@/stores/wizard-store";

export function StepBackstory() {
  const { backstory, appearance, updateField } = useWizardStore();
  const [generating, setGenerating] = useState(false);

  const updateAppearance = (field: string, value: string) => {
    updateField("appearance", { ...appearance, [field]: value });
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">Backstory</label>
        <textarea
          value={backstory}
          onChange={(e) => updateField("backstory", e.target.value)}
          rows={5}
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
          placeholder="Write your character's backstory, or leave blank and the AI will generate one..."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-3">Appearance</label>
        <div className="grid grid-cols-2 gap-3">
          {["hair", "eyes", "skin", "build", "height", "distinguishing"].map((field) => (
            <div key={field}>
              <label className="block text-xs text-neutral-400 mb-1 capitalize">{field}</label>
              <input
                type="text"
                value={appearance[field] || ""}
                onChange={(e) => updateAppearance(field, e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-sm text-white focus:ring-1 focus:ring-amber-500"
                placeholder={
                  field === "hair" ? "Silver, shoulder-length" :
                  field === "eyes" ? "Amber" :
                  field === "skin" ? "Light olive" :
                  field === "build" ? "Lean, athletic" :
                  field === "height" ? "5'11\"" :
                  "Lightning scar on left cheek"
                }
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
