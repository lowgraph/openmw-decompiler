# Places

Run in this project's VS Code terminal, after the services catalog exists:

```powershell
python build_places_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\places\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Places` catalog. See `place-types.ts` for
the app contract, with `placeIndex`, `placeLabel`, `settlementOf` and `cellDistance`.

## Why it exists

Gear rows, merchants and travel all identify somewhere by `cellKey`. Until this
catalog, only Travel's own endpoints carried a name — 137 of them in TR — so every
other reference resolved to nothing. A gear row could say where the Chitin Helm is and
the site had no way to call it anywhere.

```
vanilla    2,887 places   1,328 inside   1,454 named    95 settlements   16 regions    32 KB gzipped
tr        10,784 places   5,983 inside   6,486 named   394 settlements   49 regions   130 KB gzipped
```

It publishes **every** cell, not just the referenced ones. Only 439 of vanilla's and
1,638 of TR's are named by another catalog today, and shipping just those would be
smaller — but it would make Places depend on the other builders' output, so adding a
catalog could silently break the join. A catalog that answers "what is this key" has
to answer for every key.

## A town is several cells

Exterior cells that share a name are one settlement. Port Telvannis is seven grid
squares; 74 of TR's 394 named exteriors span more than one. `settlements` groups them,
with the bounding box and its rounded middle — good enough to point at, and not a claim
about where the town centre is.

That is the question three other catalogs need: *which cells are Balmora*.
`policy/early-game.json` currently answers it by matching authored substrings against
cell keys, which works and is not checked against anything. This catalog is what would
let that be verified instead.

## Absent, not null

Most exterior cells are unnamed wilderness carrying only a region — 4,801 of them in
TR. Writing `"name": null, "grid": [...], "region": ...` for each costs more than every
other field in the catalog together, so absent fields are simply left out:

```json
{"key":"interior:aalmu ouradas' shack","interior":true,"name":"Aalmu Ouradas' Shack"}
{"key":"exterior:-1,-1","interior":false,"region":"west gash region","grid":[-1,-1]}
```

An absent `name` means the cell has none. An absent `region` means the record carries
none, which is normal for interiors. `synthetic: true` marks a cell the extraction
inferred from a reference rather than reading a CELL record.

## The join is checked at bundle time

`build_app_bundle.py` refuses to publish when any cell key named by Travel, Merchants
or GearRows is missing from Places:

```
tr: 3 cell(s) named by Merchants are not in Places: interior:nowhere ...
  One of the two was built from a different extraction; rebuild both.
```

Measured on the current release, that check passes completely — **0 unresolved out of
1,763 referenced cells in TR and 487 in vanilla**. So within one bundle the join is
total, and `placeLabel` never has to fall back to showing a raw key.

This is worth having because the failure is otherwise silent: a stale Places built from
an older extraction would leave a handful of locations nameless in the browser and
nothing would complain.

## Options and verification

```powershell
python build_places_catalog.py --profile tr
python build_app_bundle.py --no-places
python -m unittest test_places_catalog -v
```

Tests cover an interior's name and lack of grid, an exterior's grid, absent fields
being omitted rather than nulled, the synthetic flag, cells sharing a name becoming one
settlement with its bounds and middle, interiors and wilderness not being settlements,
region counting, the payload counts, key ordering for a stable hash, an empty profile
failing loudly, and the bundle's referential check against each of the three catalogs
that name cells.

## What this layer does not do

It does not know what is inside a cell, how to walk between cells, or where within a
cell anything stands. Interiors carry no position: an interior has none of its own, and
inferring one from its name would be a fiction, so `cellDistance` returns null rather
than a guess. Door links between cells are extracted but not shipped — see TRAVEL.md.
