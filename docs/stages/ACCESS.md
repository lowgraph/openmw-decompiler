# Access

Run in this project's VS Code terminal, after the services catalog exists:

```powershell
python build_access_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\access\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Access` catalog. See `access-types.ts` for
the app contract and a reference `onLand`.

## What it answers

Two questions routing to any place needs, which no other catalog answers:

- **The way into every interior.** Each record holds `depth`, the number of doors between
  the room and the outside; `via`, the next room towards the outside; and `exits`, up to
  four points outdoors where the nearest way out opens. Follow `via` to depth 0 and read
  the list backwards for the way in.
- **Where land is.** `land` maps every exterior cell with land to 16 hex digits: an 8 x 8
  mask of 1,024-unit blocks, bit `by x 8 + bx` set where any of the block's height
  vertices stands above the water line. A cell missing from `land` is sea.

```
vanilla   1,227 of 1,339 interiors reach the outside   112 sealed   1,105 land cells   30 KB gzipped
tr        5,729 of 5,974                                245 sealed   3,936 land cells  127 KB gzipped
deepest   4 doors, in both
tr_arce   identical to tr, so the bundle inherits it
```

Checked on the real data: Arkngthand's Heaven's Gallery goes out through Weepingbell Hall
and the Hall of Centrifuge; the Vivec Guild of Mages goes out through the Foreign
Quarter plaza; Bamz-Amschend is sealed, reached from Mournhold by script.

## Why a mask and not a path

OpenMW builds its navigation mesh from collision shapes only while the game runs, so a
real walking path cannot be computed here. What can be is whether a straight line
between two points stays out of the sea. The site samples every 256 units along a walk
and refuses one that crosses more than 2,048 units of water, so a river, a canal or a
narrow strait is crossed and open sea is not. Hills, cliffs and the Ghostfence are not
known; a walk is labelled as a straight line.

A block counts as land when any of its vertices is above water, so a shoreline, a canal
or a bridge's footing does not cut a walk in two.

## Heights

Transcribed from `ESM::Land::loadData` (`components/esm3/loadland.cpp`, OpenMW 0.51.0):
a float offset, then 65 x 65 signed byte deltas, accumulated down the first column and
then along each row, scaled by 8. A cell without height data is at the default
-2,048, under water.

## Walking speed

Published as `walking`, from `Npc::getWalkSpeed` and `Npc::getRunSpeed`: walk speed is
`fMinWalkSpeed + 0.01 x Speed x (fMaxWalkSpeed - fMinWalkSpeed)`, reduced by
encumbrance; run speed multiplies it by `0.01 x Athletics x fAthleticsRunBonus +
fBaseRunMultiplier`. Game time runs 30 times faster than real time, so a Speed 40,
Athletics 30 character carrying nothing runs a cell in about 14 in-game minutes.

## Options and verification

```powershell
python build_access_catalog.py --profile tr
python build_app_bundle.py --no-access
python -m unittest test_access_catalog -v
```

Tests cover the height accumulation, the water line itself being water, a vertex on a
block border counting for both blocks, the bit order, depth and `via` through a tomb, the
shorter chain winning, a sealed loop, a room entered one way only, exits merged within
256 units and capped at four, deleted and sea cells left out of `land`, and profiles
with no land or no interiors refused.

## What this layer does not do

It does not find a path over the terrain, does not know which doors are locked, and
assumes a door works both ways, as nearly all do. Scripted teleports (Mournhold, the
Propylon chambers) are not doors and are not here.
