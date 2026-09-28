# Gear rows

Run in this project's VS Code terminal, after the catalogs and the world, acquisition
and services databases exist:

```powershell
python build_gear_rows.py
```

Every profile unless `--profile` names some, about twenty minutes each.

A row answers "what should a level 1 character wear here" for one equipment slot
under one setting of the site's three toggles. Rows are **derived, never authored**:
candidates come from the catalogs, verdicts from the policy layer, and nothing here
decides what is obtainable. Change a rule in [policy/early-game.json](../../policy/early-game.json)
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

## The objective a row answers

A row optimises for something, and "best" is not one question. You foresaw this as
*best protection* versus *best constant effect*, and they are genuinely different
items:

| Objective | Ranks on |
| --- | --- |
| `power` | armour rating on armour and shields, best damage on weapons, and on clothing its enchantment (below) |
| `enchantment` | room for your own enchantment, which decides what a constant effect can cost |

Every slot is answered once per objective, so the row count doubles to 848, and the key
gains a fifth segment: `armor/cuirass/heavy/000/power`. Both are authored in
`policy/early-game.json`, where HANDOFF said a first-class objective belongs, and the
builder refuses one it cannot measure:

```
Policy names objective(s) the row builder cannot measure: lightest
  Known objectives: enchantment, power
```

**It matters more than it might sound.** The two disagree on **94 of vanilla's 352
filled pairs and 148 of TR's 424** — better than one row in four, and more than one in
three once Tamriel Rebuilt's wider selection is in play:

```
armor/helmet/heavy    power Indoril Helmet (45ar)          -> enchantment Imperial Steel Helmet (250pts)
armor/cuirass/heavy   power Duke's Guard Silver Cuirass    -> enchantment Iron Cuirass (200pts)
armor/greaves/medium  power Orcish Greaves (30ar)          -> enchantment Imperial Chain Greaves (70pts)
```

The objective applies to the whole row, not just the primary: the "or" row is judged on
it, and so is `beastPrimary`. An alternative that is stronger on power but weaker on
capacity earns no "or" in the enchantment row.

### An enchantment already on a piece comes first

Ranking clothing on capacity recommended a blank Exquisite Ring over Mentor's Ring: 120
points of room against a ring that already fortifies Intelligence and Willpower by 10.
A level 1 character cannot afford to fill that room, so the room is not what they want.
Every pick now carries `enchanted`, the item's own enchantment with what making it would
cost in enchant points, the engine's sum from `Enchanting::getEnchantPoints`: per effect
`((min + max) x duration + area) x baseCost x fEffectCostMult x 0.05`, half again at
range, a constant effect lasting `fEnchantmentConstantDurationMult`. The records' own
cost is 0 on every constant effect, so it cannot be used. Mentor's Ring comes to 100.1,
on the same scale the game shows the Exquisite Ring's 120 of room.

The engine's hardcoded effect flags come from the rules library, because the plugins'
MGEF flags leave them out: a harmful effect on the wearer is a curse and counts against,
and a NoMagnitude or NoDuration effect is priced as magnitude 1 or duration 0 and shows
neither number. The builder refuses to run without a rules library for the profile.

### What an enchantment is worth, and what it is worth to you

`worth` is what the engine charges to make an enchantment, and on its own it overvalues
cheap utility effects: a constant Feather belt or Light ring costs as much as a real
bonus. Since policy 2026.09.27.2, `enchantmentUsefulness` in `policy/early-game.json`
puts every effect in a tier, and each pick's enchantment also carries `value`: each
effect's cost times its tier's weight, with the tier on each effect.

| Tier | Weight | For example |
| --- | --- | --- |
| essential | 1.0 | Fortify attributes and skills, Restore, Shields, Reflect, Resist Magicka, Levitate, Recall, strike damage |
| situational | 0.5 | elemental Resists, Cure, Dispel, Drain and Absorb on enemies, crowd control, summons |
| convenience | 0.2 | Feather, Light, Night Eye, Water Breathing, Swift Swim, SlowFall, Detect |
| none | 0 | Corprus, Vampirism, Sun Damage, Stunted Magicka |

