/**
 * Contract for factions schema 1.0.0 — who they are and what each rank asks for.
 *
 * Requirements come from the FACT record's FADT subrecord, 240 bytes of two favoured
 * attributes, ten ranks of five numbers, seven faction skills and a flags word. The
 * numbers are what the game checks when it decides whether you may be promoted.
 *
 * This is also what grounds the fast travel `conjurerRank` toggle: Conjurer is rank 4
 * of the Mages Guild, and this catalog says what reaching it costs.
 */
import type { Profile } from "./catalog-types";

export type FactionRank = {
  /** 0-based position. Rank 0 is the one you hold on joining. */
  index: number;
  /** Always present: a rank with no name is not published. */
  name: string | null;
  /** Both of the faction's favoured attributes must reach this. */
  attribute1: number;
  attribute2: number;
  /** One faction skill at `primarySkill`, and two more at `favouredSkill`. */
  primarySkill: number;
  favouredSkill: number;
  /** Faction reputation required, which is not the same as personal reputation. */
  reputation: number;
};

export type Faction = {
  key: string;
  name: string | null;
  /** Up to two. The two the ranks' attribute requirements are checked against. */
  favouredAttributes: string[];
  /** Up to seven. The record reserves seven slots; unused ones are dropped. */
  skills: string[];
  /** Named ranks only. **Empty means the faction cannot be joined** — Sixth House,
   *  Skaal, Talos Cult and the Hands of Almalexia exist but admit nobody. */
  ranks: FactionRank[];
  rankCount: number;
  /** Hidden from the player's faction list. */
  hidden: boolean;
  flagsRaw: number;
  /** How this faction feels about others. Negative is hostile. */
  reactions: Array<{ faction: string; adjustment: number }>;
  /** How many placements in the world this faction owns. This is the number that made
   *  the catalog worth shipping: the policy layer decides whether taking a
   *  faction-owned item counts as theft. */
  ownedPlacements: number;
};

export type FactionCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  derivation: {
    method: string;
    factions: number; hidden: number; joinable: number;
    owningPlacements: number; reactions: number;
  };
  coverage: string;
  records: Faction[];
};

/** Factions a character can actually join. */
export function joinableFactions(catalog: FactionCatalog): Faction[] {
  return catalog.records.filter(faction => faction.ranks.length > 0);
}

/**
 * Whether a character meets a rank's stated requirements.
 *
 * Null when the faction has no such rank. This checks only the numbers the record
 * carries — the game also requires the right questgiver and, for some factions,
 * that you are not in a rival one. Nothing here knows about either.
 */
export function meetsRank(
  faction: Faction,
  rankIndex: number,
  character: {
    attributes: Record<string, number>;
    skills: Record<string, number>;
    factionReputation?: number;
  },
): boolean | null {
  const rank = faction.ranks.find(r => r.index === rankIndex);
  if (!rank) return null;
  const [first, second] = faction.favouredAttributes;
  if ((character.attributes[first] ?? 0) < rank.attribute1) return false;
  if (second !== undefined && (character.attributes[second] ?? 0) < rank.attribute2) return false;
  if ((character.factionReputation ?? 0) < rank.reputation) return false;
  const values = faction.skills.map(skill => character.skills[skill] ?? 0)
    .sort((a, b) => b - a);
  // One skill at primary, then two more at favoured.
  if ((values[0] ?? 0) < rank.primarySkill) return false;
  return (values[1] ?? 0) >= rank.favouredSkill && (values[2] ?? 0) >= rank.favouredSkill;
}
