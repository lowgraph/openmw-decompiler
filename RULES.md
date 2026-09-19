# Effect rules library

Run in this project's VS Code terminal, after a catalog release exists:

```powershell
python dump_profiles.py
python build_rules_library.py
```

The first launches OpenMW once per profile to read the engine's own effect table.
Nothing needs installing; skip it and the rules are inferred from content alone.
Output goes to `A:\Cache\OpenMWFoundation\rules\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `EffectRules` catalog. See `rules-types.ts`
for the app contract and a reference `effectCost`. This reads catalog JSON only; it
opens no database and runs no extractor.

## The problem it solves

A magic effect's behaviour is not in the plugin files. Measured across all 141 vanilla
effects, the MEDT flags field holds exactly two values:

```
1536 (0x600 = spellmaking | enchanting)   129 effects
   0 (neither)                             12 effects
```

Targeting, whether an effect has a magnitude, and whether it has a duration are
engine-side. That matters because the spell cost formula branches on the last two: a
`noMagnitude` effect is priced at magnitude 1 whatever the spell says, and a
`noDuration` effect at duration 0. Guess them and dozens of effects are mispriced.

## The engine's own table, when you have it

OpenMW publishes every one of these flags through `core.magic.effects.records`, and
documents them in your install at `resources/lua_api/openmw/core.lua`:

```
harmful   hasDuration   hasMagnitude   hasSkill   hasAttribute
onSelf    onTouch       onTarget       isAppliedOnce   casterLinked
nonRecastable   unreflectable   continuousVfx   negativeLight
```

[openmw_effect_dump](openmw_effect_dump/README.md) is a small mod that prints that
table to `openmw.log`; the Lua sandbox has no `io` and `openmw.vfs` is read-only, so
the log is the only way out. `dump_profiles.py` launches the game once per profile,
passing the mod folder as `--data` so nothing has to be installed, watches the log, and
closes the game as soon as the dump lands — around five seconds a profile.
`build_rules_library.py` picks the results up automatically.

That turns three things around. `harmful` becomes available, which content cannot
reveal at all. `onSelf`/`onTouch`/`onTarget` become definitive, where
`rangesObserved` can only ever prove a range allowed. And the inferences below get
**graded**: each carries `agreement` of `confirmed`, `corrected` or `decided`, with
the original inference kept in `inferred`, so the method is checked rather than
trusted. A range the content uses but the engine forbids is reported in
`rangesUnexplained`, because one of the two readings would then be wrong and silence
would hide it.

Without the dump nothing claims engine provenance: `source` is `derived`, `harmful`
and the targeting fields are null, and the rules are the inferences below.

The join is checked before anything merges. Every catalog effect must be in the dump,
so a stale dump, one from another game, or one whose key has drifted is refused outright
rather than rewriting the rules of whatever it happened to match:

```
The effect dump does not cover the catalogs: 141 of 141 effects are absent from it.
  Water Breathing, Swift Swim, Detect Animal, ...
```

That is not hypothetical. The first version of the dumper keyed on position in the
record list rather than on the engine's id, which shifted every effect by one; the
second joined on a numeric index the engine does not expose, which matched nothing at
all. Both produced plausible-looking output.

Effects join on **name**. OpenMW keys its own records by a string id the catalogs do
not carry, and two effects — Call Wolf and Call Bear — have ids that do not match their
names either, so name is the only key that covers all 141. A name the dump repeats
resolves to nothing rather than to one of the two arbitrarily: Tamriel Rebuilt ships two
Wabbajack effects and two Corruption effects with distinct ids. If a catalog effect
carries such a name the merge is refused, because there is no honest answer. Nothing is
lost when it does not — those records are published below, keyed by their own id, where
no join is involved.

## Effects that exist only in the engine

A dump also sees effects that no plugin defines. Tamriel Rebuilt registers 45 extra
effects through Lua, via `content=Tamriel_Data.omwscripts`, so a TR run reports 186
against the 141 in the data — `Tamriel_Data.esm` contributes no MGEF records at all.
39 of the 45 are available for spellmaking and enchanting, so a spell maker that lists
only extracted effects is missing entries the game itself offers.

They are published as ordinary rules, with `extracted: false` and a null `effectId`
because no plugin record exists to carry one. Their `key` is the engine's own string
id, such as `t_conjuration_devourer`. **Key rules by `key`, never by `effectId`.**
`derivation.engineOnly` counts them, and their flags are the engine's own facts with
empty evidence — there is no content to infer from, and none is claimed.

Because the engine's list depends on the load order, one dump describes one load order
and not the project. `dump_profiles.py` therefore runs the game once per profile, with
that profile's own plugins plus the Lua content that belongs with them, and writes
`<root>/effect-flags/<profile>.json`. `build_rules_library.py` reads each profile's own
file, falling back to a shared `effect-flags.json` for any profile without one. Merging
a single TR dump into vanilla would hand vanilla 45 effects it does not have.

### How the inferences actually fared

```
549 confirmed    1 corrected    14 previously unknown
```

The one correction is Corprus, where four uses all at duration 1 suggested no duration
and the engine disagrees — exactly the thin-evidence case the threshold was meant to
catch, sitting right on it.

Three effects report `rangesUnexplained`, and the cause is real rather than a bug.
Rally Humanoid, Absorb Attribute and Absorb Health are all forbidden on Self by the
engine, yet four records use them that way: the vanilla enchantments `magnus' wrath`
and `vampire's kiss_en`, and the Tamriel Rebuilt spells `tr_m1_telwarlock` and
`tr_m3_farascultbuff`. Absorbing from yourself does nothing, so these are authoring
mistakes the engine tolerates. The flag is informational and does not stop the merge.

