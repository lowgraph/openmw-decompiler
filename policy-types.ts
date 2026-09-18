/**
 * Contract for policy schema 1.0.0 — authored verdicts over extracted evidence.
 *
 * Verdicts are refusable. `earlyGameEligible` is null and `obtainable` is "unknown"
 * when the evidence was truncated and nothing eligible was found: a capped search
 * proves a positive, never a negative. Treat null as "ask again with a higher cap",
 * not as false.
 */
export type RouteQuality = "direct" | "inventory" | "restocking" | "random";
export type Acquisition = "direct" | "take" | "purchase" | "theft" | "pickpocket";
export type Obtainable = "guaranteed" | "random" | "script_conditional" | "none" | "unknown";
export type SaleStatus = "restocking" | "stocked" | "not_sold";

export type ActorThreat = {
  key: string; level: number; health: number; fight: number;
  /** Present when this actor is the item's holder rather than part of the cell. */
  role?: "holder";
};

export type Danger = {
  cellKey: string; characterLevel: number;
  hostiles: number; maxActorLevel: number; totalHealth: number;
  actors: ActorThreat[];
};

export type Limits = {
  maxHostiles: number; maxActorLevel: number; maxTotalHealth: number;
} & (
  | { source: "authored" }
  | { source: "benchmark"; benchmark: { profile: string; cellKey: string; label?: string; measured: Danger } }
);

export type Route = {
  holder: { key: string; name: string | null; recordType: string };
  quality: RouteQuality;
  sourceQuality: "guaranteed" | "random";
  acquisition: Acquisition;
  cellKey: string; referenceKey: string;
  ownerKey: string | null; factionKey: string | null;
  lockLevel: number; trapId: string | null;
  /** The actor this route must be taken from, when the item is carried. */
  heldBy: ActorThreat | null;
  theftRequired: boolean;
  price: number | null;
  danger: Danger;
  dangerWithinBenchmark: boolean;
  earlyGameEligible: boolean;
  /** Empty exactly when the route is eligible; otherwise why it is not. */
  reasons: string[];
};

export type Assessment = {
  policy: { version: string; name: string | null; schemaVersion: string; evaluatorVersion: string };
  limits: Limits;
  obtainable: Obtainable;
  theftRequired: boolean | null;
  evidenceTruncated: boolean;
  saleStatus: SaleStatus;
  /** Lowest catalog base value among purchase routes. Merchant markup is not simulated. */
  price: number | null;
  /** null means undetermined under truncated evidence, not ineligible. */
  earlyGameEligible: boolean | null;
  basisValue: number | null;
  counts: { routes: number; guaranteed: number; earlyGameEligible: number; scriptGrants: number };
  coverage: string;
  routes: Route[];
};

/** The shape before a policy is supplied: evidence alone yields no verdict. */
export type EmptyAssessment = {
  obtainable: null; theftRequired: null; saleStatus: null;
  price: null; earlyGameEligible: null;
};
