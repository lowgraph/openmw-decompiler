/**
 * Contract for access schema 1.0.0: the way into every interior, and where land is.
 *
 * Records cover every interior Places publishes. Exteriors need none: a grid square is
 * reached by walking to it. Nothing here is a path over the terrain; a walk is a
 * straight line, checked against the land mask so it never swims open sea.
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
};

export type AccessCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  /** OpenMW 0.51.0's walk and run speed, described; the settings come from GameSettings. */
  walking: {
    source: "authored"; transcribedFrom: string; functions: string; note: string;
    gameSettings: string[]; timescale: number; timescaleNote: string;
  };
  landMask: { blocks: 8; blockSize: 1024; waterLevel: number; bitOrder: string; source: string };
  /** Exterior cell key -> 16 hex digits, bit by*8+bx set where block (bx, by) has land.
   *  A cell missing from here is sea. */
  land: Record<string, string>;
  derivation: {
    method: string; interiors: number; reachable: number; sealed: number;
    deepest: number; landCells: number;
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
