/**
 * Contract for gear-row schema 1.0.0 — one row per equipment slot per toggle set.
 *
 * Rows are derived from policy verdicts, not authored. Every toggle combination is
 * emitted even when empty, so a lookup is an index rather than a search.
 */
import type { Toggles } from "./policy-types";

export type RowCategory = "armor" | "shield" | "weapon" | "clothing";
export type ArmorClass = "light" | "medium" | "heavy";
export type ArmorSlot =
  | "helmet" | "cuirass" | "greaves" | "boots"
  | "left_pauldron" | "right_pauldron"
  | "left_gauntlet" | "right_gauntlet"
  | "left_bracer" | "right_bracer";
export type ClothingSlot =
  | "shirt" | "pants" | "shoes" | "belt" | "robe" | "skirt"
  | "ring" | "amulet" | "left_glove" | "right_glove";
export type WeaponSkill = "short_blade" | "long_blade" | "blunt" | "axe" | "spear" | "marksman";

/** The toggle set a row was built for; the same three the policy layer takes. */
export type PolicyToggles = { theft: boolean; endgame: boolean; nearStart: boolean };

/** An ambush row names its own toggle instead: gear worn by an actor a script sends at
 *  the player, shown only when that toggle is on, whatever the policy toggles. Additive
 *  to schema 1.0.0; a site that only matches the three policy toggles never selects it. */
export type AmbushToggles = { darkBrotherhood: true };

export type RowToggles = PolicyToggles | AmbushToggles;

/** What a row optimises for. Every slot is answered once per objective, and they
 *  disagree on 94 of vanilla's 352 filled rows. */
export type Objective = "power" | "enchantment";

/** Races with the Beast flag: Argonian and Khajiit. */
export type BeastRace = "argonian" | "khajiit";

export type Pick = {
  /** False when an Argonian or Khajiit cannot equip this at all. The engine refuses
   *  any item whose body parts touch the head or a foot, so a closed helm and every
   *  pair of boots are out, while an open helm that dresses the hair is fine. */
  beastWearable: boolean;
  key: string;
  name: string;
  /** What the piece is for: armour rating on armour and shields, best damage on
   *  weapons, enchantment capacity on clothing, which has no other purpose. For an item
   *  whose Cast When Used enchantment conjures Bound gear for its own row, the conjured
   *  piece's strength when it is higher: a Devil Tanto ranks on its Bound Dagger. */
  strength: number;
  /** Present only with `summons`: the item's own strength, before what it conjures. */
  baseStrength?: number;
  /** Present only when the item's Cast When Used enchantment conjures Bound gear. */
  summons?: Summon[];
  /** Enchantment capacity, which decides what a constant effect can cost. */
  enchantment: number;
  /** Undamaged catalog value, for comparison against the route's own price. */
  baseValue: number;
  endgame: boolean;
  /** `ambush`: taken from the body of an actor a script sends at the player. */
  acquisition: "direct" | "take" | "purchase" | "theft" | "pickpocket" | "ambush";
  /** Gold for a purchase route, condition-scaled; null when nothing is paid. */
  price: number | null;
  /** This copy's worth after condition. */
  value: number | null;
  /** Null on an ambush pick, which has no fixed place. */
  cellKey: string | null;
  /** What to call `cellKey` on screen: the cell's name, or for an unnamed exterior its
   *  region and grid ("Grazelands Region (10, 10)"). Additive; absent in older rows. */
  place?: string | null;
  /** Who you buy it from, on a purchase: the merchant, not the crate they keep stock
   *  in. Null for anything not bought. Additive; absent in older rows. */
  seller?: string | null;
  nearStart: boolean;
  /** Condition 0: free and repairable, no armour rating until repaired. */
  needsRepair: boolean;
  condition: { raw: number; maximum: number; ratio: number; worn: boolean } | null;
  holder: string | null;
  theftRequired: boolean;
  /** The item's search was capped, so a better source may exist. */
  evidenceTruncated: boolean;
  /** On an ambush pick: how the actor comes and what to do. */
  note?: string;
};