A curse on the wearer still counts in full against, whatever its tier. An entry can name
one attribute or skill, as "Fortify Attribute: Personality", to override its effect for
that alone. The build refuses a name the profile's MagicEffects catalog does not have
before it spends twenty minutes, and prints every effect that fell to `defaultTier`, so
a new plugin's effects get placed rather than guessed. The table travels in the payload
under `policy.enchantmentUsefulness`, with `defaulted`.

Rows rank on `value` where it exists, and the site's `pickRank` does the same, falling
back to `worth` for rows built before the table.

| Objective | Clothing | Armour and weapons |
| --- | --- | --- |
| `power` | enchanted first, on value; then blank, on capacity; then cursed | strength; value settles a tie |
| `enchantment` | blank first, on capacity; enchanted after | the same |

Only a blank piece takes your own enchantment, since OpenMW's enchanting window lists
unenchanted items alone, so the enchantment objective puts every blank piece first.
On vanilla the power ring row now reads Mentor's Ring from Samarys, and the power amulet
row the Amulet of Mighty Blows, 15 gold in Caldera; the enchantment rows keep the
Exquisite Ring and Amulet at Milie Hastien's in Balmora.

### A shortlist, ranked again for each build

A row ranks the same way for every character, so it can only say what is best on
average. Tamriel Rebuilt has 172 eligible rings and its ring row picks Ring of Toxic
Cloud; Mentor's Ring, eligible and near a start, never reached the site, and a mage
could not be offered it however well the site knew the character.

So each clothing row answering `power` carries `candidates`: the pieces worth ranking
again for one build. It keeps what the row chose (primary, alternative, beastPrimary),
the blank piece with the most room, and for each effect the piece that carries the most
of it, keyed by effect, attribute or skill, and whether it is constant, so an always-on
Fortify Intelligence and one cast on use are different offers. Close and far sources are
shortlisted apart. Effects worth nothing and curses keep no piece. Past 40, the
carriers of the smallest effects go. Vanilla's 30 eligible rings shortlist to 16, about
11 KB per row, with Mentor's Ring on the list.

Each effect of an enchantment also carries its own `worth` and `value`, so the site can
weigh them for the character: `lib/build-traits.mjs` in the site takes the leveler's
archetype, counts a build as a caster when it trains magic (two points per casting school
among its majors, one among its minors, four or more), and weighs a Fortify Attribute
by the archetype's attribute queue, a Fortify Skill by major, minor or neither, magicka
effects by whether the build casts, and attack spells at half for a caster, who has
spells of their own. Armour and weapons carry no shortlist; their rows rank on
protection and damage, which do not depend on who wears them.

**It is free at build time.** The candidates and the policy verdicts are gathered once;
an objective only changes which of them wins. Vanilla took 188s for 848 rows against
184s for 424. Gzipped, the catalog goes from 14 to 24 KB on vanilla and 19 to 34 KB on
TR — the rows doubled and the payload did not, because the two objectives pick the same
item three times in four.

## The near-start places are checked now

`nearStart.places` is a list of authored strings matched as substrings of a cell key.
That worked, and was checked against nothing — so `ald'ruhn` sat in the policy matching
**no cell in any profile**, because the game writes `ald-ruhn`. The rule kept working
only because both spellings were listed. It has been corrected, and the build now
refuses a place that names nowhere:

```
1 near-start place(s) in the policy match no cell in any profile: "ald'ruhn"
  Check the spelling against the cell keys: the game writes ald-ruhn with a
  hyphen, not an apostrophe.
```

The bar is **somewhere, not everywhere**. Old Ebonheart is a Tamriel Rebuilt city and
correctly matches nothing in vanilla; a per-profile check would have failed an entry
doing its job. A place inert in the profile being built is reported rather than refused.

