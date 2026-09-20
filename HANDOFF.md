# Handoff

You are picking up the game-data pipeline for **Silt Strider**, a Morrowind build
planner and challenge-run generator. This document is the whole picture: what the app
needs, what exists, what was learned the hard way, and what to do next.

A second agent owns the site in parallel: read [COORDINATION.md](COORDINATION.md)
for the ownership split and the additive-only contract rule.

Read [README.md](README.md) for the run order, then the doc for whatever stage you
touch. `AGENTS.md` holds the local workflow rules and they are not optional: **the
user runs full real-data extractions themselves in VS Code.** Build the code, verify
with synthetic fixtures, hand over commands.

## Two repositories

| | Path | What |
| --- | --- | --- |
| Site | `A:\Claude\morrowind-tools` | The app. Next.js 16 / React 19, Tailwind, Clerk auth, a Cloudflare Worker and D1 |
| Pipeline | this repo | Extraction, catalogs, policy, rows. Pushed to `lowgraph/openmw-decompiler` (private) |
| Artifacts | `A:\Cache\OpenMWFoundation` | ~3.6 GB of SQLite. Never committed, always rebuildable |

The site moved from a single static `index.html` to Next.js 16 with a Cloudflare
export, and now consumes the app bundle through `lib/bundle-loader.mjs`. The legacy
markup is still extracted into the React shell during the transition, and the
calculators have not been rewired to the loader yet. That work belongs to the site
agent; see [COORDINATION.md](COORDINATION.md).

## What the app does

1. Challenge-run generator
2. Character build maker, with premade optimized builds and best-in-slot picks for
   early and late game
3. Enchanting and spellmaking calculators, with gold price per merchant
4. Alchemy calculator, filterable by effect or ingredient, with a toggle that shows
   only ingredients sharing an effect with the first
5. Fast travel calculator
6. One global Vanilla / Tamriel Rebuilt toggle across every tool, plus ARCE
7. Persistent accounts (Clerk), saved characters and challenges
8. Persistent characters that can filter and equip any equipment or spell in the game
9. A journal marking every quest, with completion tracked per character
10. Reading OpenMW save files to update the current character

Profiles are fixed and explicit: `vanilla` (Morrowind, Tribunal, Bloodmoon), `tr`
(plus Tamriel_Data, Cyr_Main, TR_Mainland, TR_Factions, the Firemoth patch, Sky_Main)
and `tr_arce` (TR plus ARCE). ARCE is a toggle available only when TR is selected.

## The storage split — the load-bearing decision

Three kinds of data with opposite requirements. Do not let them merge.

| | Changes when | Same for everyone | Belongs in |
| --- | --- | --- | --- |
| Game content | a plugin version ships | yes | R2 / static, content-addressed |
| User data | every click | no | **D1** |
| Authored content | you decide | yes | this repo, versioned separately |

The SQLite databases under `A:\Cache` are **local tooling storage**, not a shipping
format and not a browser download. Only the app bundle ships. Never put the placement
graph in D1: it is identical for every user, it is billed per row read, and the
calculators want to scan thousands of records per keystroke.

Authored content — the policy, premade builds, challenge objectives, curated tips —
is versioned independently of any extraction `snapshotId`, so changing a rule costs a
re-evaluation and never a re-extraction. Keep it that way.

## What exists

Every stage is built and tested. `python -m unittest discover -p "test_*.py"` runs
**233 tests** on synthetic fixtures; none touch the user's real data.

