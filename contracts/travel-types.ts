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

/** The provider's class decides this. Null is a real answer: a one-off transport that
 *  belongs to no network — a slave, a fisherman, a Telvanni retainer doing a favour. */
export type TravelMode =
  | "silt_strider" | "boat" | "gondola" | "riverstrider" | "guild_guide" | null;

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
};

export type TravelNode = {
  key: string;
  /** Null for an exterior cell that carries no name of its own; fall back to `region`. */
  name: string | null;
  interior: boolean;
  region: string | null;
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
  authored: { source: "authored"; guildGuide: unknown; conjurerRank: unknown };
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
    unplacedProviders: string[];
    destinationsSkipped: number;
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
