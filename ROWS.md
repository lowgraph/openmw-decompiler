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

`build_app_bundle.py` picks these up automatically and publishes them as the `GearRows`
catalog, so the site reads rows through the same loader as everything else. Each row
carries a stable `key` — `category/slot-or-skill/armorClass/theft endgame nearStart`,
for example `armor/helmet/light/000` or `shield/-/heavy/111` — because the loader joins
records on it. Rebuild rows before bundling; the packager refuses a rows file from a
different snapshot, or one whose rows predate the key.

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

## Beast races get their own pick

Argonians and Khajiit cannot equip anything that covers the head or a foot.
`MWClass::Armor::canBeEquipped` and its Clothing twin refuse on `ESM::PRT_Head`,
`PRT_LFoot` or `PRT_RFoot`, with the engine's own comment: *"Beast races cannot equip
shoes / boots, or full helms (head part vs hair part)."* An open helm dresses
`PRT_Hair` instead, which is why some helmets pass and most do not.

The rule is **per item, not per slot**, so it has to be read off each record's body
part list rather than guessed from the type:

| | vanilla | Tamriel Rebuilt |
| --- | --- | --- |
| helmets a beast race cannot wear | 45 of 79 | 219 of 517 |
| boots | **37 of 37** | **224 of 224** |
| shoes | 25 of 25 | 86 of **87** |

The two outliers are worth naming, because each shows the check reading the record
rather than the type. Tamriel Rebuilt's **Rough Cloth Strips**, typed `shoes`, passes
because its body part list is *empty* — it dresses nothing, so there is no foot to
object to. And its **Pants of Missing Bits** fails, because the list references
`PRT_LFoot` and `PRT_LAnkle` with no mesh attached to either; the engine compares
`mPart` and never looks at whether a model is there. Neither is an exception to code
around. Both are why the check cannot be a table of slot names.

So every `Pick` carries `beastWearable`, and every row carries `beastPrimary` — the
same row answered from the same candidates by the same near-first rule. On vanilla:

```
vanilla   424 rows: 18 need a different item for a beast race, 32 where nothing fits
tr        424 rows: 22 need a different item for a beast race, 32 where nothing fits
nothing fits: boots and shoes, and only those, in both profiles
```

The picks are their own confirmation. Nothing here matches on names — the rule reads
`PRT_Head` against `PRT_Hair` in the body part list — yet it independently arrives at
what Bethesda and Tamriel Rebuilt wrote into the names:

```
Adamantium Helm     -> Orcish Open Helm
Ebony Closed Helm   -> Imperial Templar Helmet
Chitin Helm         -> Colovian Fur Helm
```

`beastPrimary: null` means **nothing in this slot fits them**, not that the row is
empty — `primary` is still there for everyone else. When the primary is already
wearable, `beastPrimary` repeats it, so a caller never has to work out which applies.

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

Beast-race tests cover a closed helm being refused and an open one allowed, both
feet, an ankle not counting as a foot, one forbidden part among several being enough,
an item with no body parts at all, the engine's own part numbers, and at row level: a
beast getting the best helm it can wear rather than the best helm, a row where nothing
fits saying so, an unrestricted row giving the same pick, and the near-first rule
applying to the beast pick too.

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