| Stage | Builder | Doc | Output |
| --- | --- | --- | --- |
| Archive and profile resolution | `extract_foundation.py` | FOUNDATION.md | `game-data.sqlite`, 1.3 GB |
| Typed catalogs | `build_catalogs.py` | CATALOGS.md | 21 catalogs + `BookText` per profile |
| World | `build_world_catalog.py` | WORLD_CATALOG.md | `world.sqlite`, 1.9 GB |
| Services and travel | `build_services_catalog.py` | SERVICES_CATALOG.md | `services.sqlite` |
| Quests, dialogue, scripts | `build_journal_catalog.py` | JOURNAL_CATALOG.md | `journal.sqlite` |
| Acquisition graph | `build_acquisition_index.py` | ACQUISITION_INDEX.md | `acquisition.sqlite` |
| Script evidence | `build_script_evidence.py` | SCRIPT_EVIDENCE.md | `script-evidence.sqlite` |
| Item sources | `query_item_sources.py` | ITEM_SOURCES.md | JSON per item |
| **Policy verdicts** | `evaluate_policy.py` | POLICY.md | fills `assessment` |
| **App bundle** | `build_app_bundle.py` | BUNDLE.md | what the browser downloads |
| **Gear rows** | `build_gear_rows.py` | ROWS.md | 424 rows per profile |
| **Engine effect dump** | `dump_profiles.py` | openmw_effect_dump/README.md | `effect-flags/<profile>.json` |
| **Effect rules** | `build_rules_library.py` | RULES.md | 141 vanilla / 186 TR rules |
| **Fast travel** | `build_travel_catalog.py` | TRAVEL.md | 115 vanilla / 427 TR edges |
| **Journal quests** | `build_quest_catalog.py` | QUESTS.md | 754 vanilla / 2573 TR topics |
| **Merchants** | `build_merchant_catalog.py` | MERCHANTS.md | 660 vanilla / 2575 TR providers |

The app contract is in `catalog-types.ts`, `bundle-types.ts`, `policy-types.ts`,
`gear-rows-types.ts`, `rules-types.ts`, `travel-types.ts`, `quest-types.ts` and
`merchant-types.ts`. Keep them in step with the builders.

### Numbers worth knowing

```
placements, tr profile        2,215,031      STAT alone is 60.6% of them
profile_placements rows       4,787,754      tr and tr_arce are identical
app bundle, gzipped           vanilla 271 KB   tr 988 KB   tr_arce +13 KB
gear rows                     424 per profile, vanilla 414 filled, 196s
effect rules                  vanilla 141   tr and tr_arce 186   45 are Lua-only
travel edges                  vanilla 115   tr and tr_arce 427   23 guild guides in tr
journal quests                vanilla 530   tr and tr_arce 1905 trackable of 2573
merchants                     vanilla 382   tr and tr_arce 1530 traders; 20% autocalc
engine dump                   141 effects in 6s, 186 in 4s, one run per profile
journal topics                tr 2,577  vanilla 758      326 have no resolvable title
transport destinations        tr 433  vanilla 117        17k directed door links
script events resolved        38,692 of 38,697 in tr
```

## Where things stand, 18 September 2026

Bundle `05c8e35f088e181ca115d94c` is built, verified through the site's own loader and
staged into `morrowind-tools/public/game-data`. Both repositories are clean and pushed
except for Antigravity's own files. Next steps 1 and 3 below are done; 2 is underway.

## What the last two sessions added

**The rules library and the engine dump.** `build_rules_library.py` derives the
per-effect behaviour the plugin files omit, and `dump_profiles.py` reads the engine's
real answers by launching OpenMW once per profile. 549 inferences confirmed, 1
corrected, 14 newly decided. See RULES.md, which is the most useful single document in
this repository for understanding what is evidence and what is fact.

**45 effects that exist in no file.** Tamriel Rebuilt registers them through Lua, 39 of
them available for spellmaking and enchanting. They reach the catalogs only through a
runtime dump, carry `extracted: false` and a null `effectId`, and are keyed by the
engine's own string id. **Key effect rules by `key`, never by `effectId`.**

**A third agent.** Antigravity now leads UI architecture and authors
`UI_TRANSFORMATION.md`; Codex implements it in `morrowind-tools`. See COORDINATION.md,
which must stay identical in both repositories.

**Packaging.** Catalog schema 1.1.0 moves book prose into its own `BookText` catalog;
`build_app_bundle.py` publishes the browser bundle, excluding prose and expressing
ARCE as a record-level delta over TR. It also strips prose from a 1.0.0 release, so
the current catalogs do not need rebuilding first. Three full profile copies went from
about 11 MB gzipped to 1.20 MB.

**The policy layer.** `assessment` used to be five nulls. It now carries obtainability,
theft, sale status, price and early-game eligibility, with a per-route trace of the
reasons. `--policy` is opt-in; without it the assessment stays null, because evidence
must not imply a verdict on its own.

