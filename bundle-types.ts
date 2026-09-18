/**
 * Contract for app bundle schema 1.0.0 — the files the site downloads.
 *
 * Resolution rule, in full:
 *   1. Read manifest.json.
 *   2. For profile P and catalog C: if C is in P.files, fetch that file.
 *      - kind "full"  -> use records.
 *      - kind "delta" -> fetch the base profile's C (always kind "full"),
 *                        drop every key in removed, then upsert changed by key.
 *   3. Otherwise C is in P.inherits: fetch the base profile's C and use it as is.
 * A base profile always has base: null, so resolution never recurses.
 */
import type { Profile } from "./catalog-types";

export type CatalogName = string;

export type BundleFile = {
  path: string;
  /** Bytes as served before transport compression; gzipBytes is the size budget. */
  bytes: number;
  gzipBytes: number;
  sha256: string;
  /** Records in the resolved catalog, after any delta is applied. */
  records: number;
} & (
  | { kind: "full" }
  | { kind: "delta"; base: string; changed: number; removed: number }
);

export type BundleProfile = Profile & {
  /** The profile this one is expressed against, or null when it is complete. */
  base: string | null;
  files: Record<CatalogName, BundleFile>;
  /** Catalogs identical to the base's, published only once. */
  inherits: CatalogName[];
};

export type BundleManifest = {
  schemaVersion: "1.0.0";
  bundleId: string;
  snapshotId: string;
  catalogSchemaVersion: string;
  catalogReleaseId: string;
  catalogs: CatalogName[];
  profiles: BundleProfile[];
  builtAtUnix: number;
  totals: { files: number; bytes: number; gzipBytes: number };
};

export type BundlePointer = { bundleId: string; manifest: string; snapshotId: string };

export type FullPayload<T> = {
  schemaVersion: "1.0.0"; snapshotId: string; profile: Profile;
  catalog: CatalogName; kind: "full"; records: T[];
};

export type DeltaPayload<T> = {
  schemaVersion: "1.0.0"; snapshotId: string; profile: Profile;
  catalog: CatalogName; kind: "delta"; base: string;
  /** New or altered records, complete — never field-level patches. */
  changed: T[];
  /** Keys present in the base and absent here. */
  removed: string[];
};

export type BundlePayload<T> = FullPayload<T> | DeltaPayload<T>;

/** Records join on `key`; derived rows such as Attributes only carry `id`. */
export function recordKey(record: { key?: string; id?: string }): string {
  const value = record.key ?? record.id;
  if (value === undefined) throw new Error("Bundle record has neither key nor id");
  return value;
}

export function applyDelta<T extends { key?: string; id?: string }>(base: T[], payload: BundlePayload<T>): T[] {
  if (payload.kind === "full") return payload.records;
  const rows = new Map(base.map((record) => [recordKey(record), record]));
  for (const key of payload.removed) rows.delete(key);
  for (const record of payload.changed) rows.set(recordKey(record), record);
  return [...rows.values()];
}