## How the rules are derived

Bethesda and the Tamriel Rebuilt authors wrote every spell, enchantment and potion
against the real engine, so their usage is evidence. An effect with no magnitude is
written with magnitude exactly `(1, 1)` every single time; an effect with no duration
is written with duration exactly `1`. An effect that uses the field varies it.

Observations are pooled across every profile in the release, because **one
counter-example anywhere refutes a flag**. That is not a theoretical concern:

```
Restore Skill   vanilla   54 uses, every one at duration 1   -> looks like noDuration
                tr       110 uses, durations {1, 5}          -> it has a duration
```

All 1,065 vanilla spells agreed on the wrong answer. Tamriel Rebuilt's content settles
it. Lock, Open and Dispel go the other way — both profiles agree, so they are decided
with far more confidence than either alone.

An effect the content never exercises at least three times in any one profile reports
`null` rather than a guess. On the current release that is 7 of 141: Cure Corprus
Disease, Remove Curse, EXTRA SPELL, Stunted Magicka, Summon Fabricant, Call Bear and
Summon Bonewolf. **134 are decided**, and with a dump all 141 are.

`rangesObserved` proves a range is allowed. It does not prove an unobserved range is
forbidden, and the field is named for what it is. Potions contribute magnitude and
duration evidence but never range, because a potion is always drunk by its holder.

## What is authored rather than derived

`costFormula` carries the engine's own literals — the 0.5, 0.1, 0.05 and 1.5 of the
spell cost calculation, and the magnitude and duration an unused field is priced at.
These are constants in the engine, not game settings and not visible in content, so
they are authored and marked `source: "authored"`. It also names the game settings a
caller still needs, such as `fSpellMakingValueMult` and `iAlchemyMod`; their values
are already in the `GameSettings` catalog rather than duplicated here.

## Cost in the bundle

Measured on the current release, with the engine's flags merged:

```
vanilla   141 effects   118 KB raw   6.7 KB gzipped
tr        186 effects   145 KB raw   7.8 KB gzipped
tr_arce   186 effects   145 KB raw   7.8 KB gzipped
```

58 KB and 5 KB from content alone, before the flags and the extra records. ARCE
inherits TR's catalog unchanged.

Vanilla and TR now differ, which they did not before: TR's rules carry the 45 effects
it registers and vanilla's do not. The extracted 141 are identical across all three —
the engine's rules are the same everywhere, and TR adds no MGEF records — so the
difference is exactly the Lua-registered set.

## Options and verification

```powershell
python dump_profiles.py --dry-run
python dump_profiles.py --profile tr
python import_effect_flags.py --profile tr
python build_rules_library.py --no-flags
python build_rules_library.py --profile vanilla
python build_rules_library.py --catalogs A:\Cache\OpenMWFoundation\catalogs\<releaseId>
python build_app_bundle.py --no-rules
python -m unittest test_rules_library -v
```

Selecting fewer profiles narrows the evidence pool as well as the output, which can
turn a decided flag back into `null` or, worse, into a wrong answer — the Restore
Skill case is exactly that. Build all profiles unless you have a reason not to.

Tests cover a field fixed at its sentinel, a field that varies, a counter-example in
one profile refuting another, thin and absent evidence, skill and attribute targeting,
potions proving no range, pooling, keyed records, extracted fields surviving, the
authored formula, content addressing, a missing catalog failing loudly, and the merge:
engine facts replacing inferences, confirmed and corrected and newly decided labels,
an unexplained range surfacing, a dump that does not cover the catalogs being refused,
an unreadable flag schema being refused, an engine-only effect reaching the output, a
repeated name still reaching it by id, and each profile reading its own dump.

`test_dump_profiles.py` covers the content order and the replaced content list a
profile is launched with, finding the executable, when a log counts as this run's, the
game being closed once the dump lands, a game that exits without dumping, a timeout,
that the game is given a file rather than a pipe, that every profile needing Lua
content declares it, that the shipped `.omwscripts` point at scripts that exist, and
that nothing in the mod quits the game.

## What this layer does not do

It does not decide display units — whether a magnitude reads as points, a percentage,
levels or feet is engine-side and not inferable from content, so no field claims it.
It marks effects harmful only when the dump supplies it; harmful is not inferable
from content. It does not implement alchemy, enchanting or spellmaking: it supplies
the per-effect rules and the formula constants those calculators need, and
`effectCost` in `rules-types.ts` is a reference implementation of the spell cost step,
not a full calculator.
