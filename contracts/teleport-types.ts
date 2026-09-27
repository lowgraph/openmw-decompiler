/**
 * Contract for teleports schema 1.0.0: Propylons, dialogue transports, activators and
 * items that move the player by script. Every cell named here is a Places key.
 */
import type { Profile } from "./catalog-types";

export type TeleportKind = "propylon" | "dialogue" | "activator" | "item";

export type Teleport = {
  key: string;
  kind: TeleportKind;
  /** Cells it leaves from: where the activator stands or the speaker is. Empty for an
   *  item, which works anywhere. */
  from: string[];
  /** World points [x, y] where it is used, when known. */
  fromPos: Array<[number, number]>;
  to: string;
  toPos: [number, number];
  /** Item ids the player must carry. For an item teleport, the item itself. */
  requires: string[];
  /** Item ids that send the player elsewhere first: a Propylon with the Master Index
   *  in the pack goes to Caldera instead. */
  unless: string[];
  /** Every other test the script or dialogue makes, as text, unevaluated. */
  conditions: string[];
  /** True when this is not everyday travel; `gatedBecause` says why. The site hides
   *  these unless asked. */
  questGated: boolean;
  gatedBecause?: "authored" | "conditions" | "greeting" | "dialogue topic" | "activator";
  /** The script or dialogue line it comes from. */
  source: string;
  /** Dialogue: who to ask, and about what. */
  speaker?: string | null;
  speakerName?: string | null;
  topic?: string;
  /** Activator or item: the object to use. */
  object?: string;
  objectName?: string | null;
};

export type TeleportCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  policyVersion: string | null;
  /** Item id -> name, for every item a teleport needs or is diverted by. */
  items: Record<string, string | null>;
  derivation: {
    method: string; teleports: number; questGated: number;
    byKind: Partial<Record<TeleportKind, number>>;
    /** What was read and left out, by reason. */
    skipped: Record<string, number>;
  };
  coverage: string;
  records: Teleport[];
};

/** Whether a teleport works for a player carrying `held` item ids (lowercase). */
export function usable(teleport: Teleport, held: Set<string>, includeQuest = false): boolean {
  if (teleport.questGated && !includeQuest) return false;
  return teleport.requires.every(item => held.has(item)) && !teleport.unless.some(item => held.has(item));
}
