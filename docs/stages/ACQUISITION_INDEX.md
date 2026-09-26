# Item acquisition evidence index

Run locally in VS Code after the world catalogue:

```powershell
python build_acquisition_index.py
python inspect_acquisition_index.py
python inspect_acquisition_index.py --item katana_goldbrand_unique
```

Input: `A:\Cache\OpenMWFoundation\world\world.sqlite`, schema 1.1.1.
Output: **`A:\Cache\OpenMWFoundation\acquisition\acquisition.sqlite`**.
No new dependencies beyond Python 3.10+. This builder is verified with synthetic
fixtures; the real-data build is left to you. It does not run the old location
exporter, expand paths, or copy the placement table.

## What the index supplies

The index answers which static definitions contain a target item, directly or
through lists, and where those definitions are placed. It preserves profile
overrides, duplicate list entries, negative/restocking inventory counts, stored
level thresholds, chance-none and list flags. Creature lists can lead to NPCs
or creatures whose inventories contain an item. Cycles are safe to query.

| Table | Contents |
| --- | --- |
| metadata, profiles | Source snapshot, exact world build metadata, profile definitions |
| nodes | Shared item/container/actor/list revisions, names, scripts, provenance and holder/list details |
| profile_nodes | Profile-specific definition winners and original plugins |
| edges | Inventory or leveled-list memberships, once per parent revision and entry index |
| profile_edges | Target resolution per profile and indexed reverse lookup |
| warnings | Grouped missing, ambiguous or invalid-type targets |

An edge runs **parent → contained target**. Queries traverse it in reverse, starting
at the requested item. The query returns the connected evidence graph; it does
not enumerate every path through it. Definitions are visited once, and duplicate
source entries retain separate edge indices. Node `depth` is the shortest number
of reverse membership steps discovered, not distance or danger.

Items are world definitions in the twelve item record categories. The world
catalogue includes noncarryable lights; match against the typed inventory catalog
before offering equipment/inventory choices in the app. BODY parts, scenery and
doors are not acquisition nodes. Wrong-type targets remain unresolved edges and
warnings rather than fabricated item sources.

## Querying and limits

```powershell
python inspect_acquisition_index.py --profile vanilla --item katana_goldbrand_unique
python inspect_acquisition_index.py --profile tr --item iron_dagger --max-placements 300
```

The JSON response contains `nodes`, `edges`, and `placements`, plus `truncated`
and `limitReasons`. Each placement identifies its graph node, world revision,
reference ID, cell, position, raw count, owner/faction, and original instance
details including locks, keys and traps. `directItemPlacement` distinguishes the
root item's placement from a holder/list placement.

Default caps are 2,000 nodes, 5,000 edges, 12 membership steps, and 100 placements.
Use `--max-nodes`, `--max-edges`, `--max-depth`, and `--max-placements` to adjust
them. CLI ceilings are 10,000 nodes, 50,000 edges, 100 steps and 10,000 placements.
Depth zero checks direct placements only and flags deeper evidence when present.
No result with `truncated=true` should be presented as a complete location list.
Even an untruncated query covers only this static graph, not script-created items.

Definition queries can use `--type WEAP` (or another record type) when IDs are
ambiguous. IDs are case-insensitive. The inspector writes JSON to stdout; it does
not create large per-item files automatically. The normal summary shows grouped
warnings, such as the known `imperial cuirass` BODY reference in an item list.

## Interpretation limits

An inventory edge is evidence of stored membership, not proof that an item can
be stolen, purchased, looted or safely obtained. Ownership is raw evidence, not
a theft verdict. Actor stats, container respawn flags and restocking counts are
preserved without simulating runtime behavior. Level thresholds and chance-none
are not converted into probabilities or a single required player level.

This stage does not evaluate scripts, quest rewards, merchant-owned containers,
equipped stock, dialogue access, or conditional spawns. Providers can be joined
through their actor revision to the services catalogue, but that does not establish
sale status. The next acquisition-rule layer will need those distinctions before
applying your theft toggle, 500-gold spending limit, faction-access assumption,
or Mentor's Ring danger benchmark. None is inferred here.

## Rebuilds and source consistency

The world database remains required for item queries. Its snapshot, schema and
build timestamp must match the index; rebuild this index after rebuilding world.
The saved world path is used by default. If you move an unchanged world database,
pass `--world-database PATH` to the inspector.

Builder options: `--world-database PATH`, `--output DIRECTORY`, repeated
`--profile vanilla`, `--profile tr`, `--profile tr_arce`. All profiles are built
by default. A selected-profile build replaces the whole output; use another
directory if retaining separate versions.

The world database is opened read-only. Output is staged and validated beside
the destination on A: before atomic replacement. Normal cancellation/failure
preserves the previous index. After a forced kill, verify no build is running
before removing a stale `build.lock` or `.acquisition-*` staging directory.

Synthetic tests:

```powershell
$env:TEMP = 'A:\Cache'
$env:TMP = 'A:\Cache'
python -B -m unittest test_acquisition_index
```
