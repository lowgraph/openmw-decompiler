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
export type RowToggles = { theft: boolean; endgame: boolean; nearStart: boolean };

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
   *  weapons, enchantment capacity on clothing, which has no other purpose. */
  strength: number;
  /** Enchantment capacity, which decides what a constant effect can cost. */
  enchantment: number;
  /** Undamaged catalog value, for comparison against the route's own price. */
  baseValue: number;
  endgame: boolean;
  acquisition: "direct" | "take" | "purchase" | "theft" | "pickpocket";
  /** Gold for a purchase route, condition-scaled; null when nothing is paid. */
  price: number | null;
  /** This copy's worth after condition. */
  value: number | null;
  cellKey: string;
  nearStart: boolean;
  /** Condition 0: free and repairable, no armour rating until repaired. */
  needsRepair: boolean;
  condition: { raw: number; maximum: number; ratio: number; worn: boolean } | null;
  holder: string | null;
  theftRequired: boolean;
  /** The item's search was capped, so a better source may exist. */
  evidenceTruncated: boolean;
};

export type GearRow = {
  /** Stable, unique:
   *  `category/slot-or-skill/armorClass/theft endgame nearStart/objective`. */
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
  const t = `${+row.toggles.theft}${+row.toggles.endgame}${+row.toggles.nearStart}`;
  return `${row.category}/${slot}/${row.armorClass ?? "-"}/${t}`;
}

export type { Toggles };