/** One Bound piece an item conjures on use. Additive to schema 1.0.0. */
export type Summon = {
  key: string;
  name: string;
  /** WEAP or ARMO: whether `strength` is damage or armour rating. */
  recordType: "WEAP" | "ARMO";
  /** The conjured piece's own strength: damage or armour rating. */
  strength: number;
  /** How long one cast lasts. */
  seconds: number | null;
  /** Whole casts from a full charge at the listed cost; the Enchant skill lowers the cost. */
  uses: number | null;
  /** True when it fills the item's own row (a weapon of the same skill, armour for the
   *  same slot) and so lifted `strength`; a helm that conjures gloves is false. */
  sameRow: boolean;
};

export type GearRow = {
  /** Stable, unique:
   *  `category/slot-or-skill/armorClass/theft endgame nearStart/objective`, or the
   *  ambush toggle's name in place of the three flags. */
  key: string;
  category: RowCategory;
  /** Set for armor and clothing rows; null for shields and weapons. */
  slot: ArmorSlot | ClothingSlot | null;
  /** Set for armor and shield rows; null for weapons and clothing. */
  armorClass: ArmorClass | null;
  /** Set for weapon rows only. */
  skill: WeaponSkill | null;
  hands: 1 | 2 | null;
  toggles: RowToggles;
  /** Eligible candidates considered for this row, and how many were near a start. */
  eligible: number;
  nearStart: number;
  /** Closest source first, even when it costs more. Null when the row is empty. */
  primary: Pick | null;
  /** Which question this row answers. `power` ranks on `strength`, `enchantment` on
   *  `enchantment`, and every pick in the row — primary, alternative and beastPrimary
   *  alike — was chosen on it. */
  objective: Objective;
  /** A strictly stronger piece from farther away; null unless it beats a near primary.
   *  "Stronger" means stronger *on this row's objective*. */
  alternative: Pick | null;
  /** How many of `eligible` an Argonian or Khajiit could actually equip. */
  beastEligible: number;
  /** The same row answered for a beast race, chosen from the same candidates by the
   *  same near-first rule. **Null means nothing in this slot fits them** — which is
   *  every boots row and almost every shoes row — not that the row is empty. When the
   *  primary is already wearable this repeats it, so a caller never has to decide. */
  beastPrimary: Pick | null;
};

/** The standalone artifact. In the app bundle these rows ship as the `GearRows` catalog,
 *  where `policy`, `limits`, `categories` and `coverage` travel as payload fields. */
export type GearRows = {
  /** The objectives this release was built for, and what each ranks on. */
  objectives?: Array<{ key: Objective; ranksOn: string; note: string | null }>;
  schemaVersion: "1.0.0";
  profile: "vanilla" | "tr" | "tr_arce";
  snapshotId: string;
  policy: { version: string; schemaVersion: string; name: string | null };
  limits: import("./policy-types").Limits;
  categories: RowCategory[];
  /** The ambushes this profile's scripts still send, with their rows' toggle. */
  ambushes?: Array<{ toggle: keyof AmbushToggles; label: string; actor: string; script: string; note: string }>;
  coverage: string;
  builtAtUnix: number;
  rows: GearRow[];
};

/**
 * Rows carry their own `key`; this is the derivation the builder uses, kept here so
 * a caller can compute the key of a row it wants before loading anything.
 */
export function rowKey(row: Pick<GearRow, "category" | "slot" | "armorClass" | "skill" | "hands" | "toggles">): string {
  const slot = row.slot ?? (row.skill ? `${row.skill}-${row.hands}h` : "-");
  const t = "theft" in row.toggles
    ? `${+row.toggles.theft}${+row.toggles.endgame}${+row.toggles.nearStart}`
    : Object.keys(row.toggles).sort().join("-");
  return `${row.category}/${slot}/${row.armorClass ?? "-"}/${t}`;
}

export type { Toggles };
