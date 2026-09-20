/**
 * Contract for places schema 1.0.0 — what a `cellKey` actually refers to.
 *
 * Gear rows, merchants and travel all identify somewhere by cell key. This is the only
 * catalog that can turn one into a name, a region and a position, so it is the join
 * every "where do I get this" answer goes through.
 *
 * The bundle refuses to publish if any cell key named by another catalog is missing
 * here, so within one bundle the join is total: you never need a fallback for an
 * unresolved key.
 */
import type { Profile } from "./catalog-types";

export type Place = {
  /** `interior:<name>` or `exterior:<x>,<y>`, lowercased, as every other catalog spells it. */
  key: string;
  interior: boolean;
  /** Absent when the cell has no name. Most exterior wilderness does not — 4,801 cells
   *  in TR — so this is the common case outdoors, not a gap. */
  name?: string;
  /** Absent when the record carries none, which is normal for interiors. */
  region?: string;
  /** World grid position. Present for exteriors only. */
  grid?: [number, number];
  /** Present and true when the extraction inferred this cell from a reference rather
   *  than reading a CELL record. */
  synthetic?: true;
};

/** Exterior cells sharing a name: a town is several grid squares, Port Telvannis is 7. */
export type Settlement = {
  name: string;
  cells: string[];
  /** The rounded middle of `bounds`. Good enough to point at; not a claim about where
   *  the town centre is. */
  centre: [number, number];
  bounds: { minX: number; maxX: number; minY: number; maxY: number };
};

export type PlaceCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  derivation: {
    method: string;
    places: number; named: number; interiors: number; exteriors: number;
    settlements: number; settlementsSpanningSeveralCells: number;
    regions: number; synthetic: number;
  };
  regions: Array<{ key: string; cells: number }>;
  settlements: Settlement[];
  coverage: string;
  records: Place[];
};

/** Index once; every other catalog's cellKey resolves through it. */
export function placeIndex(catalog: PlaceCatalog): Map<string, Place> {
  return new Map(catalog.records.map(place => [place.key, place]));
}

/**
 * How to show a cell key to a reader.
 *
 * Falls back to the region for unnamed wilderness, and to the key itself only when the
 * catalog has neither — which within a valid bundle means the key came from somewhere
 * that is not a place.
 */
export function placeLabel(place: Place | undefined, key: string): string {
  if (!place) return key;
  if (place.name) return place.name;
  if (place.region) return place.region;
  return key;
}

/** The settlement an exterior cell belongs to, if any. */
export function settlementOf(
  catalog: PlaceCatalog,
  key: string,
): Settlement | undefined {
  return catalog.settlements.find(town => town.cells.includes(key));
}

/**
 * Grid distance between two places, in cells. Null when either is an interior or
 * missing: an interior has no position of its own, and guessing one from its name
 * would be a fiction.
 */
export function cellDistance(a: Place | undefined, b: Place | undefined): number | null {
  if (!a?.grid || !b?.grid) return null;
  return Math.hypot(a.grid[0] - b.grid[0], a.grid[1] - b.grid[1]);
}
