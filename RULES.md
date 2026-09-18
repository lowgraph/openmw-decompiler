# Effect rules library

Run in this project's VS Code terminal, after a catalog release exists:

```powershell
python build_rules_library.py
```

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
the log is the only way out. `import_effect_flags.py` reads it back, and
`build_rules_library.py` picks the result up automatically.

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
Summon Bonewolf. **134 are decided.**

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

58 KB raw per profile, **5 KB gzipped**, and nothing for ARCE, which inherits the
catalog unchanged. The records are identical across profiles because the engine's
rules are; only the extracted fields could differ, and on the current release they
do not.

## Options and verification

```powershell
python import_effect_flags.py
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
an unexplained range surfacing, an effect absent from the dump falling back, and an
unreadable flag schema being refused.

## What this layer does not do

It does not decide display units — whether a magnitude reads as points, a percentage,
levels or feet is engine-side and not inferable from content, so no field claims it.
It marks effects harmful only when the dump supplies it; harmful is not inferable
from content. It does not implement alchemy, enchanting or spellmaking: it supplies
the per-effect rules and the formula constants those calculators need, and
`effectCost` in `rules-types.ts` is a reference implementation of the spell cost step,
not a full calculator.
