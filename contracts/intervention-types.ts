/**
 * Contract for intervention schema 1.0.0: where Divine and Almsivi Intervention land,
 * from every place in the game.
 *
 * The engine's answer depends only on the cell the spell is cast in, so it is worked
 * out once per cell and looked up. Records cover exactly the cells Places publishes;
 * the bundle refuses a key Places does not have.
 */
import type { Profile } from "./catalog-types";

export type InterventionKind = "divine" | "almsivi";

export type InterventionMarker = {
  /** The marker's placement, e.g. "morrowind.esm:0004218a". */
  reference: string;
  /** The cell you land in; a key into Places. */
  cell: string;
  /** World units [x, y], rounded. */
  pos: [number, number];
  /** The landing cell's name; null for unnamed wilderness. */
  name: string | null;
  /** The town, by the travel policy's town rule: "Vivec, Temple" is Vivec. Null when
   *  no town is certain. Forts such as Moonmoth Legion Fort are their own places. */
  town: string | null;
};

export type InterventionRecord = {
  /** A Places key. */
  key: string;
  /** Index into `markers.divine`; null where the spell finds no marker and fails. */
  divine: number | null;
  almsivi: number | null;
  /** Present only when the engine's own cell or door order, which the data
   *  approximates, could pick another marker: the other possible indices per kind. */
  ambiguous?: Partial<Record<InterventionKind, Array<number | null>>>;
};

export type InterventionCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  /** World::getClosestMarker from OpenMW 0.51.0, described; authored, not extracted. */
  rule: {
    source: "authored"; transcribedFrom: string; functions: string;
    markers: Record<InterventionKind, string>; cellSize: number; note: string;
  };
  markers: Record<InterventionKind, InterventionMarker[]>;
  derivation: {
    method: string; places: number;
  } & Record<InterventionKind, {
    markers: number; exteriorMarkers: number; interiorMarkers: number;
    markersSharingACell: string[];
    placesWithNoAnswer: number; placesWithAnAmbiguousAnswer: number;
  }>;
  coverage: string;
  records: InterventionRecord[];
};

/** Where one spell cast from `cellKey` lands, or null when it fails there. */
export function landing(
  catalog: InterventionCatalog, byKey: Map<string, InterventionRecord>,
  cellKey: string, kind: InterventionKind,
): InterventionMarker | null {
  const index = byKey.get(cellKey)?.[kind];
  return index == null ? null : catalog.markers[kind][index] ?? null;
}
