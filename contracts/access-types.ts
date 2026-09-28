/**
 * Contract for access schema 1.2.0: the way into every interior, where land is, and
 * where a walk can go.
 *
 * Records cover every interior Places publishes. Exteriors need none: a grid square is
 * reached by walking to it. 1.1.0 adds `walkable`, a grid graded from the terrain's
 * heights that a site finds paths over; 1.0.0 readers ignore it and walk the straight
 * line checked against the land mask, as before. 1.2.0 adds `doors` to sealed rooms.
 */
import type { Profile } from "./catalog-types";

export type AccessRecord = {
  /** An interior's Places key. */
  key: string;
  /** Doors between this room and the outside; 0 when a door here opens outdoors. Null
   *  when none does: reached by a script or a spell, or not at all. */
  depth: number | null;
  /** The next room towards the outside. Follow it to depth 0, then read the list
   *  backwards for the way in. Absent at depth 0 and for sealed rooms. */
  via?: string;
  /** Up to four points outdoors, world units [x, y], where the nearest way out opens. */
  exits: Array<[number, number]>;
  /** Since 1.2.0, on sealed rooms (depth null) only: the rooms this one's doors join,
   *  either way through the door. Walk them to a room a teleport reaches, as Mournhold's
   *  streets lead to the room its transport arrives in. Empty when the room has no doors. */
  doors?: string[];
};

/** A wall policy/walking.json names, as it was drawn in this profile. */
export type WalkableBarrier = {
  name: string;
  /** Placements joined round the ring, pairs joined, and pairs further apart than maxGap. */
  pieces: number; joined: number; unjoined: number;
  /** Placements of the openings, and the squares walled and opened. */
  openings: number; squares: number; gateSquares: number;
};

/**
 * The walkable grid. Each exterior cell is squaresPerCell x squaresPerCell squares of
 * squareSize units, coded two bits each (see `codes`): 0 open sea, 1 land, 2 too steep
 * or a wall, 3 water within swimReach squares of land. A path may enter 1 and 3.
 */
export type Walkable = {
  policyVersion: string;
  squaresPerCell: number;
  squareSize: number;
  /** Share of a square's terrain triangles steeper than maxSlopeDegrees that blocks it. */
  steepShare: number;
  swimReach: number;
  /** OpenMW's steepest walkable slope, Constants::sMaxSlope. */
  maxSlopeDegrees: number;
  transcribedFrom: string;
  slopeSource: string;
  codes: Record<"0" | "1" | "2" | "3", string>;
  encoding: string;
  barriers: WalkableBarrier[];
  note: string;
  /** Exterior cell key -> base64 of the packed squares, four a byte, the first square in
   *  the low bits; squares run west to east, then south to north. A cell missing from
   *  here is open sea. */
  cells: Record<string, string>;
};

export type AccessCatalog = {
  schemaVersion: "1.0.0" | "1.1.0" | "1.2.0";
  profile: Profile["id"];
  snapshotId: string;
  /** OpenMW 0.51.0's walk, run and swim speed, described; the settings come from GameSettings. */
  walking: {
    source: "authored"; transcribedFrom: string; functions: string; note: string;
    swimNote?: string; gameSettings: string[]; timescale: number; timescaleNote: string;
  };
  landMask: { blocks: 8; blockSize: 1024; waterLevel: number; bitOrder: string; source: string };
  /** Exterior cell key -> 16 hex digits, bit by*8+bx set where block (bx, by) has land.
   *  A cell missing from here is sea. */
  land: Record<string, string>;
  /** Since 1.1.0. */
  walkable?: Walkable;
  derivation: {
    method: string; interiors: number; reachable: number; sealed: number;
    /** Since 1.2.0: sealed rooms with at least one door to another room. */
    sealedWithDoors?: number;
    deepest: number; landCells: number;
    /** Since 1.1.0. */
    walkableCells?: number; landSquares?: number; blockedSquares?: number;
    swimSquares?: number; wallSquares?: number;
  };
  coverage: string;
  records: AccessRecord[];
};

/** True when world point (x, y) is on land by the mask. */
export function onLand(catalog: AccessCatalog, x: number, y: number): boolean {
  const cx = Math.floor(x / 8192), cy = Math.floor(y / 8192);
  const mask = catalog.land[`exterior:${cx},${cy}`];
  if (!mask) return false;
  const bx = Math.min(7, Math.floor((x - cx * 8192) / 1024));
  const by = Math.min(7, Math.floor((y - cy * 8192) / 1024));
  return (BigInt("0x" + mask) >> BigInt(by * 8 + bx) & 1n) === 1n;
}

/** The code of square (gx, gy) of the walkable grid; a cell it lacks is open sea (0). */
export function squareAt(walkable: Walkable, gx: number, gy: number): 0 | 1 | 2 | 3 {
  const per = walkable.squaresPerCell;
  const cx = Math.floor(gx / per), cy = Math.floor(gy / per);
  const text = walkable.cells[`exterior:${cx},${cy}`];
  if (!text) return 0;
  const packed = Uint8Array.from(atob(text), c => c.charCodeAt(0));
  const index = (gy - cy * per) * per + (gx - cx * per);
  return ((packed[index >> 2] >> ((index & 3) * 2)) & 3) as 0 | 1 | 2 | 3;
}
