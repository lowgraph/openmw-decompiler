# Factions

Run in this project's VS Code terminal, after the world catalog exists:

```powershell
python build_faction_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\factions\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Factions` catalog. See `faction-types.ts`
for the app contract, with `joinableFactions` and a reference `meetsRank`.

## Why it exists

47 factions own placements in Tamriel Rebuilt and 14 in vanilla, and none of them
resolved to anything. The policy layer already asks whether an item is faction-owned
and answers with one `assumeFactionAccess` boolean; this is what lets it say *which*
faction, and what joining it costs.

```
vanilla    27 factions    23 joinable   3 hidden    14 own placements     3.8 KB gzipped
tr        103 factions    99 joinable   5 hidden    47 own placements    13.1 KB gzipped
```

The biggest landlords are the Great Houses. In TR, Hlaalu alone owns 9,746 placements.

## The requirements are in the record

Each faction's FADT subrecord is 240 bytes: two favoured attributes, ten ranks of five
numbers, seven faction skills, and a flags word
(`components/esm3/loadfact.hpp`). The five numbers per rank are what the game checks
when it decides whether you may be promoted.

```
Mages Guild — intelligence, willpower
  skills: alchemy, mysticism, illusion, alteration, destruction, enchant
  0. Associate    attrs 30/30   skills  0/0    rep  0
  1. Apprentice   attrs 30/30   skills 10/0    rep  5
  ...
  4. Conjurer     attrs 30/30   skills 40/10   rep 30
```

One faction skill must reach `primarySkill` and two more must reach `favouredSkill`;
both favoured attributes must reach their thresholds. `meetsRank` in the contract
applies exactly that, and returns null for a rank the faction does not have.

**This grounds the fast travel toggle.** TRAVEL.md gates the long-distance guild guide
network behind the Mages Guild rank of Conjurer, which until now was an authored string
with nothing behind it. Conjurer is rank 4, and the catalog says what it costs — with a
real difference between profiles: **vanilla asks for reputation 30, Tamriel Rebuilt for
70.**

## Ten slots, not ten ranks

Every FACT record reserves ten rank slots whether or not it uses them. An unnamed slot
is padding, so only named ranks are published and `ranks: []` means the faction cannot
be joined at all. In vanilla that is Sixth House, Skaal, Talos Cult and the Hands of
Almalexia — they exist, NPCs belong to them, and no player ever will.

The same applies to the seven skill slots: unused ones hold -1 and are dropped rather
than published as a number that means nothing.

## The build refuses a faction it cannot explain

If a placement is owned by a faction with no FACT record, the world and the foundation
were built from different extractions, and the build says so instead of publishing a
catalog that cannot answer for its own data:

```
2 faction(s) own placements but have no FACT record in tr: ghost guild, ...
  The world and the foundation disagree; rebuild both.
```

## Options and verification

```powershell
python build_faction_catalog.py --profile tr
python build_app_bundle.py --no-factions
python -m unittest test_faction_catalog -v
```

Tests cover the name and named ranks, unnamed slots being padding, a faction with no
ranks being unjoinable, attribute and skill indices resolving, unused skill slots being
dropped, a rank keeping all five of its numbers, the hidden flag, reactions pairing each
name with the number that follows it, a record with no FADT and one of the wrong size
both being refused, an unused index resolving to nothing, owned placements being
counted, a faction owning nothing reporting zero, an owner with no record failing the
build, and the payload counts.

## What this layer does not do

It does not know your standing in a faction, who can admit you, or which quests a rank
gates — those live in dialogue and scripts, which this layer does not evaluate. The
requirements here are the numeric ones the record carries; the game also refuses
promotion for reasons it keeps elsewhere, such as membership of a rival house. And
`reactions` describes how factions regard each other, not how any of them regard you.
