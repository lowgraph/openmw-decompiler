# Extraction foundation — start here

This is the replacement foundation for the larger app. It preserves source data
and resolves profiles without expanding inventories into millions of location paths.
The old item and location exporters are prototypes; do not run them to build this
foundation. Existing JSON exports and the separate website are not modified.

## Run in VS Code

Open this project folder and use Python 3.10 or newer. No pip installation is
needed for the foundation; SQLite is included with Python.

```powershell
python extract_foundation.py --list-plugins
python extract_foundation.py
```

Or select **Build extraction foundation (recommended)** in VS Code's Python
Run and Debug configuration. The first command only previews paths and profiles.
The second builds:

**`A:\Cache\OpenMWFoundation\game-data.sqlite`**

Staging databases, SQLite rollback journals, and the build lock live in that
directory on A:. No large temporary database is created in Windows Temp on C:.
SQLite cache is configured to approximately 32 MiB; individual plugin records
and SQLite auxiliary operations also use memory. Records are read one at a time,
not accumulated as a Python object graph. Profile indexes reference shared source
records instead of copying their payloads. No inventory-path expansion runs.

Progress is printed during archiving and resolution. Database integrity checking
is a separate final phase. Runtime and final size depend on the installed files;
the full build has not been run during implementation.

## The three profiles

`foundation_config.json` explicitly defines:

| Profile | Included content |
| --- | --- |
| `vanilla` | Morrowind, Tribunal, Bloodmoon |
| `tr` | Vanilla plus Tamriel_Data, Cyr_Main, TR_Mainland, TR_Factions, Firemoth patch, Sky_Main |
| `tr_arce` | TR profile plus ARCE |

Profiles use `world: vanilla / tamriel_rebuilt`, your version labels, and a separate
ARCE flag. The app's existing `world: tr` is a UI/state alias to adapt later.

Source directories, encoding, and the approved file/folder allowlists come from
`export_config.json` and its `openmwConfig`. Later approved data directories win
filename collisions. **Profile load order comes from foundation_config.json**, not
the currently enabled `content=` entries: all three profiles must be available
even while one profile is selected in OpenMW. Thus ARCE can be archived while
disabled, provided its approved data directory is configured. Every dependency
must appear earlier in its profile or the build fails.

Change these manifests when intentionally updating versions or plugin membership.
This is not automatic discovery of all installed mods. Assets, BSAs, Lua scripts,
and saves are outside this first extraction stage.

## What's in the database

| Table/view | Contents |
| --- | --- |
| `metadata` | Schema version, snapshot ID, encoding, build time, profile definitions |
| `plugins` | Paths, byte sizes, modification timestamps, SHA-256 fingerprints, dependencies |
| `record_versions` | Every record in each approved plugin, original order/offset/header flags, untouched binary payload, indexed identity where supported |
| `reference_versions` | Every CELL reference revision, stable reference ID, object ID, source/destination cell, deletion flag, pointer to its archived bytes |
| `profiles`, `profile_plugins` | Explicit profile memberships and load orders |
| `resolved_records` | Origin plugin and winning record revision per identity/profile, including deleted winners |
| `resolved_references` | Origin and winning reference revision per profile, including deleted winners |
| `live_records`, `live_references` | Nondeleted resolved rows; references in deleted cells are excluded |

The complete original record header and payload are retained. Tests reconstruct
the fixture plugins byte-for-byte from the archive. File hashing occurs during
the read, and size/mtime are checked afterward to detect files changing during
extraction. The snapshot ID covers schema version, encoding, ordered fingerprints,
and profile configuration; it is repeatable for identical inputs.

Record identity includes **record type plus a canonical key**; display IDs retain
their original spelling. Named IDs are case-insensitive. SKIL/MGEF use numeric
indices, CELL/LAND use cell identities, and INFO uses a topic-and-info-ID pair.
Deleted winning records remain as tombstones, so removing a mod restores the
earlier profile's data. Later undeletes preserve origin provenance.

CELL references resolve individually, so overriding one chest does not discard
other placements in that cell. Master-relative FRMR IDs resolve through each
plugin's dependency list. MVRF/CNDT moved references use the destination exterior.
Reference payload offsets point into the corresponding archived CELL payload;
the large bytes are not stored twice.

## What this stage does not yet do

This is an **archive and identity-resolution foundation**, not the app's final
typed catalogs. Inventory entries, leveled lists, effects, quest conditions, and
merchant data are retained in their original records, ready for subsequent
decoders. They are not yet exposed as normalized typed tables or browser JSON.

PGRD and unknown record types are preserved but not assigned guessed semantic
identities. They are reported after the build. TES3 headers are archive-only.
The `live_records` CELL row is the latest cell revision; optional cell-property
inheritance across revisions must be implemented by the later typed cell decoder.
References already resolve independently. Engine calculations, runtime scripts,
save state, asset extraction, and early-game policy evaluation are not simulated.

The snapshot and raw record store let later decoders rebuild their output without
reading installed plugins again. Those decoders must version their own schemas
and record the source snapshot. The SQLite file is local tooling storage, not a
replacement for the website's Clerk/D1/R2 architecture or a browser download.

## Inspect after building

```powershell
python inspect_foundation.py --profile vanilla
python inspect_foundation.py --profile tr
python inspect_foundation.py --profile tr_arce
python inspect_foundation.py --profile tr --type WEAP --id katana_goldbrand_unique
```

Summary commands show record counts and live reference counts. A record query
shows original/winning plugin, deletion state, and its binary subrecords. This is
a debugging tool, not a formatted weapon display. It opens the database read-only.

## Rebuilds, cancellation, and checks

Each run is a full rebuild, not an incremental update. It creates a staging file,
checks SQLite integrity and foreign keys, then replaces the published database.
Allow space for both the old database and the new staged database during rebuilds.
Parsing errors and Ctrl+C leave the previous published database intact. Close
database viewers before replacing it on Windows.

Only one build can run for a destination. A forced kill or power loss can leave
`game-data.lock` and `.foundation-*` staging files. Check that the build is no longer
running before manually deleting only those stale files. Normal cancellation
cleans them up automatically.

```powershell
python -m unittest test_foundation -v
```

Tests use small synthetic plugins: exact binary reconstruction and hashes, profile
overrides, deletions/undeletes, original provenance, moved/deleted cell references,
topic-scoped dialogue IDs, dependency failures, invalid binary data, repeatable
snapshots, disabled-plugin discovery, and preservation of existing output on failure.
