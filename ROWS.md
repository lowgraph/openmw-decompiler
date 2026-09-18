# Gear rows

Run in this project's VS Code terminal, after the catalogs and the world, acquisition
and services databases exist:

```powershell
python build_gear_rows.py --profile vanilla
```

A row answers "what should a level 1 character wear here" for one equipment slot
under one setting of the site's three toggles. Rows are **derived, never authored**:
candidates come from the catalogs, verdicts from the policy layer, and nothing here
decides what is obtainable. Change a rule in [policy/early-game.json](policy/early-game.json)
and rebuild; no re-extraction is involved.

Output goes to `A:\Cache\OpenMWFoundation\gear-rows\<profile>-<hash>.json`.
See `gear-rows-types.ts` for the app contract.

## The rows

| Category | Split by | Count |
| --- | --- | --- |
| `armor` | slot × armour class | 10 × 3 = 30 |
| `shield` | armour class | 3 |
| `weapon` | skill × handedness | 10 |
| `clothing` | slot | 10 |

53 definitions × 8 toggle combinations = **424 rows per profile**. Every combination
is emitted even when empty, so the site can index straight into it rather than
searching. Arrows and bolts are ammunition, not a slot, and get no row.

Armour class is computed the way the engine does it: the piece's weight against its
slot's threshold GMST, `light` at or under `fLightMaxMod`, `medium` at or under
`fMedMaxMod`, `heavy` above. Bracers borrow `iGauntletWeight`, as in OpenMW's
`Armor::getEquipmentSkill`.

Rows rank on `strength`: armour rating for armour and shields, the best of chop,
slash and thrust for weapons, enchantment capacity for clothing. The number is
published on every pick so the site can re-rank on its own objective.

## Primary and the "or" row

> Each row starts with the closest source in or around Seyda Neen, Pelagiad, Balmora,
> Caldera, Ald'ruhn, Vivec, Suran, Ebonheart or Old Ebonheart, even if it costs more;
> an "or" row adds a stronger piece from farther away.

`primary` is the strongest eligible piece with a near-start route, falling back to the
best far one when nothing is close. `alternative` is the strongest far piece, and is
published **only** when the primary was near and the far piece is strictly stronger —
an equal piece farther away earns no row. Ties on strength go to the cheaper piece.

Measured on the vanilla profile, every row fills with all three toggles off except
the ones vanilla genuinely lacks nearby, and 18 carry an "or". Requiring near-start
empties medium gauntlets and the light right bracer: vanilla's only medium gauntlets
are Bear Gauntlets in Skaal Village, on Solstheim. That is the rule working, not a gap. Turning theft and endgame on moves the "or" rows to the Mournhold Museum of
Artifacts, which is what the site already says that toggle does.

## Toggles

Every row carries the `toggles` it was built for. The combinations are independent
of the routes, so the builder walks each item's acquisition graph once and evaluates
all eight against it through a shared cache — the reason a full profile takes minutes
rather than hours.

```
vanilla: 1,605 items -> 424 rows, 414 filled, 254 KB, 196s
```

## Options and verification

```powershell
python build_gear_rows.py --profile tr
python build_gear_rows.py --profile vanilla --category weapon --category shield
python build_gear_rows.py --profile vanilla --limit 60 --output A:\Cache\RowsPreview
python -m unittest test_gear_rows -v
```

`--limit` takes the first N records per category for a smoke run; it truncates in
catalog order, so its picks are not representative. `--max-placements` (default 1500)
bounds each item's search: a row built from truncated evidence still carries
`evidenceTruncated` on the pick, because a capped search can miss a better source.
`--category` builds a subset. Publication is a staged write followed by an atomic
rename, and the filename is content-addressed, so an identical build overwrites itself
and a changed one lands beside the old.

Tests cover armour-class thresholds and their boundaries, bracers borrowing the
gauntlet threshold, strength per record type, row keys including shields and excluded
ammunition, the eight toggle sets, variant isolation, row counts per category, and
primary/alternative selection.

## What this layer does not do

Script grants are not consulted, so a quest reward is never a row: the builder passes
no events, and `obtainable` never reaches `script_conditional` here. It does not
compare across slots, build a full loadout, or weigh armour against enchantment
capacity — one row is one slot. It does not model a character: no race, class, skills
or armour-skill scaling enter the ranking, so `strength` is the item's own number.
