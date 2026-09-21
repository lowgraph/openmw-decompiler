/**
 * Contract for best-in-slot schema 1.0.0 — the best constant-effect gear per build.
 *
 * A record answers one build, one toggle setting: for every equipment slot, the items
 * already carrying a constant effect that best serve that build. Candidates are items
 * that exist in the game; enchantment capacity and custom enchanting are out of scope.
 *
 * Scores are comparable **within a slot for one build** and nowhere else. A helmet
 * scoring 19.5 for a Battlemage is not "better" than a ring scoring 9, and the same
 * helmet scores 12 for a build without Heavy Armor.
 *
 * Not to be confused with the site's *loadout*, which is a set of equipment the player
 * has assembled and saved themselves, and which the cloud vault persists. This catalog
 * is the recommendation a player builds a loadout from; the two words are kept apart
 * deliberately, and nothing here should be renamed back.
 */
import type { Profile } from "./catalog-types";

/** Engine inventory slots. Gloves and bracers share a gauntlet slot, shoes share the
 *  boots slot, and both rings draw from `ring`. */
export type GearSlot =
  | "helmet" | "cuirass" | "greaves" | "boots" | "left_pauldron" | "right_pauldron"
  | "left_hand" | "right_hand" | "shield" | "weapon"
  | "shirt" | "pants" | "skirt" | "robe" | "belt" | "amulet" | "ring";

/** How an item can be had. `unconfirmed` items are never ranked: nothing places them
 *  and no script hands them over, so there is no evidence a player can get one. */
export type SourceKind = "placed" | "quest" | "unconfirmed";

export type GearItem = {
  key: string;
  name: string;
  recordType: string;
  /** The record's own type, e.g. "cuirass", "left_bracer", "LB2H". */
  type: string;
  slot: GearSlot;
  value: number | null;
  /** False when an Argonian or Khajiit cannot equip it. Beast builds never see these. */
  beastWearable: boolean;
  armorRating?: number;
  armorClass?: "light" | "medium" | "heavy";
  weaponSkill?: string;
  damage?: number;
  effects: Array<{
    name: string;
    /** Set for parameterised effects: Fortify Skill names a skill, Fortify Attribute
     *  an attribute. Null otherwise. */
    skill: string | null;
    attribute: string | null;
    magnitude: number;
  }>;
  source: {
    kind: SourceKind;
    /** How many static routes place it in the world. */
    routes: number;
    /** Highest actor level on the easiest route — what you would face or rob. Null
     *  when nothing places it. */
    easiestLevel: number | null;
    /** Scripts that hand it to the player. Non-empty means questing gets it. */
    questGrants: string[];
  };
};

export type Pick = {
  /** Key into `items`. */
  item: string;
  score: number;
  /** Present on the first pick of a slot only: the three largest contributions. */
  reasons?: Array<[string, number]>;
  /** Drawbacks worth knowing that did not disqualify the item. Never subtracted from
   *  the score — the Boots of Blinding Speed carry Blind 100 and are still a top pick,
   *  because Resist Magicka cancels it. */
  warnings?: string[];
};

/** Everything recommended to one build, under one toggle setting. */
export type BuildPicks = {
  /** `build/0` or `build/1`, the suffix being `allowFormidableSources`. */
  key: string;
  build: string;
  category: string | null;
  /** Which premade set it came from. */
  set: "BUILDS" | "RACE_BUILDS" | "ARCE_BUILDS";
  race: string;
  beast: boolean;
  /** Two or more casting schools among major and minor skills. */
  caster: boolean;
  fighter: boolean;
  toggles: { allowFormidableSources: boolean };
  /** Best picks per slot, best first. A slot is absent when nothing qualifies — which
   *  is a real answer: a Battlemage gets no shield, because the only strong candidate
   *  drains 100 magicka. */
  slots: Partial<Record<GearSlot, Pick[]>>;
};

export type BestInSlotCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  policyVersion: string;
  builds: {
    /** The site file the builds were read from, and a digest of them. A digest that no
     *  longer matches `lib/premade-data.mjs` means this catalog is stale. */
    source: string;
    digest: string;
    applied: number;
    /** Builds that do not apply here, with why — almost always a race the profile
     *  lacks, which is how ARCE builds stay out of vanilla. */
    skipped: Array<{ build: string; reason: string }>;
  };
  toggles: {
    allowFormidableSources: { default: boolean; formidableLevel: number; note: string };
  };
  /** The scoring model, shipped so a custom build can be scored client-side with the
   *  same weights these records were built from. */
  model: unknown;
  items: Record<string, GearItem>;
  derivation: {
    method: string;
    candidates: number;
    bySource: Partial<Record<SourceKind, number>>;
    formidableOnly: number;
    records: number;
  };
  coverage: string;
  records: BuildPicks[];
};

/** The record for one build under one toggle setting. */
export function picksForBuild(
  catalog: BestInSlotCatalog,
  build: string,
  allowFormidableSources = catalog.toggles.allowFormidableSources.default,
): BuildPicks | undefined {
  return catalog.records.find(
    record => record.build === build
      && record.toggles.allowFormidableSources === allowFormidableSources);
}

/** Resolve a slot's picks to their items, best first. */
export function picksFor(
  catalog: BestInSlotCatalog,
  record: BuildPicks,
  slot: GearSlot,
): Array<{ pick: Pick; item: GearItem }> {
  return (record.slots[slot] ?? []).map(pick => ({ pick, item: catalog.items[pick.item] }));
}

/**
 * Both rings, which share one candidate pool. Returns up to two distinct items.
 */
export function ringPair(
  catalog: BestInSlotCatalog,
  record: BuildPicks,
): Array<{ pick: Pick; item: GearItem }> {
  return picksFor(catalog, record, "ring").slice(0, 2);
}
