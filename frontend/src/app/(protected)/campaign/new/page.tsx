"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useWizardStore } from "@/stores/wizard-store";
import { useCampaignStore } from "@/stores/campaign-store";
import { useGameStore } from "@/stores/game-store";
import { api } from "@/lib/api";
import { StepTone } from "@/components/wizard/StepTone";
import { StepAbilities } from "@/components/wizard/StepAbilities";
import { StepRaceClass } from "@/components/wizard/StepRaceClass";
import { StepBackstory } from "@/components/wizard/StepBackstory";
import { StepReview } from "@/components/wizard/StepReview";

const STEPS = [
  { label: "Tone & Setting", component: StepTone },
  { label: "Abilities", component: StepAbilities },
  { label: "Race & Class", component: StepRaceClass },
  { label: "Backstory", component: StepBackstory },
  { label: "Review", component: StepReview },
];

export default function NewCampaignPage() {
  const router = useRouter();
  const { user, accessToken, _hasHydrated } = useAuthStore();
  const wizard = useWizardStore();
  const { createCampaign } = useCampaignStore();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!user) router.push("/login");
    wizard.reset();
  }, [_hasHydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  const CurrentStep = STEPS[wizard.step].component;

  const canProceed = () => {
    switch (wizard.step) {
      case 0: return wizard.campaignName.length >= 2;
      case 1: return wizard.characterName.length >= 2;
      case 2: return wizard.raceIndex !== "" && wizard.classIndex !== "";
      case 3: return true; // Backstory is optional
      case 4: return true; // Review
      default: return false;
    }
  };

  const handleNext = () => {
    if (wizard.step < STEPS.length - 1) {
      wizard.setStep(wizard.step + 1);
    }
  };

  const handleBack = () => {
    if (wizard.step > 0) {
      wizard.setStep(wizard.step - 1);
    }
  };

  const handleCreate = async () => {
    if (!accessToken) return;
    setIsCreating(true);
    setError("");

    try {
      // 1. Create the campaign in MongoDB
      const campaign = await createCampaign(wizard.campaignName, {
        tone: wizard.tone,
        combat_emphasis: wizard.combatEmphasis,
        world_setting: wizard.worldSetting,
      });

      if (!campaign) {
        setError("Failed to create campaign");
        setIsCreating(false);
        return;
      }

      // 2. Create the character + generate the world
      const result = await api<{
        character_uuid: string;
        opening_narration: string;
        locations_created: number;
        npcs_created: number;
      }>("/character/create", {
        method: "POST",
        token: accessToken,
        body: {
          campaign_id: campaign.id,
          name: wizard.characterName || "The Adventurer",
          race_index: wizard.raceIndex || "human",
          subrace_index: wizard.subraceIndex || null,
          class_index: wizard.classIndex || "fighter",
          background_index: wizard.backgroundIndex,
          abilities: wizard.abilities,
          selected_skills: wizard.selectedSkills,
          selected_spells: [...wizard.selectedCantrips, ...wizard.selectedSpells],
          backstory: wizard.backstory,
          appearance: wizard.appearance,
        },
      });

      // 3. Pre-populate game store with opening narration so game page doesn't re-init
      const gameStore = useGameStore.getState();
      gameStore.clearMessages();
      gameStore.addDMMessage(result.opening_narration);
      gameStore.setSuggestions(["Look around", "Talk to someone nearby", "Explore the area"]);

      // 4. Navigate to the game
      router.push(`/campaign/${campaign.id}/game`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setIsCreating(false);
    }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-neutral-950">
      <header className="border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
        <button onClick={() => router.push("/dashboard")} className="text-neutral-400 hover:text-white text-sm">
          &larr; Dashboard
        </button>
        <h1 className="text-xl font-bold text-amber-500">Create Adventure</h1>
        <div className="w-20" />
      </header>

      {/* Step indicator */}
      <div className="max-w-2xl mx-auto px-6 py-4">
        <div className="flex gap-1 mb-2">
          {STEPS.map((s, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= wizard.step ? "bg-amber-500" : "bg-neutral-700"
              }`}
            />
          ))}
        </div>
        <div className="text-sm text-neutral-400">
          Step {wizard.step + 1} of {STEPS.length}: {STEPS[wizard.step].label}
        </div>
      </div>

      {/* Step content */}
      <main className="max-w-2xl mx-auto px-6 py-4">
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        <CurrentStep />

        {/* Navigation */}
        <div className="flex justify-between mt-8 pb-8">
          <button
            onClick={handleBack}
            disabled={wizard.step === 0}
            className="px-4 py-2 text-neutral-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          >
            &larr; Back
          </button>

          {wizard.step < STEPS.length - 1 ? (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="px-6 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-neutral-700 text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
            >
              Next &rarr;
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={isCreating || !canProceed()}
              className="px-6 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-neutral-700 text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
            >
              {isCreating ? "Generating World..." : "Begin Adventure"}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
