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

export type Pick = {
  key: string;
  name: string;
  /** Armour rating, best weapon damage, or enchantment capacity. Re-rank on this. */
  strength: number;
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
  category: RowCategory;
  /** Set for armor and clothing rows; null for shields and weapons. */
  slot: ArmorSlot | ClothingSlot | null;
  /** Set for armor rows only. */
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
  /** A strictly stronger piece from farther away; null unless it beats a near primary. */
  alternative: Pick | null;
};

export type GearRows = {
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

/** Rows are keyed by category, slot/skill and toggle set; this is the index key. */
export function rowKey(row: GearRow): string {
  const slot = row.slot ?? (row.skill ? `${row.skill}-${row.hands}h` : "-");
  const t = `${+row.toggles.theft}${+row.toggles.endgame}${+row.toggles.nearStart}`;
  return `${row.category}/${slot}/${row.armorClass ?? "-"}/${t}`;
}

export type { Toggles };
