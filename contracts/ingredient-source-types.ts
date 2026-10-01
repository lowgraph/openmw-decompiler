/**
 * Contract for ingredient sources schema 1.0.0 (build_ingredient_sources.py): where each
 * ingredient comes from, per profile, for CALC-4's effect finder. Every `cellKey` and
 * every cell in `cells` is a Places key; regions are Places region keys. Absent fields are
 * left out rather than null, as in Places: an ingredient with no source is just
 * `{ key, name }`.
 *
 * Theft is never a source (owner, 30 September): anything owned by someone else, and
 * anything only an NPC carries. Random loot, scripts and quest rewards are not sources.
 */
import type { Profile } from "./catalog-types";

/** [key, count], most first: where the placements of one source fall. */
export type Tally = [string, number];

export type Spread = {
  /** How many placements: plants, deposits, loose pickups. */
  count: number;
  /** Exterior placements by region key; the eight largest. */
  regions?: Tally[];
  /** Placements in or next to a starting town (policy nearStart), by the town's display
   *  name, e.g. "Seyda Neen", "Vivec". */
  near?: Tally[];
  /** Interior placements by cell key; the six largest (caves, mines). */
  cells?: Tally[];
};

/** What one plant, creature or container gives: `quantity` items, each with `chance`
 *  for a level 1 character; `fromLevel` when the list gives nothing before that level. */
export type Draw = {
  chance: number;
  quantity: number;
  fromLevel?: number;
};

export type IngredientShop = {
  /** The merchant's actor key; Merchants has their services and barter stats. */
  seller: string;
  name: string | null;
  /** Where they trade. */
  cellKey: string;
  /** Stock per visit: their own inventory plus crates they own where they trade. */
  quantity: number;
  /** True when the stock comes back (negative inventory count). */
  restocks: boolean;
  /** The starting town the shop is in or next to. */
  near?: string;
};

export type IngredientPlant = Draw & Spread & {
  /** The plant's name in game, e.g. "Marshmerrow". */
  name: string;
  /** Container ids sharing that name and draw. */
  containers: string[];
  /** Always true: a plant is an organic container that grows back. */
  regrows: true;
};

export type IngredientCreature = Draw & Omit<Spread, "count"> & {
  creature: string;
  name: string;
  level: number | null;
  /** Placed directly in the world. */
  placed: number;
  /** Levelled spawn points that can produce it; which creature appears depends on level. */
  spawnPoints: number;
};

export type IngredientFind = Draw & Spread & {
  /** What holds it, e.g. "Raw Ebony" (a deposit) or "Crate"; absent when lying loose. */
  name?: string;
  loose?: true;
  /** The container fills up again. Otherwise each place gives it once. */
  refills?: true;
  /** How many of the places are locked. */
  locked?: number;
};

export type IngredientSource = {
  /** The ingredient's key, as in the Ingredients catalog. */
  key: string;
  name: string;
  /** Nearest the starting towns first, then restocking, then most stock. */
  shops?: IngredientShop[];
  /** Set when there are more shops than listed. */
  shopCount?: number;
  plants?: IngredientPlant[];
  creatures?: IngredientCreature[];
  creatureCount?: number;
  finds?: IngredientFind[];
  /** The evidence query hit a limit; the lists may be incomplete. */
  truncated?: string[];
};

export type IngredientSourceCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  policyVersion: string;
  derivation: {
    ingredients: number;
    withShop: number;
    withPlant: number;
    withCreature: number;
    withFind: number;
    withoutSource: number;
    truncated: number;
    referenceLevel: number;
    transcribedFrom: string;
    /** Hash of everything this profile's build read; equal hashes, equal records. Absent
     *  on a partial run. */
    inputsFingerprint?: string;
    /** The profile whose records were reused because the fingerprints matched. */
    reusedFrom?: Profile["id"];
    /** Placements not counted, by reason: theft, carried, random, unreachableCell. */
    leftOut: Record<string, number>;
  };
  coverage: string;
  records: IngredientSource[];
};
