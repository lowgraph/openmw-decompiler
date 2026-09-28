# Access

Run in this project's VS Code terminal, after the services catalog exists:

```powershell
python build_access_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\access\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Access` catalog. See `access-types.ts` for
the app contract and reference `onLand` and `squareAt`. The walkable grid's authored
choices are in `policy/walking.json`; barrier placements are read from `world.sqlite`.
About 30 seconds for all three profiles.

## What it answers

Three questions routing to any place needs, which no other catalog answers:

- **The way into every interior.** Each record holds `depth`, the number of doors between
  the room and the outside; `via`, the next room towards the outside; and `exits`, up to
  four points outdoors where the nearest way out opens. Follow `via` to depth 0 and read
  the list backwards for the way in.
- **Where land is.** `land` maps every exterior cell with land to 16 hex digits: an 8 x 8
  mask of 1,024-unit blocks, bit `by x 8 + bx` set where any of the block's height
  vertices stands above the water line. A cell missing from `land` is sea.
- **Where a walk can go** (schema 1.1.0). `walkable` grades every exterior cell into
  16 x 16 squares of 512 units: land, too steep or a wall, water near enough to land to
  swim, and open sea. The site searches it for walking paths.

```
vanilla   1,227 of 1,339 interiors reach the outside   112 sealed   1,105 land cells    63 KB gzipped
          193,802 land squares, 21,714 too steep or walled, 32,423 to swim
tr        5,729 of 5,974                                245 sealed   3,936 land cells   226 KB gzipped
          748,087 land squares, 72,216 too steep or walled, 89,745 to swim
deepest   4 doors, in both
tr_arce   identical to tr, so the bundle inherits it
Ghostfence  132 pieces joined in a ring, 479 squares, the Ghostgate's 2 portcullises open
```

Checked on the real data: Arkngthand's Heaven's Gallery goes out through Weepingbell Hall
and the Hall of Centrifuge; the Vivec Guild of Mages goes out through the Foreign
Quarter plaza; Bamz-Amschend is sealed, reached from Mournhold by script.

## The land mask

Releases before 1.1.0, and the site when a release has no grid, walk a straight line
checked against the mask: the site samples every 256 units along a walk and refuses one
that crosses more than 2,048 units of water, so a river, a canal or a narrow strait is
crossed and open sea is not.

A block counts as land when any of its vertices is above water, so a shoreline, a canal
or a bridge's footing does not cut a walk in two.

## The walkable grid

OpenMW builds its navigation mesh from collision shapes only while the game runs, so
the real mesh cannot be read here. The terrain can. OpenMW 0.51.0 lets an actor walk up
no slope steeper than 46 degrees (`Constants::sMaxSlope` in
`components/misc/constants.hpp`, read by `isWalkableSlope` in
`apps/openmw/mwphysics/stepper.cpp`). Terrain vertices are 128 units apart; each quad is
two triangles, and a triangle is too steep when its rise across both axes passes
tan(46°) x 128, about 132 units a vertex.

Each 512-unit square covers 4 x 4 quads, 32 triangles:

- **Land** when any of its vertices stands above the water line, as the mask reads it.
- **Too steep** when at least `steepShare` of its triangles are, 0.6 as shipped.
- **Swum** when it is water within `swimReach` squares of land, two as shipped, across
  cell borders.
- **Open sea** otherwise. A cell all open sea is left out.

`steepShare` was calibrated on fourteen walks known to work in vanilla and one known not
to; `policy/walking.json` records how. At 0.3 or 0.5 the Red Mountain citadels were cut
off from the Ghostgate; at 0.6 eleven of fourteen are within 1.5 times the straight
line, the rest being climbs up Red Mountain.

**Barriers** are walls the heights cannot show, named in `policy/walking.json` by object
id prefix. The Ghostfence's 132 fence and pylon placements are put in order by their
angle around the ring's middle and each is joined to the next by a line of blocked
squares. Squares within `openingRadius` of the Ghostgate's portcullises are made land
whatever the terrain says: the gate is a built passage. A barrier whose objects match no
placement in a profile it applies to fails the build, so a renamed object cannot open
the wall silently. The build prints how many pieces were joined and how many pairs lay
further apart than `maxGap`; a gap there is a hole in the wall worth a look.

The grid is published as `walkable.cells`: per cell, two bits a square, four squares a
byte with the first in the low bits, base64, squares west to east then south to north.

### What the grid does not see

Rocks, buildings, trees and bridges are meshes, not terrain. A path over the grid goes
around steep ground and open sea, not around a boulder, and a ridge the heights leave
open may be closed by rocks in the game; a bridge over deep water is not there.

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
Swimming, from `getSwimSpeedImpl` (`apps/openmw/mwclass/actor.hpp`), is the run speed
times `fSwimRunBase + 0.01 x Athletics x fSwimRunAthleticsMult`: about half as fast.

## Options and verification

```powershell
python build_access_catalog.py --profile tr
python build_app_bundle.py --no-access
python build_access_catalog.py --policy my-walking.json --output A:\Cache\walk-try
python -m unittest test_access_catalog -v
```

Tests cover the height accumulation, the water line itself being water, a vertex on a
block border counting for both blocks, the bit order, depth and `via` through a tomb, the
shorter chain winning, a sealed loop, a room entered one way only, exits merged within
256 units and capped at four, deleted and sea cells left out of `land`, and profiles
with no land or no interiors refused. For the grid: the 46 degree limit either side,
the steep share, square order, swimming across cell borders, walls and gates overriding
the terrain, the bit packing, the ring joined in order, a gap over `maxGap` counted, an
opening clearing its squares, placements found by prefix outdoors in the profile, a
barrier with no pieces refused, and malformed policies refused.

## What this layer does not do

It does not find paths itself (the site searches the grid), does not know which doors
are locked, and assumes a door works both ways, as nearly all do. Scripted teleports (Mournhold, the
Propylon chambers) are not doors and are not here.
