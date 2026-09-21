# Late-game loadouts

Run in this project's VS Code terminal, after the acquisition and script-evidence
databases exist:

```powershell
python build_loadout_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\loadouts\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Loadouts` catalog. See `loadout-types.ts`
for the app contract.

## What it answers

For each of the site's premade builds, and each equipment slot: which items that
**already carry a constant effect** best serve that build. Candidates are items that
exist in the game. Enchantment capacity and custom enchanting are out of scope by
decision, which is what makes this a ranking rather than a packing problem.

```
vanilla    61 builds   141 candidates   107 placed,  19 quest,  15 unconfirmed   25 KB gzipped
tr         61 builds   644 candidates   388 placed, 129 quest, 127 unconfirmed   62 KB gzipped
tr_arce   103 builds   644 candidates                                            76 KB gzipped
```

Builds come from `lib/premade-data.mjs` in the site repository — 41 archetypes, 20 race
builds and 42 ARCE builds. A build applies to a profile only when its race exists there
and is playable, which is how the ARCE builds stay out of vanilla without a special
case. The payload carries a digest of the definitions, so a catalog built against an
older set of builds can be spotted.

## Scoring is mostly derived, not authored

The two commonest constant effects are `Fortify Skill` (270 items) and
`Fortify Attribute` (256), and both name *which* skill or attribute. The build already
says which skills are major and minor and which attributes are favoured, so how much a
Battlemage values `Fortify Destruction` falls out of its own definition rather than a
taste table. Armour rating works the same way, weighted by the build's skill in that
armour class.

The Helm of Oreyn Bearclaw shows the effect. Almar's guide calls it the best helm for
Heavy Armor users, and the scoring agrees without being told:

```
Redguard Lady Spellsword [Battlemage, Heavy Armor minor]   19.5
a build with no armour skill at all                        12.0
```

What *is* authored is the ~45 effects with no skill or attribute to key on — Reflect,
Sanctuary, Resist Magicka, Levitate. Those came from guide and forum sentiment, and
each entry in `policy/late-game.json` is marked `research` where the tier came from
that and `placed` where it did not, so the two are never confused.

**Both directions are checked.** Every constant effect on a candidate must be covered
by the policy, or an unmapped effect would silently score zero; and every effect the
policy names must appear on a candidate somewhere. As with the near-start places, the
bar is *somewhere*, not everywhere — 36 of the 71 exist only on Tamriel Rebuilt items
and are rightly absent from vanilla.

## Drawbacks are never subtracted

Half the best items in the game are cursed, so netting a penalty against a benefit
would bury exactly the items players actually want. Instead a drawback either removes
an item for this build, or rides along as a warning:

```
Darksun Shield   Drain Magicka 100, Reflect 20, Restore Fatigue 10, Night Eye 10
   Battlemage   no shield at all -- Drain Magicka disqualifies it for a caster
   Pure melee   ranked first, at 16.5
```

That is one item giving two honest answers. The Boots of Blinding Speed are the same
shape: Blind 100 alongside Fortify Speed 200, published as `Blind 100 (cancelled by
Resist Magicka)` rather than scored down, because the community rates them near
essential for anyone who can resist the blind.

### Magnitude escalates, but only on what the build runs on

A drain of 5 and a drain of 255 are not the same drawback, and the first version of
this scored them identically. Neb-Crescen drains Willpower *and* Intelligence by 255
and was being recommended to a Battlemage with a polite warning attached.

The fix is not a blanket magnitude threshold. The Mantle of Woe drains Personality by
100 and is still a caster's item — and Personality *governs* the Illusion that both
Conjurer builds carry, so "governs one of my skills" is the wrong test. What matters is
what the archetype actually runs on: casters on Intelligence and Willpower, fighters on
Strength and Agility, everyone on Endurance. Only those escalate to disqualifying when
the drain zeroes them.

```
Battlemage weapon   Neb-Crescen disqualified -> Sunder 22.2 ['Drain Fatigue 1']
Conjurer robe       Mantle of Woe 14.0 ['Drain Personality 100', 'Weakness to Normal Weapons 20']
```

## Obtainability, and the one toggle

Every candidate is classified by how it can actually be had:

- **placed** — something in the world holds it, with the highest actor level on the
  easiest route recorded.
- **quest** — a script hands it to the player. Only player-directed `inventory_add`
  counts; a script arming an NPC is not a way for you to get one. Ebony Mail reaches
  the player through `shrineassarnibibi`, the Boethiah shrine.
- **unconfirmed** — neither, so it is never ranked. In TR that is 127 items: bound
  armour that spells summon rather than items you own, Tamriel_Data assets defined for
  content that does not place them yet, and items inside NPCs who are themselves placed
  nowhere. Anger sits in `tr_dead_warrior_01`, an NPC with zero placements.

**Questing is always assumed**, so a scripted grant counts and no toggle governs it.

The single toggle is `allowFormidableSources`, default **off**: it drops items whose
easiest route means facing or robbing an actor above level 30, unless a quest hands
them over anyway. This began as "a toggle for the Royal Signet Ring", whose only route
is taking it off King Helseth at level 35 — but the ring is the *fifth* hardest of the
forty best candidates, behind Philosopher's Armor at level 52, so keying on one item
would have hidden it while recommending worse offenders. It changes the top pick in
**413 slots** across the ARCE profile:

```
Altmer Atronach Spellweaver  ring   Royal Signet Ring -> Aesliip's Ring
Breton Apprentice Nuker      boots  Boots of Peace    -> Honor's March
```

## Beast races, per subrace

Beast races cannot equip anything covering the head or a foot, and the flag is per
race record, not per name. All eight Khajiit races share the display name "Khajiit",
and they disagree: Cathay-raht and Dagi-raht are beast, Ohmes and Suthay are not. Races
are resolved by key through the same label map the site uses in
`lib/character-catalogs.mjs`, and a build whose race label resolves to two records is
skipped rather than guessed at.

Beast builds still get helmets — the open ones. A Khajiit Nightblade is offered the
Witchhunter's Mastery Crown and the Helm of Oreyn Bearclaw, both of which dress the
hair rather than the head.

## Options and verification

```powershell
python build_loadout_catalog.py --profile tr
python build_loadout_catalog.py --builds builds.json
python build_app_bundle.py --no-loadouts
python -m unittest test_loadout_catalog -v
```

Tests cover the policy guards, coverage in both directions, trait derivation from a
build's own definition, saturation, caster- and fighter-only effects, armour and weapon
weighting, every drawback rule, the Darksun Shield split, magnitude escalation on
critical attributes only, eligibility including beast filtering and the formidable
toggle, ranking order, deduplication, and build-name uniqueness.

## What this layer does not do

It does not model enchantment capacity, so it cannot tell you what you could *make* —
only what already exists. It does not pair slots: two-handed weapons and shields are
ranked independently and the site must not equip both. It does not compute effective
armour rating, which needs a character's actual skill values; armour is weighted by
skill *tier* instead. Scores are comparable within one slot for one build and nowhere
else.
