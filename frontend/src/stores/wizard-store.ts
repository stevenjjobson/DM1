import { create } from "zustand";

export type AbilityScores = {
  strength: number;
  dexterity: number;
  constitution: number;
  intelligence: number;
  wisdom: number;
  charisma: number;
};

export type WizardState = {
  step: number;
  campaignId: string;

  // Step 1: Tone
  campaignName: string;
  tone: string;
  combatEmphasis: number;
  worldSetting: string;

  // Step 2: Character
  characterName: string;
  raceIndex: string;
  subraceIndex: string;
  classIndex: string;
  backgroundIndex: string;
  abilities: AbilityScores;
  scoreMethod: "standard" | "pointbuy" | "roll";
  selectedSkills: string[];
  selectedCantrips: string[];
  selectedSpells: string[];

  // Step 3: Backstory
  backstory: string;
  appearance: Record<string, string>;

  // Actions
  setStep: (step: number) => void;
  setCampaignId: (id: string) => void;
  updateField: (field: string, value: unknown) => void;
  updateAbility: (ability: keyof AbilityScores, value: number) => void;
  toggleSkill: (skill: string) => void;
  toggleCantrip: (cantrip: string) => void;
  toggleSpell: (spell: string) => void;
  clearSpells: () => void;
  reset: () => void;
};

const INITIAL: Omit<WizardState, "setStep" | "setCampaignId" | "updateField" | "updateAbility" | "toggleSkill" | "toggleCantrip" | "toggleSpell" | "clearSpells" | "reset"> = {
  step: 0,
  campaignId: "",
  campaignName: "New Adventure",
  tone: "epic_fantasy",
  combatEmphasis: 0.5,
  worldSetting: "surprise_me",
  characterName: "",
  raceIndex: "",
  subraceIndex: "",
  classIndex: "",
  backgroundIndex: "acolyte",
  abilities: { strength: 10, dexterity: 10, constitution: 10, intelligence: 10, wisdom: 10, charisma: 10 },
  scoreMethod: "standard",
  selectedSkills: [],
  selectedCantrips: [],
  selectedSpells: [],
  backstory: "",
  appearance: {},
};

export const useWizardStore = create<WizardState>((set) => ({
  ...INITIAL,

  setStep: (step) => set({ step }),
  setCampaignId: (id) => set({ campaignId: id }),
  updateField: (field, value) => set({ [field]: value } as Partial<WizardState>),
  updateAbility: (ability, value) =>
    set((s) => ({ abilities: { ...s.abilities, [ability]: value } })),
  toggleSkill: (skill) =>
    set((s) => ({
      selectedSkills: s.selectedSkills.includes(skill)
        ? s.selectedSkills.filter((sk) => sk !== skill)
        : [...s.selectedSkills, skill],
    })),
  toggleCantrip: (cantrip) =>
    set((s) => ({
      selectedCantrips: s.selectedCantrips.includes(cantrip)
        ? s.selectedCantrips.filter((c) => c !== cantrip)
        : [...s.selectedCantrips, cantrip],
    })),
  toggleSpell: (spell) =>
    set((s) => ({
      selectedSpells: s.selectedSpells.includes(spell)
        ? s.selectedSpells.filter((sp) => sp !== spell)
        : [...s.selectedSpells, spell],
    })),
  clearSpells: () => set({ selectedCantrips: [], selectedSpells: [] }),
  reset: () => set(INITIAL),
}));
