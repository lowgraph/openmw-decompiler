/**
 * Contract for effect-rules schema 1.0.0 — the engine behaviour the plugin files omit.
 *
 * Morrowind's data carries only two of a magic effect's flags: whether the Construction
 * Set permits spellmaking and enchanting. Targeting, whether an effect has a magnitude,
 * and whether it has a duration are engine-side. They are inferred here from how the
 * game's own content uses each effect, and every inference ships with its evidence.
 *
 * `noMagnitude` and `noDuration` are null when the content never exercised the effect
 * enough to decide. Null means unknown, not false — a calculator should say so rather
 * than price the effect as if the field were in use.
 */
import type { Profile } from "./catalog-types";

export type Range = "self" | "touch" | "target";

export type EffectEvidence = {
  /** Total observations, which double-counts content a profile inherits from another. */
  uses: number;
  /** Observations in the best-covered profile; this is what the threshold is applied to. */
  bestProfileUses: number;
  byProfile: Record<string, number>;
  distinctMagnitudes: number;
  distinctDurations: number;
  sufficient: boolean;
};

/** Where a rule's behavioural fields came from. */
export type RuleSource = "engine" | "derived";

export type EffectRule = {
  /** The effect id as a decimal string, matching MagicEffects' own key. */
  key: string;
  effectId: number;
  name: string;
  // --- read from the plugin files ---
  school: string;
  baseCost: number;
  allowSpellmaking: boolean;
  allowEnchanting: boolean;
  // --- inferred from content, with the evidence below ---
  targetsSkill: boolean;
  targetsAttribute: boolean;
  /** null when the content gave too little evidence to decide. */
  noMagnitude: boolean | null;
  noDuration: boolean | null;
  /** Ranges the content is seen using. With source "derived" an absent range is
   *  unproven rather than forbidden; prefer castSelf/castTouch/castTarget when present. */
  rangesObserved: Range[];
  evidence: EffectEvidence;

  /** "engine" when an OpenMW dump supplied the behaviour, "derived" when inferred. */
  source: RuleSource;
  /** Engine-only fields. All null when source is "derived". */
  harmful: boolean | null;
  castSelf: boolean | null;
  castTouch: boolean | null;
  castTarget: boolean | null;
  appliedOnce: boolean | null;
  casterLinked: boolean | null;
  nonRecastable: boolean | null;
  unreflectable: boolean | null;
  /** What the content-only inference said, kept so the method can be checked. */
  inferred: {
    targetsSkill: boolean; targetsAttribute: boolean;
    noMagnitude: boolean | null; noDuration: boolean | null;
  } | null;
  /** How each inference fared against the engine. Null when there was no dump. */
  agreement: Record<"targetsSkill" | "targetsAttribute" | "noMagnitude" | "noDuration",
                    "confirmed" | "corrected" | "decided"> | null;
  /** Ranges the content uses that the engine says are forbidden. Should be empty. */
  rangesUnexplained: Range[];
};

/** Engine literals, not game settings and not derivable from content. */
export type CostFormula = {
  source: "authored";
  note: string;
  magnitudeAverage: number;
  baseCostMultiplier: number;
  areaMultiplier: number;
  targetRangeMultiplier: number;
  /** A noMagnitude effect is priced at this magnitude, a noDuration one at this duration. */
  unusedMagnitude: number;
  unusedDuration: number;
  /** Game settings the caller still needs, by name; their values are in GameSettings. */
  gameSettings: string[];
};

export type EffectRules = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  derivation: {
    method: string;
    profilesPooled: string[];
    sources: string[];
    minimumUses: number;
    effects: number;
    decided: number;
    unknown: number;
  };
  costFormula: CostFormula;
  verification: {
    source: "engine" | "content only";
    effectsFromEngine: number;
    confirmed: number;
    corrected: number;
    decided: number;
    /** Effect names whose observed ranges contradict the engine. Should be empty. */
    rangesUnexplained: string[];
  };
  coverage: string;
  builtAtUnix: number;
  records: EffectRule[];
};

/**
 * The spell cost of one effect, in the engine's own terms. Returns null when a rule
 * the formula depends on is still unknown, so a caller can refuse rather than mislead.
 */
export function effectCost(
  rule: EffectRule,
  formula: CostFormula,
  effect: { magnitude: { min: number; max: number }; durationSeconds: number; areaFeet: number; range: Range },
): number | null {
  if (rule.noMagnitude === null || rule.noDuration === null) return null;
  const magnitude = rule.noMagnitude
    ? formula.unusedMagnitude * 2
    : effect.magnitude.min + effect.magnitude.max;
  const duration = rule.noDuration ? formula.unusedDuration : effect.durationSeconds;
  let cost = formula.magnitudeAverage * magnitude;
  cost *= formula.baseCostMultiplier * rule.baseCost;
  cost *= 1 + duration;
  cost += formula.areaMultiplier * Math.max(1, effect.areaFeet) * rule.baseCost;
  return effect.range === "target" ? cost * formula.targetRangeMultiplier : cost;
}