Worth knowing when reading a row: `ebonheart` as a substring also matches all 116 Old
Ebonheart cells, so it is not the fourteen you might expect. Harmless here, since both
are on the list.

## Toggles

Every row carries the `toggles` it was built for. The combinations are independent
of the routes, so the builder walks each item's acquisition graph once and evaluates
all eight against it through a shared cache — the reason a full profile takes minutes
rather than hours.

```
vanilla: 1,605 items -> 424 rows, 414 filled, 254 KB, 196s
```

## Ambush rows: the Dark Brotherhood

One source has no placement at all. Tribunal's `dbAttackScript` wakes a resting
character to a Dark Brotherhood assassin, and at levels 1 to 3 it places one
`db_assassin1b`, level 1, wearing the whole set: eight pieces of **light** armour at
30 each, twice a Wolf Helmet, for 100 to 1,000 gold of worth. The chance is 20% a
rest, 10% after the first attack and none after the second. No policy verdict can see
this: the assassin exists only once the script runs, so every route the evidence has
is a carried item on an actor with no cell.

The site offers it as its own toggle, so the policy authors it as an **ambush**:
`earlyGame.ambushes` names the toggle, the script and the actor, and which categories
to offer (armour only: the Silver Dagger is sold everywhere and the one Ebony Dart is
one throw). The builder then:

- checks that the profile's **winning** version of the script still says
  `PlaceAtPC "db_assassin1b"`, and prints why when it does not, so a mod that rewrites
  the attacks turns the rows off rather than leaving them wrong;
- finds each item that actor carries directly (not through a leveled list) in the
  item's own acquisition graph;
- emits a row for that slot with `toggles: {"darkBrotherhood": true}` and a key such as
  `armor/helmet/light/darkBrotherhood/power`, only where the actor wears something.

The pick is `acquisition: "ambush"`, `place: "Wherever you rest"`, no price and no
cell, `nearStart: true` because the assassin comes to you, and carries the policy's
`note`. The policy rows are untouched: an ambush row stands beside them, and the site
merges it into its slot only when that toggle is on. A site that matches only the
three policy toggles never selects one. All three profiles send the same assassin in
the same eight pieces.

## Options and verification

```powershell
python build_gear_rows.py --profile tr
python build_gear_rows.py --profile vanilla --category weapon --category shield --output A:\Cache\RowsPreview
python build_gear_rows.py --profile vanilla --limit 60 --output A:\Cache\RowsPreview
python -m unittest test_gear_rows -v
```

A partial run — `--limit` or `--category` — needs `--output`. It does not merge with
the last full rows, and the bundler takes the newest file per profile, so published
beside the real rows it would ship in their place. A smoke run once did exactly that;
the builder now refuses it.

`--limit` takes the first N records per category for a smoke run; it truncates in
catalog order, so its picks are not representative. `--max-placements` (default 1500)
bounds each item's search: a row built from truncated evidence still carries
`evidenceTruncated` on the pick, because a capped search can miss a better source.
`--category` builds a subset. Publication is a staged write followed by an atomic
rename, and the filename is content-addressed, so an identical build overwrites itself
and a changed one lands beside the old.

Objective tests cover each objective getting its own row, the two choosing
differently, a row naming the objective it answered, the "or" row being judged on the
same objective, the beast pick following it, one objective reproducing the old row
count, an unmeasurable objective being refused, the fallback when none are named, and
the shipped policy asking for both.

Beast-race tests cover a closed helm being refused and an open one allowed, both
feet, an ankle not counting as a foot, one forbidden part among several being enough,
an item with no body parts at all, the engine's own part numbers, and at row level: a
beast getting the best helm it can wear rather than the best helm, a row where nothing
fits saying so, an unrestricted row giving the same pick, and the near-first rule
applying to the beast pick too.

Ambush tests cover the winning script deciding, a prefix of the actor's id not
matching, only the named actor's own inventory counting, the pick taken from the body,
ambush rows standing apart and only where something is worn, and malformed entries
being refused.

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