**Gear rows.** One row per slot per toggle set: 10 armour slots × 3 classes, 3 shield
classes, 10 weapon rows by skill and handedness, 10 clothing slots, times 8 toggle
combinations.

**Git.** The repo had no commits. It now has a full history and a private GitHub
remote at `lowgraph/openmw-decompiler`.

## Rules that cost real debugging

Do not regress these. Each one was a wrong answer first.

- **Carried items are guarded by their holder.** An item in an actor's inventory needs
  that actor pickpocketed or killed. Bolvyn Venim's `ai.fight` is 30, so his room reads
  as empty and his placement has no owner — a Daedric Dai-katana looked like a free
  pickup. The holder joins the danger budget regardless of temperament.
- **Worn gear is priced pro rata.** `value × condition ÷ maximum`. A Glass Dagger at 2
  of 300 condition is worth 27 gold, not 4,000. 1,697 of vanilla's 2,552 equipment
  placements carry an explicit condition. Without this, every worn bargain fails the
  gold cap.
- **Shop stock is owned by its vendor.** Check the *placement's owner* against the
  service flags, not only the holder. Four of the five worn Glass Daggers belong to
  weapon merchants; reading the owner as a victim made them all theft.
- **A capped search cannot prove a negative.** `earlyGameEligible` is `null` and
  `obtainable` is `unknown` when evidence was truncated and nothing eligible was found.
  One good route still proves a positive.
- **Exclude developer cells by exact key, never by pattern.** `Nchuleftingth, Test of
  Pattern` and `Atestas' Pawn & Loan` are real places. A substring match on "test"
  deletes them silently.
- **Benchmarks are measured, not typed.** The danger budget comes from reading Samarys
  Ancestral Tomb at level 1: two hostiles, level at most 4, 83 total health. Three of
  its five leveled spawns have no qualifying entry at level 1, which is why it is the
  two-enemy fight it is remembered as. Hardcoding the numbers would drift.
- **Use the `CROSS JOIN` join-order idiom** against `world.sqlite`. Letting SQLite
  choose took a 400-route query 45 seconds; forcing the index order took it to 0.46.
- **Toggles do not change routes, only which pass.** Walk each acquisition graph once
  and evaluate every toggle combination against it through a shared cache.

## Next steps

**1. ~~Finish the profile builds.~~ Done.** All three gear row sets and all three rule
sets are built, and ARCE's are byte-identical to TR's — checked record by record, not
assumed — so the bundle inherits rather than duplicating them.

**2. Wire the bundle into the site.** *Underway, Codex's.* The loader, the profile-aware
character catalogs and a React character planner have landed. What remains: the legacy
alchemy, enchanting and spellmaking calculators still hold vanilla and TR data as
literal arrays inside `index.html`. Replace those with the profile-resolved bundle, and
replace display-name references with stable keys, keeping names as labels. A
compatibility adapter must translate existing saved names, because saved characters and
share links are already in the wild.

**3. ~~The rules library the calculators need.~~ Done.** Shipped as the `EffectRules`
catalog. Targeting, no-magnitude, no-duration and harmful are now engine facts rather
than inferences, and `costFormula` carries the engine literals the spell cost step
needs. Display units remain absent, deliberately: they are not in the effect record at
all, OpenMW decides them in its own interface, so nothing claims them. A calculator
that needs them has to author them.

**3a. Build the spellmaking and enchanting calculators on it.** The rules are the input
those features were blocked on, and nothing consumes them yet. `effectCost` in
`rules-types.ts` is a reference implementation of the spell cost step, not a full
calculator. Whatever consumes it must key by `key`, or it silently drops the 39
Lua-registered effects the game itself offers.

**4. ~~Travel.~~ Shipped as the `Travel` catalog.** The transport network, with
`mageGuildMember` and `conjurerRank` toggles. What remains is the *routing*, which is
the site's: the existing calculator optimizes for fewest connections; keep that as a
baseline objective and add cheapest and character-aware routing beside it, not instead
of it. Teleport doors are still unshipped by choice — 17,156 links, a separate graph,
a different question. See TRAVEL.md.

