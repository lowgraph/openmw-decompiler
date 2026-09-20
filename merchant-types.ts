/**
 * Contract for merchants schema 1.0.0 — the merchant side of haggling.
 *
 * A merchant's offer is not a number in any record. The engine computes it when you
 * open the barter window, from both sides' Mercantile, Luck, Personality, fatigue and
 * the merchant's disposition toward you. This catalog publishes the merchant's half;
 * the player's half comes from the character being planned.
 *
 * `barterOffer` below is transcribed from OpenMW's own getBarterOffer, not reconstructed
 * from a wiki. Two cases never reach the arithmetic: a creature merchant returns the
 * base price unchanged, and a zero base price stays zero.
 *
 * Every trader is priceable. One in five stores no stats at all — the engine derives
 * them from class and level at load — and those are derived here the same way, marked
 * `statsSource: "derived"`. See MERCHANTS.md for how that was checked.
 */
import type { Profile } from "./catalog-types";

export type ServiceFlag = { bit: number; code: string; kind: "trade" | "service" };

export type Merchant = {
  key: string;
  name: string;
  /** "NPC_" or "CREA". A creature does not haggle. */
  recordType: string;
  /** Cells this merchant stands in. Normally one. */
  cells: string[];
  /** True when any service flag is a trade flag — they buy or sell goods. */
  trades: boolean;
  /** Decode against the catalog's `serviceFlags`. */
  servicesRaw: number;
  /** Barter gold. Restocks on a timer; see fBarterGoldResetDelay. */
  gold: number | null;
  /** Base disposition before anything the player does to it. */
  disposition: number | null;
  level: number | null;
  fatigue: number | null;

  /** Read from the record, or worked out by rerunning the engine's own autocalc when
   *  the record stores nothing. Null only when neither was possible. **Null never means
   *  zero** — treating it as 0 makes a merchant look maximally generous. */
  mercantile: number | null;
  personality: number | null;
  luck: number | null;
  /** Which of the two produced the three values above. Null when neither could. */
  statsSource: "record" | "derived" | null;

  /** True when the record itself stores no stats. Independent of `statsSource`: an
   *  auto-calculated merchant usually still has derived values. */
  autocalc: boolean;
  /** False for creatures, which the engine exempts from the formula entirely. */
  haggles: boolean;
  /** True when a price can be computed exactly: either it does not haggle, or its
   *  stats are all present. False means `barterOffer` would be guessing. */
  priceable: boolean;

  /** The inputs the derivation used, kept so its answer can be checked. */
  class: string | null;
  race: string | null;
  female: boolean;
};

/** Engine literals, not game settings, and not visible in any record. */
export type BarterFormula = {
  source: "authored";
  note: string;
  mercantileCap: number;
  luckWeight: number; luckCap: number;
  personalityWeight: number; personalityCap: number;
  dispositionBaseline: number;
  buyBase: number;
  sellBase: number;
  termWeight: number;
  percentScale: number;
  minimumPrice: number;
  creaturesDoNotHaggle: true;
  zeroBasePriceStaysZero: true;
  /** Values live in the GameSettings catalog rather than being duplicated here. */
  gameSettings: string[];
};

export type MerchantCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  barterFormula: BarterFormula;
  serviceFlags: ServiceFlag[];
  derivation: {
    method: string;
    providers: number; traders: number; priceable: number;
    statsFromRecord: number; statsDerived: number; statsUnknown: number;
    autocalc: number; creatures: number; withoutGold: number;
  };
  coverage: string;
  records: Merchant[];
};

export type Haggler = {
  mercantile: number;
  luck: number;
  personality: number;
  /** Current fatigue over maximum, 0..1. Full fatigue is the common case. */
  fatigueRatio?: number;
};

/** fFatigueBase - fFatigueMult * (1 - normalised fatigue). */
export function fatigueTerm(
  ratio: number | undefined,
  settings: { fFatigueBase: number; fFatigueMult: number },
): number {
  const normalised = Math.max(0, Math.min(1, ratio ?? 1));
  return settings.fFatigueBase - settings.fFatigueMult * (1 - normalised);
}

/**
 * What the merchant will charge (buying) or pay (selling), in gold.
 *
 * Returns null when the merchant is not `priceable` — an auto-calculated NPC whose
 * stats the engine invents at load. Refusing beats returning a number computed from
 * zeros, which would read as an implausibly good deal.
 */
export function barterOffer(
  merchant: Merchant,
  player: Haggler,
  basePrice: number,
  buying: boolean,
  formula: BarterFormula,
  settings: { fFatigueBase: number; fFatigueMult: number },
  disposition = merchant.disposition ?? formula.dispositionBaseline,
): number | null {
  if (basePrice === 0) return 0;
  if (!merchant.haggles) return basePrice;
  if (!merchant.priceable) return null;

  const side = (h: Haggler) =>
    Math.min(h.mercantile, formula.mercantileCap)
    + Math.min(formula.luckWeight * h.luck, formula.luckCap)
    + Math.min(formula.personalityWeight * h.personality, formula.personalityCap);

  const pcTerm = (disposition - formula.dispositionBaseline + side(player))
    * fatigueTerm(player.fatigueRatio, settings);
  const npcTerm = side({
    mercantile: merchant.mercantile!,
    luck: merchant.luck!,
    personality: merchant.personality!,
  }) * fatigueTerm(undefined, settings);

  const buyTerm = formula.percentScale * (formula.buyBase - formula.termWeight * (pcTerm - npcTerm));
  const sellTerm = formula.percentScale * (formula.sellBase - formula.termWeight * (npcTerm - pcTerm));
  // The engine truncates toward zero here, then floors at 1.
  return Math.max(formula.minimumPrice, Math.trunc(basePrice * (buying ? buyTerm : sellTerm)));
}
