# Ingredient sources

Run in this project's VS Code terminal, after the acquisition index and the services
catalog exist:

```powershell
python build_ingredient_sources.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\ingredient-sources\<profile>-<hash>.json`,
and `build_app_bundle.py` publishes it as the `IngredientSources` catalog once all three
profiles exist. See `ingredient-source-types.ts` for the app contract.

```
vanilla    126 ingredients   shop 75   plant 44   creature 41   find 95   none 9   31 KB gzipped, 2 s
tr         first 100 of 921 in 8 s; tr_arce reuses tr (see below)
```

The nine without a source are quest and unique items, such as the Innocent Heart, the
Pinetear Emerald and two named guar hides.

## Why it exists

CALC-4's effect finder picks ingredients by what they do. The Merchants catalog says
who trades ingredients but not what they stock, so "where do I get it" had no answer.
This reads what actually holds each ingredient, and where.

## What counts

Each placement of anything that holds the ingredient, directly or through levelled
lists, becomes at most one kind of source:

| Kind | Rule |
|---|---|
| shops | A merchant whose services include Ingredients (`sells()`, as gear uses), with it in their own inventory, or in a container they own where they trade (`trade_spot`). Levelled shop stock counts only if it restocks, as for gear. |
| plants | An **organic container that grows back**. Ore deposits and food barrels are organic too and never refill, so they are not plants. |
| creatures | A creature carrying it directly, or by a list that gives nothing else or gives it at least 1 kill in 5, placed directly or as a levelled spawn point. Below that it is random loot: real drops run 23 to 60% (Spriggans' Heartwood 48%), random loot 1 to 6%. |
| finds | Lying loose, or in an unowned container that is not a plant, put there directly or by a list that can give nothing else (a deposit, a kwama egg sack). Grouped by what holds it. |

Left out, and counted in `derivation.leftOut`: anything owned by someone else (theft,
owner's decision of 30 September), anything only an NPC carries (pickpocket or kill),
random loot (a container's list of several things), and holding and test cells from
`policy/early-game.json`. Scripts and quest rewards are not sources; nothing judges
danger or price.

## Read once, built once

The gear rows ask the acquisition index about one item at a time (`query_item`), which
is right for a few hundred pieces of gear and slow for a thousand ingredients that share
the same barrels and NPCs: Bread alone made 8,400 queries and took 22 s in TR. `Evidence`
reads a profile's memberships once (TR: 164,000) and its placements in one pass (TR: 2.2
million), walks each ingredient's graph in memory the way `query_item` does, and hands
`classify` the same shape; a test checks the two agree on a synthetic world. Rankings
break ties by key, so the output does not depend on the order rows arrive in.

Each profile's inputs -- the definitions and placements it reads, its cells, its
acquisition edges, its merchants, the policy and this builder's version -- are hashed into
`derivation.inputsFingerprint`. A profile with the same fingerprint as one built in the
same run, or as another profile's newest published file, reuses its records and says
`reusedFrom`. TR + ARCE differs from TR only in 17 body parts, which nothing here reads,
so a full run builds TR once. A partial run (`--limit`) gets no fingerprint and must go
to a scratch `--output`: the bundler takes the newest file.

## Chances are the engine's

`draw_chance` is OpenMW's `getLevelledItem` (`apps/openmw/mwmechanics/levelledlist.cpp`,
0.51.0): chance-none first; then one entry, uniformly, from those at or below the level —
all of them with the all-levels flag, otherwise only those at the highest such level;
a nested list draws again. The flag is `0x02` on item lists and `0x01` on creature
lists (`components/esm3/loadlevlist.hpp`). The builder refuses another release until
someone compares the two (REBUILD.md, "After an OpenMW update").

Chances are for a level 1 character. Nearly every ingredient list has only level 1
entries, so that is the real chance; a list that gives nothing at level 1 is described
at the first level that does, as `fromLevel`. A creature's spawn points are counted, but
which creature a spawn point produces depends on level and is not computed.

## Where, compactly

Marshmerrow has 2,655 plants in vanilla, so placements are tallied rather than listed:
by region, by starting town (in it or one square away, from `nearStart.places`, longest
match first so Old Ebonheart is not Ebonheart), and by interior cell, the six largest.
Shops keep the sixteen nearest a starting town, then restocking, then most stock;
`shopCount` says how many there are.

Synthetic tests: `test_ingredient_sources.py` (the draw, town matching, the release pin,
and a small world through the real world and index builders).