**5. ~~Journal titles.~~ Done, and the premise was wrong.** The 326 was the sum across
three profiles; per profile it is 82 and 122. Almost none are quests — a topic no entry
ever finishes is a journal note, and `trackable: false` now says so. Only 3 vanilla and
15 TR topics are completable *and* unnamed; three are authored in
`policy/journal-titles.json`, which clears vanilla, and the remaining 12 publish
`name: null` with the first entry as fallback rather than an invented title. Shipped as
the `Quests` catalog; see QUESTS.md.

**6. The user-data schema in D1.** *Partly built by Codex.* `cloud_saves`,
`saved_challenges`, `saved_loadouts` and `user_tiers` now exist, with parsed saves in a
packed SLT1 blob and a few queryable metadata columns beside it. **There is still no
journal table**: quest progress lives inside that blob, with only `quest_count` and
`topic_count` exposed, so "which of my characters finished this quest" cannot be asked.
The field requirements for that table are now written up in
[JOURNAL_PROGRESS.md](JOURNAL_PROGRESS.md), with the measurements behind them and a
proposal in Codex's own house style that has been executed against SQLite. Codex owns
the migration. The headline: every quest id in all 96 real saves resolves to the
`Quests` catalog, but 469 of 757 only after lowercasing, so case folding is mandatory
rather than tidy. Rows are small in practice — median 4 per save against a 2,577
ceiling — so the argument for rows is queryability, not size.

The original note, still true of the older table: only `saved_characters` existed, with
a 16 KB `character_json` cap. Journal completion per character, equipped loadouts, known spells
and saved challenges will not fit in that blob. Decide blob-versus-rows now, keep the
Clerk-owned-identity and revision discipline that `cloudflare/README.md` sets out, and
put the content `snapshotId` on every row that stores a game reference.

**7. ~~Save import.~~ Built by Codex, on the site side.** `lib/omwsave-parser.mjs` in
`morrowind-tools` reads `.omwsave` directly — ESM3 framing, version-gated to format 40.
Verified 20 September 2026 against the user's real corpus: **96 of 96 saves parsed, all
format 37**, yielding identity, vitals, skills and attributes, quests, journal ids,
factions, inventory and spells. It is not ours to build; do not start a second one.

It has one gap, and our data closes it. A save names the character's class but not what
that class *contains*, so the parser reports `skill.kind` as null rather than guessing
which skills were major:

```
Class "T_Glb_Jeweler" is defined in a content file, not in this save, so
major/minor/misc cannot be recovered; skill.kind is null.
```

95 of the 96 saves carry that warning, so it is the normal case, not an edge. **38 of
the 39 distinct classes in the corpus are in the `Classes` catalog we already ship** —
`T_Glb_Jeweler` included, with its five majors and five minors. Filling `kind` is a
lookup against the bundle, not new pipeline work. The one class the catalog cannot
supply is `$generated:3`, a player-made custom class, which the save does store and the
parser can recover itself.

The framing still holds: a save produces *observations* to reconcile against a planned
build, not character records.

**8. The objective toggle.** The user has foreseen "best protection" versus "best
constant effect". `strength` in a row is currently armour rating, best weapon damage,
or enchantment capacity, and every pick publishes the number, so the site can re-rank
today. A first-class objective belongs in the policy, not the row builder.

**Optional, only if disk matters:** filtering STAT placements out of `world.sqlite`
removes 1.49M of 2.2M rows with zero consumers — STAT appears in no acquisition graph
and no script attachment. It forces a rebuild of `acquisition` and `script-evidence`
too, because both pin `worldBuiltAtUnix`. The gates fail loudly, so there is no silent
corruption risk, only cost. `ACTI` and `LIGH` must **not** be filtered: 4,017 activators
and 273 lights are script-attachment anchors, and dropping them would empty
`contextPlacements` with no error.

## Conventions

- Preserve `vanilla`, `tr` and `tr_arce` separately, with source provenance.
- Generated data, staging files and test temporaries live under `A:\Cache`. Set `TEMP`
  and `TMP` there when running tests; use `python -B`.
- Every derivative database records the `snapshotId` it came from and refuses to mix
  revisions. Keep that. It is what makes a rebuild safe.
- Publication is staged then atomically renamed, and releases are content-addressed.
- Extracted fact and authored judgement stay in separate files with separate versions.
- Never commit game files, plugins or their assets. Only derived facts and code.
