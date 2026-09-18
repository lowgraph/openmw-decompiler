# Acquisition policy layer

Run in this project's VS Code terminal:

```powershell
python query_item_sources.py --item ring_mentor_unique --profile vanilla --policy
```

`--policy` with no path uses [policy/early-game.json](policy/early-game.json). Without
it, `assessment` stays null exactly as before: **evidence never implies a verdict on
its own.** No database is rebuilt, and no new one is written.

This layer is authored judgement, not extracted fact. It is versioned by
`policyVersion`, independently of any extraction `snapshotId`, so changing a rule
costs one re-evaluation and never a re-extraction.

## The rules, and where the numbers come from

| Rule | Stated as | Number |
| --- | --- | --- |
| Danger | "no harder than the Mentor's Ring" | measured from the benchmark cell |
| Spending | at most 500 gold per item | authored, against condition-scaled worth |
| Broken gear | counts, flagged `needsRepair` | authored |
| Theft | a toggle, off by default | authored |
| Faction access | assumed, so faction-owned is not theft | authored |
| Source | guaranteed only; restocking merchants count | authored |
| Hostility | an actor attacks on sight at `ai.fight` 70+ | authored threshold, checked against the data |

The danger benchmark is a **cell reference, not a number**. The policy names
Samarys Ancestral Tomb at character level 1, and the evaluator measures that
encounter to derive the budget. Measured on the current vanilla profile:

```
in_tomb_all_lev-2  x1  ->  worst qualifying candidate: bonewalker  level 4, 60 hp
in_tomb_all_lev+0  x1  ->  worst qualifying candidate: ancestor_ghost  level 1, 23 hp
in_tomb_all_lev+2  x3  ->  no entry qualifies at level 1, so nothing spawns
                            budget: 2 hostiles, level <= 4, 83 total health
```

Three of the tomb's five leveled spawns contribute nothing at level 1, which is why
the encounter is the two enemies it is remembered as. Because the budget is measured
rather than typed in, it recalibrates by itself when the game data changes. Set
`earlyGame.danger.limits` to override with explicit numbers; the verdict then reports
`source: "authored"` instead of `source: "benchmark"` and carries no measurement.

## How a route is judged

The reverse containment graph is walked from the item up to every holder, and each
holder's world placements become routes. A route's quality is the best path that
reaches it — `direct`, `inventory`, `restocking`, or `random`. **`random` is
absorbing:** one leveled hop anywhere below makes the whole path a chance, however
guaranteed the rest of it is.

Each route is then checked against the policy, and fails with stated reasons:

- **Carried items are guarded by their holder.** An item inside an actor needs that
  actor pickpocketed or killed, so the holder counts as an obstacle and is added to
  the cell's danger — even at `ai.fight` 30, standing there peacefully. Without this,
  a Daedric Dai-katana in an archmaster's inventory reads as a free pickup in an
  empty room.
- **Ownership means theft** unless the holder sells that category of item, or the
  only claim is a faction's and faction access is assumed.
- **A merchant that stocks the item's service bit is a purchase**, whether it holds
  the item or owns it where it lies. Shop stock is owned by its merchant, so an owner
  that sells the category is a vendor, not a victim. Set
  `vendorOwnedPlacementsArePurchasable` to false to treat it as theft instead.
- **Worn gear is priced pro rata.** Weapons, armour and tools carry a condition on
  each placement, and worth scales with what is left of it. A Glass Dagger at 2 of
  300 condition is worth 27 gold, not 4000 — which is the whole reason worn shop
  stock is an early-game route at all. 1,697 of vanilla's 2,552 equipment placements
  carry an explicit condition, and 40 cross the 500 gold line once it is applied.
- **A fully worn item is a route, not protection.** Condition 0 is free and
  repairable, so it counts, and the route is flagged `needsRepair` — an optimizer
  must repair it before treating it as armour. Set `allowBrokenItems` to false to
  refuse them instead. TR places these liberally: 6 of the Adamantium Helm's 17
  routes are condition 0, including a free unowned one in Narsis Measurehall.
- **Danger** is the cell's worst-case hostile population at the policy's character
  level, plus any holder, compared against the budget on all three dimensions.

## Verdicts are refusable

`earlyGameEligible` is `true`, `false`, or **`null` when the evidence was truncated**
and no eligible route was found. A capped search can prove a positive — one good
route is enough — but it can never prove a negative. `obtainable` becomes `unknown`
rather than `none` under the same condition. Raise `--max-placements` for a decisive
answer; popular items have thousands of placements.

Script grants are counted and reported, and produce `obtainable: "script_conditional"`
when nothing static exists, but they never make a route eligible: lexical evidence
that a script mentions `AddItem` is not proof that it runs.

## Options and verification

```powershell
python query_item_sources.py --item "glass dagger" --profile vanilla --policy --max-placements 8000
python query_item_sources.py --item ring_mentor_unique --policy A:\my-policies\permissive.json
python -m unittest test_policy -v
```

`--services-database` and `--catalogs` override the inputs the policy needs; both
default to the configured output root, with catalogs resolved through `current.json`.
Prices require a catalog release, and are reported as `null` when none is available
rather than guessed. `price` is the cheapest purchase route whether or not it passes
the policy: the market price is a fact, eligibility is the verdict. Old Ebonheart's
worn Adamantium Helm reports `price: 2222` and stays ineligible under the 500 cap.

Tests use synthetic worlds built in memory: level gating, worst-candidate selection,
benchmark derivation and override, route quality and leveled absorption, carried
items, theft and faction toggles, condition scaling and clamping, worn shop stock,
broken items, vendor ownership, price caps, script-only items, and truncation.

## What this layer does not do

It does not simulate merchant markup, disposition, or Mercantile: `price` is the
catalog value scaled by condition, and a barter calculator is separate work. A cheap
item worn nearly to nothing can round to a price of 0, which is what it is worth.
It does not model combat, character builds, or travel distance, so "danger" is population and level,
not a fight simulation. It does not rank items or choose a best in slot — that is
the optimizer's job, and it consumes these verdicts rather than replacing them.
It writes nothing: verdicts are computed per query.
