# Normalized world catalog builder

Run in the VS Code terminal:

```powershell
python build_world_catalog.py
```

Or use **Build normalized world catalog** in Run and Debug. Python 3.10+ is enough;
there are no new dependencies. The source is the foundation database, opened
read-only. The builder does not open installed plugins or rewrite typed catalogs.

Default output: **`A:\Cache\OpenMWFoundation\world\world.sqlite`**.
The staged database and journals also live in that output directory on A:.
It contains all three profiles by default, with shared definitions and placement
revisions stored once. SQLite is the local query format; this is not a database
to upload wholesale into the app or a replacement for the site's D1/R2 choices.

```powershell
python build_world_catalog.py --profile vanilla
python build_world_catalog.py --profile tr --profile tr_arce
python build_world_catalog.py --output A:\Cache\WorldPreview
```

A profile selection replaces the entire output with that selection. Use a different
output directory when keeping multiple builds. Inputs can be changed using `--database`.

## Data tables

| Table | Purpose and identity |
| --- | --- |
| metadata | World schema version, foundation snapshot ID, coverage, build time |
| profiles | Profile ID, world, version, ARCE flag |
| objects | Shared winning object revisions: version ID, record type, key, display name, plugin, script, model |
| profile_objects | Profile + record type + key → object revision and original plugin |
| actors | NPC/creature stats and relevant flags, linked by object revision |
| containers | Capacity, organic/respawn flags, linked by object revision |
| inventories | Holder revision + entry index → item/list key, original count, quantity, restocking |
| actor_spells | Actor revision + entry index → spell key |
| leveled_lists | Item/creature list revision, raw selection flags, chance-none |
| leveled_entries | List revision + entry index → item/actor/list key and minimum level |
| cells | Profile + cell key, name, interior/exterior, grid, region, inherited metadata |
| placements | Shared reference revision, reference ID, object key, cell, coordinates, ownership and instance details |
| profile_placements | Profile + reference ID → winning placement revision and original plugin |
| warnings | Grouped unresolved targets and invalid inventory/list target types per profile |

Definitions are not placements. An NPC may have several placements or none; its
inventory is stored once regardless. A leveled-list entry remains one link even
if the list is used in thousands of chests. Duplicated list entries preserve
distinct entry indices. There is **no recursive expansion, probability calculation,
or generated acquisition route** in this builder.

Every lookup must use a profile. For example, to find placements of a container,
join `profile_placements` to `placements`, then match `object_key`. To find its
inventory, resolve `profile_objects` for that profile and `record_type='CONT'`, then
join its `version_id` to `inventories.holder_version_id`. Do not join the unfiltered
objects table by name alone: that would mix revisions from different profiles.

The `version_id` values and `record_id` in this world database refer to the source
foundation snapshot. Only combine with typed catalogs whose `snapshotId` matches.
Object keys are casefolded editor IDs. Reference keys retain the foundation's
plugin-and-reference-number identity. Locations point to object IDs without
copying the item's stats or enchantment into each placement.

## Decoded details

Version 1.1.0 includes `BODY` definitions in `objects` and `profile_objects`, with
their model paths. These are model parts, not equippable armor items; consumers
must filter by record type. Typed item catalogs remain unchanged. Rebuild with
`python build_world_catalog.py` to replace the older world catalog.

`unresolved_inventory`, `unresolved_leveled_entry`, and `unresolved_placement`
mean the target is absent from the profile's supported world definitions.
`invalid_inventory_target` and `invalid_leveled_entry_target` mean a world target
exists but has an inappropriate record type. Details include the holder/list
type and target types. Inventories and item lists accept item categories or
`LEVI`; creature lists accept `CREA`, `NPC_`, or `LEVC`. Version 1.1.1 corrects
the previous rule that incorrectly flagged NPC targets in creature lists.
These are type checks, not a
claim that every valid target is obtainable. Original links remain untouched.
In particular, `random_imp_armor` pointing to the `BODY` ID `imperial cuirass`
is preserved and flagged; it is not rewritten to `imperial cuirass_armor`.

Actor `details` is a JSON object containing attributes, skills or creature combat
stats, health/magicka/fatigue, level, gold, and raw flags. Autocalculated NPC layouts
have null derived stats, not fabricated zeros. AI hello/fight/flee/alarm values and
the raw service flags are included when stored; absent AI data is null. These are
inputs to a later danger/service analyzer, not assertions of hostility or sales.

