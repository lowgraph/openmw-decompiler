/**
 * Contract for travel schema 1.0.0 — the fast travel network and its two toggles.
 *
 * An edge is one journey a provider will sell: the cell you speak to them in, the cell
 * they put you down in. Routing is a search over `records`; `nodes` and `providers` are
 * lookup tables for labelling what the search returns.
 *
 * Teleport doors are not here. Walking between interiors and exteriors is a separate
 * graph of 17,156 links, forty times the size, and it answers a different question.
 */
import type { Profile } from "./catalog-types";

/** The provider's class decides this, except for Caravaners, where the vehicle at their
 *  stop does: Tamriel Rebuilt gives sky lamp, pack guar and carriage operators the same
 *  class as silt strider ones. Null is a real answer: a one-off transport that belongs to
 *  no network — a slave, a fisherman, a Telvanni retainer doing a favour. The new modes
 *  are additive to schema 1.0.0; a reader should treat any unknown mode as a transport. */
export type TravelMode =
  | "silt_strider" | "pack_guar" | "sky_lamp" | "carriage"
  | "boat" | "gondola" | "riverstrider" | "guild_guide" | null;

export type TravelEdge = {
  /** `provider|from|to`. Unique within a profile; the bundle enforces that. */
  key: string;
  /** Key into `providers`. */
  provider: string;
  /** Keys into `nodes`. */
  from: string;
  to: string;
  mode: TravelMode;
  /** True for guild guide journeys. Hide these when the player is not a member. */
  requiresMageGuild: boolean;
  /** True for the rank-gated long-distance guild guide network in Tamriel Rebuilt.
   *  Always false on `vanilla`. Every such edge also has requiresMageGuild true, so
   *  turning membership off already removes them. */
  requiresConjurer: boolean;
  /** Additive to schema 1.0.0 since policy 2026.09.27.2. What the travel window asks
   *  before barter and followers, per `travelFormula`. Null when either end has no
   *  known position. Absent from older releases. */
  price?: number | null;
  /** Whole in-game hours the journey takes; 0 from a provider standing indoors. */
  hours?: number | null;
  /** Straight-line distance in game units, provider to landing point. */
  distance?: number;
  /** Where the provider stands and where you land, world units [x, y], rounded. */
  fromPos?: [number, number];
  toPos?: [number, number];
};

export type TravelNode = {
  key: string;
  /** Null for an exterior cell that carries no name of its own; fall back to `region`. */
  name: string | null;
  interior: boolean;
  region: string | null;
  /** Additive. The town this stop belongs to: the name up to the first comma, so
   *  "Old Ebonheart, Docks" and "Old Ebonheart, Guild of Mages" are both Old Ebonheart.
   *  An unnamed stop takes the town beside it; null when no town is certain. Route
   *  between towns, and name the district as where to board. */
  town?: string | null;
  /** What followed the comma: "Docks", "Guild of Mages". Null for a bare town name. */
  district?: string | null;
  /** How the town was decided: its own name, the nearest named cells, or the policy. */
  townRule?: "name" | "nearest" | "override" | null;
};

/** The seller's side of getBarterOffer. Additive. */
export type TravelBarter = {
  mercantile: number | null; personality: number | null; luck: number | null;
  /** The record's base disposition, before race, personality and faction adjust it. */
  disposition: number | null;
  /** "record" when the NPC stores its stats, "derived" when rerun as OpenMW's autocalc. */
  statsSource: "record" | "derived" | null;
  /** False for a creature: getBarterOffer returns its price unchanged. */
  haggles: boolean;
  priceable: boolean;
  race: string | null;
  female: boolean;
};

export type TravelProvider = {
  key: string;
  name: string;
  /** "NPC_" for almost all of them, "CREA" for Thazlorakis. */
  recordType: string;
  /** The NPC class, or null for a creature, which carries none. */
  class: string | null;
  mode: TravelMode;
  /** Cells this provider stands in. Normally one. */
  cells: string[];
  guildGuide: boolean;
  /** The vehicle model that decided `mode`, when one did. */
  vehicle?: string;
  /** Additive. Present when the release is priced. */
  barter?: TravelBarter;
};

