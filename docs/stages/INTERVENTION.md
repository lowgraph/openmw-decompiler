# Intervention

Run in this project's VS Code terminal, after the services and world catalogs exist:

```powershell
python build_intervention_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\intervention\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Intervention` catalog. See
`intervention-types.ts` for the app contract and a reference `landing`.

## What it answers

Where Divine Intervention and Almsivi Intervention put you down, cast from any of the
places Places publishes. Divine goes to a `divinemarker`, usually at an Imperial fort,
and Almsivi to a `templemarker` at a Temple. Each record holds an index into
`markers.divine` and `markers.almsivi`, or null where the spell fails.

```
vanilla   2,900 places   divine 8 markers    almsivi 6 markers    18 KB gzipped
tr       10,773 places   divine 25 markers   almsivi 20 markers   71 KB gzipped
tr_arce  identical to tr, so the bundle inherits it
```

Checked against the game: from Seyda Neen, Divine lands at Pelagiad and Almsivi at
Vivec; from Balmora and its guild hall, Divine lands at Moonmoth Legion Fort and
Almsivi in Balmora; anywhere in Mournhold lands in Mournhold.

## "Closest" is not distance

Transcribed from OpenMW 0.51.0, `World::getClosestMarker` and
`World::getClosestMarkerFromExteriorPosition` in `apps/openmw/mwworld/worldimp.cpp`,
and published as `rule`:

- **Outdoors, only your cell counts.** The engine takes one marker per exterior cell,
  walking the cells in grid order. A marker in your own cell wins outright.
- **Then the smallest ring.** It keeps the markers on the smallest square ring of cells
  around you, which is not the nearest in a straight line: from (0, 0) a marker at
  (3, 3), 4.24 cells away, beats one at (4, 0), 4 cells away.
- **Ties go round the ring** from its south-west corner: east along the south edge,
  north up the east edge, west along the north edge, then south down the west edge.
- **Indoors, doors first.** It searches outward a cell at a time. A marker inside a
  reached cell wins (Mournhold's two are the only ones indoors), and otherwise the
  first door that opens outdoors decides, by the ring around where it puts you. Depth
  is counted in cells, not distance.
- **A sealed interior fails.** 34 vanilla and 167 TR places have no answer: developer
  test cells, and interiors no door leads out of.

Positions become cells by `floor(x / 8192)`, as `ESM::positionToExteriorCellLocation`
does, so a position just west of 0 is in cell -1.

## Ambiguous answers are flagged, not hidden

Indoors, the engine takes the first outcome in its own order: cells in
case-insensitive name order, doors in the order the cell lists them. The builder
reproduces that as closely as the data allows (door placements in extraction order)
and, when another cell or door at the same depth would land somewhere else, lists the
alternatives under `ambiguous`. Measured: 1 vanilla place, and 6 Divine and 14 Almsivi
TR places.

## Towns

Each marker carries its cell, name and `town`, decided by the travel policy's own town
rule (`towns` in `policy/travel.json`), so "Vivec, Temple" lands in Vivec and the router
can join a landing to the travel network. Forts keep their own names: Moonmoth Legion
Fort, Buckmoth Legion Fort, Wolverine Hall. Joining those to the town beside them is
walking's job.

## Options and verification

```powershell
python build_intervention_catalog.py --profile tr
python build_app_bundle.py --no-intervention
python -m unittest test_intervention_catalog -v
```

Tests cover the floor rounding, a marker in your own cell, the ring beating a straight
line, every edge of the tie-break walk, a second marker in a cell never counting, the
door search's depth order, an interior marker, a shallower exit beating a deeper
marker, a sealed loop of doors, two wings disagreeing being reported, two exits that
agree not being, a profile missing a marker kind, and the release pin.

## What this layer does not do

It does not know whether the character has the spell or a scroll; the site decides
that. It ignores disabled markers and anything a script moves at runtime.
