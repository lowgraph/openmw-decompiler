# App bundle packager

Run in this project's VS Code terminal:

```powershell
python build_app_bundle.py
```

This reads a completed catalog release and writes the files the website downloads.
It opens no databases, reads no plugins, and never modifies the catalog release.
Python 3.10+ is sufficient; there are no new dependencies.

Default input is `A:\Cache\OpenMWFoundation\catalogs`, default output is
`A:\Cache\OpenMWFoundation\app-bundle`. See `bundle-types.ts` for the app contract,
including the resolution rule and a reference `applyDelta`.

## What it changes about the catalogs

The catalog release is the complete, per-profile reference copy. The bundle is the
shipped copy, and differs from it in three ways.

**Book prose is excluded.** Catalog schema 1.1.0 already writes it to a separate
`BookText.json`; a 1.0.0 release still carries `text` inside `Books.json`, and the
packager strips it either way, so an old release does not need rebuilding first.
Skill, scroll, value, weight and enchantment fields all remain. Pass
`--include-book-text` to publish the prose as its own file, which requires a 1.1.0
release. The site should fetch it only when it actually displays a book.

**Catalogs built elsewhere are picked up.** `GearRows` and `EffectRules` are produced
by their own tools rather than decoded from the foundation, and publish
`<profile>-<hash>.json` files that the packager reads. Each must come from the same
extraction snapshot as the catalogs, carry a unique `key` per entry, and exist for every
selected profile — a catalog missing from one profile is a bundle the loader refuses, so
the packager refuses it first with a message naming the profile. Whatever produced the
records travels with them as payload fields, which the loader accepts. `--no-gear-rows`
and `--no-rules` leave them out; `--gear-rows` and `--rules` read them from elsewhere.

**Gear rows ship as a catalog.** `build_gear_rows.py` writes its own artifact per
profile; the packager reads the newest file for each and publishes it as `GearRows`,
keyed by row. The policy, limits, categories and coverage that produced the rows travel
with them as payload fields, which the loader accepts. Rows must come from the same
extraction snapshot as the catalogs, must carry a unique `key` per row, and must exist
for every selected profile — a catalog missing from one profile is a bundle the loader
refuses, so the packager refuses it first with a message naming the profile. Pass
`--no-gear-rows` to publish catalogs only, or `--gear-rows` to read them from elsewhere.
ARCE inherits them unchanged, because the rows are identical to TR's.

**ARCE is published as a delta.** ARCE toggles which races and classes are playable;
it is not a separate body of game data. Any catalog whose records are identical to
the base profile's is listed in `inherits` and published once. The rest are published
as `{changed, removed}` against that base. Base selection is by matching world and
version with `arce: false`; a base profile is always complete, so resolution never
recurses. Selecting `tr_arce` on its own instead publishes it in full.

Measured against bundle `05c8e35f088e181ca115d94c`:

| Profile | Files | Inherited | Raw | Gzipped |
| --- | --- | --- | --- | --- |
| `vanilla` | 23 | 0 | 3.86 MB | 271 KB |
| `tr` | 23 | 0 | 14.35 MB | 988 KB |
| `tr_arce` | 3 | 20 | 0.08 MB | **13 KB** |

Gear rows cost 12 KB gzipped on vanilla and 16 KB on TR, effect rules 7 KB and 8 KB.
Both cost ARCE nothing: its rows and rules are byte-identical to TR's, so it inherits
them. Effect rules are the one catalog where vanilla and TR genuinely differ in record
count — 141 against 186 — because Tamriel Rebuilt registers 45 effects through Lua
that no plugin file defines.

A visitor loads one profile: 271 KB gzipped for Vanilla, 988 KB for TR, 883 KB for
TR + ARCE. ARCE comes out lighter than TR because its own Spells, Races and Classes
deltas replace TR's full copies. Book prose alone would have added 2.7 MB per profile.

## Outputs

`current.json` points at an immutable bundle directory named by a hash of the source
snapshot, packager version, catalog schema, selected profiles, the book-text choice
and the gear row files consumed, so a rows rebuild produces a new bundle rather than
silently reusing the old one. Every published file records `bytes`, `gzipBytes` and `sha256` in the manifest,
so the download budget is auditable without re-reading the files, and the hashes serve
as cache keys. Payloads are written compactly; `gzipBytes` is a measurement, not a
stored artifact, because the CDN negotiates its own transport encoding.

Publication stages into a temporary directory, renames it into place, then replaces
the pointer atomically. A failure before pointer replacement leaves the previous
bundle active. Completed bundles are retained and never deleted automatically.

## Options and verification

```powershell
python build_app_bundle.py --profile vanilla --profile tr
python build_app_bundle.py --no-gear-rows --no-rules
python build_app_bundle.py --catalogs A:\Cache\OpenMWFoundation\catalogs\<releaseId>
python build_app_bundle.py --output A:\Cache\BundlePreview
python -m unittest test_app_bundle -v
```

`--catalogs` accepts either a release directory or the folder holding `current.json`.
An identical existing bundle is not overwritten; use a different `--output` to rebuild.
Close any running packager before removing a stale `build.lock` left by a forced kill.

Tests cover the prose split, ARCE inheritance and delta reconstruction, delta
semantics for changed/added/removed and for derived rows that join on `id`, base
selection across worlds and versions, single-profile selection, manifest size and
hash agreement, atomic publication, a schema 1.0.0 release, and gear rows: their
catalog and travelling policy, ARCE inheriting them, omission when absent or declined,
and refusal on a partial profile set, a foreign snapshot, a missing key or a duplicate.

## What this stage does not do

It does not evaluate obtainability, price, theft or early-game eligibility. It ships
those verdicts as gear rows, but the policy that produced them is authored separately
and versioned on its own, and the packager only carries it. It does not package
world, services, journal, acquisition or script-evidence data — those remain local
tooling databases behind their own query tools. It does not upload anything, set
cache headers, or decide the site's storage layout.

`query_item_sources.py` and the five extraction databases are untouched by this
stage and by the catalog schema bump. Nothing here reads `world.sqlite`.