/** OpenMW 0.51.0's travel window, transcribed; `settings` holds this profile's values. */
export type TravelFormula = {
  source: "authored"; transcribedFrom: string; function: string; note: string;
  minimumPrice: 1; followersMultiplyPrice: true;
  interiorProviderChargesFlat: "fMagesGuildTravel";
  gameSettings: string[];
  settings: { fTravelMult: number; fTravelTimeMult: number; fMagesGuildTravel: number };
};

/** Both default to the value here, not to false. */
export type TravelToggles = {
  mageGuildMember: { default: true; appliesTo: "all"; note: string };
  conjurerRank: { default: false; appliesTo: Profile["id"][]; note: string };
};

export type TravelCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  /** The authored policy's own version, which moves independently of the snapshot. */
  policyVersion: string;
  toggles: TravelToggles;
  /** The two rules the travel records cannot supply, kept verbatim so the reasoning
   *  ships with the data rather than living only in a commit message. */
  authored: { source: "authored"; guildGuide: unknown; conjurerRank: unknown; towns?: unknown };
  /** Additive; null or absent in an unpriced release. */
  travelFormula?: TravelFormula | null;
  /** The same literals the Merchants catalog carries, so Travel prices on its own. */
  barterFormula?: Record<string, unknown> | null;
  verification: {
    providers: number; edges: number; nodes: number;
    guildGuides: number;
    /** How many the NPC-class rule finds. Lower than `guildGuides` by design: a
     *  creature has no class. */
    guildGuidesByClass: number;
    /** Every provider the two rules disagree about, with enough to judge it. */
    classDisagreement: Array<{
      key: string; name: string; recordType: string;
      class: string | null; byDestination: boolean;
    }>;
    conjurerEdges: number;
    providersWithUnknownMode: string[];
    /** How many operators each vehicle marker classified. */
    vehicleModes?: Record<string, number>;
    /** Placed operators of a vehicle-read class with no vehicle near; they keep the class mode. */
    operatorsWithoutVehicle?: string[];
    unplacedProviders: string[];
    destinationsSkipped: number;
    /** Additive. */
    towns?: number;
    stopsWithoutTown?: string[];
    edgesWithoutPrice?: string[];
    providersWithoutBarterStats?: string[];
  };
  nodes: Record<string, TravelNode>;
  providers: Record<string, TravelProvider>;
  coverage: string;
  records: TravelEdge[];
};

/**
 * The edges a character can actually use. Apply this before any routing: a path found
 * over the full graph may not exist for this player.
 */
export function usableEdges(
  catalog: TravelCatalog,
  player: { mageGuildMember?: boolean; conjurerRank?: boolean } = {},
): TravelEdge[] {
  const member = player.mageGuildMember ?? catalog.toggles.mageGuildMember.default;
  const conjurer = player.conjurerRank ?? catalog.toggles.conjurerRank.default;
  return catalog.records.filter(edge =>
    (member || !edge.requiresMageGuild) && (conjurer || !edge.requiresConjurer));
}

/**
 * What a journey costs this player, as OpenMW 0.51.0 charges it: the published base
 * price times one plus the followers, then getBarterOffer. `playerDisposition` is the
 * provider's derived disposition toward the player, which the site has to estimate.
 * Returns null when the release or the provider carries no price.
 */
export function journeyPrice(
  catalog: TravelCatalog, edge: TravelEdge,
  player: { mercantile: number; personality: number; luck: number;
            fatigueTerm?: number; followers?: number; playerDisposition: number },
): number | null {
  const provider = catalog.providers[edge.provider];
  const barter = provider?.barter;
  if (edge.price == null || !barter || !barter.priceable) return null;
  const base = Math.max(1, edge.price * (1 + (player.followers ?? 0)));
  if (!barter.haggles) return base;
  const fatigue = 1.25; // fFatigueBase at full fatigue, the seller's usual state
  const pcTerm = (player.playerDisposition - 50 + Math.min(player.mercantile, 100)
    + Math.min(0.1 * player.luck, 10) + Math.min(0.2 * player.personality, 10))
    * (player.fatigueTerm ?? fatigue);
  const npcTerm = (Math.min(barter.mercantile!, 100) + Math.min(0.1 * barter.luck!, 10)
    + Math.min(0.2 * barter.personality!, 10)) * fatigue;
  return Math.max(1, Math.trunc(base * 0.01 * (100 - 0.5 * (pcTerm - npcTerm))));
}