NPC `recordReferences` keys are RNAM=race, CNAM=class, ANAM=faction, BNAM=head,
KNAM=hair. Creature CNAM is its original creature reference. Actor spells are links
to the typed Spells catalog. Script references remain links to the foundation.

Container `capacity` is stored CNDT. `organic` and `respawns` are flags, not a
simulation of when a particular container refills. Negative inventory counts are
preserved in `count_raw`, with `quantity=abs(count_raw)` and `restocking=true`.
Count zero is retained. Leveled entries with 100% chance-none are retained as data;
the acquisition analyzer should account for them later.

Placements include XYZ coordinates, raw count, owner and faction. Their JSON
`details` stores rotation (radians), scale, ownership global, faction rank, lock,
key, trap, soul, enchantment charge, and item condition/charge fields. Sentinel
values are preserved. Door destination cell names and position/rotation are
decoded, but door links are not yet converted into a travel graph. No `steal`,
`safe`, `sold`, or `earlyGame` verdict is invented.

Cell optional metadata is replayed in profile load order. Explicit water, region,
ambient, and map-color fields are retained through later revisions that omit them,
with `fieldSources` identifying the revision supplying each optional field. This
is transparent source-field inheritance, not a simulation of every engine cell
default. Deleted cell rows are retained with `deleted=1`; their placements are
excluded. Missing exterior cells targeted by references receive `synthetic=1`
metadata rows. Missing interior targets cause an error. Moved references use the
destination indexed by the foundation; regular cell siblings remain intact.

## Memory, progress, and publication

The builder streams definitions and profile mappings into SQLite. Placement payloads
are decoded in source-record order, loading a CELL BLOB once per unique source
revision. It never accumulates millions of nested Python location objects. Configured
SQLite caches total roughly 48 MiB; individual records and other Python/SQLite
structures add memory. SQLite auxiliary temp structures use RAM, while the large
output tables and rollback journals stay on the output drive.

Progress messages show each profile/phase, row counts, and elapsed time every few
seconds. Final join and integrity checks also print activity messages. Millions of
profile-placement mappings are expected; they are small links, not expanded paths.

A build lock prevents concurrent publication. The database is written to a staged
file, checked for foreign-key/decoding consistency and SQLite integrity, then
atomically replaces `world.sqlite`. Keep enough free disk space for the previous
database plus its replacement during rebuilds. Close database viewers before
replacement on Windows. Ctrl+C normally removes staging and preserves the old
published file; a forced kill can leave a `.world-*` directory and `build.lock`.
Verify no build is running before manually removing stale files.

## Inspect results

```powershell
python inspect_world_catalog.py --profile tr
python inspect_world_catalog.py --profile tr --item katana_goldbrand_unique
python inspect_world_catalog.py --profile vanilla --cell "interior:balmora, guild of mages" --limit 20
```

The item inspector lists direct placements, inventory definitions, and leveled-list
memberships separately. A container definition is not a confirmed location until
joined to its placements. Each result category is limited by `--limit`; it does not
claim exhaustive acquisition coverage or recursively expand nested lists.

## Scope and verification

Included: cells, world object identities, all live placements, typed actors and
containers, inventories, actor spell links, and item/creature leveled lists.
Not yet included: NPC transport destinations, AI movement packages, resolved
merchant service logic, quest/script conditions, travel graph, level/probability
analysis, danger judgments, or acquisition paths. Original data remains in the
foundation for these later tools. Cyclic list links are preserved rather than
traversed. Missing object targets are grouped in `warnings`; review these gaps.

```powershell
python -m unittest test_world_catalog -v
```

Tests cover normalized sharing, profile isolation, movement/deletion, optional cell
inheritance, NPC stat layouts, creature stats, ownership/door details, unresolved
targets, and preservation of previous output on failure. Real-data read-only checks
covered 80,349 TR+ARCE object definitions, 10,784 cell headers, and 23,189 sampled
placement payloads. The full world database build is left for your local run.

Layout references: OpenMW `components/esm3/loadnpc.cpp`, `loadcrea.hpp`,
`loadcont.hpp`, `loadlevlist.hpp`, and `cellref.cpp`.
