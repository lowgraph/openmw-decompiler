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
**147 tests** on synthetic fixtures; none touch the user's real data.

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

The app contract is in `catalog-types.ts`, `bundle-types.ts`, `policy-types.ts` and
`gear-rows-types.ts`. Keep them in step with the builders.

### Numbers worth knowing

```
placements, tr profile        2,215,031      STAT alone is 60.6% of them
profile_placements rows       4,787,754      tr and tr_arce are identical
app bundle, gzipped           vanilla 253 KB   tr 965 KB   tr_arce +13 KB
gear rows                     424 per profile, vanilla 414 filled, 196s
journal topics                tr 2,577  vanilla 758      326 have no resolvable title
transport destinations        tr 433  vanilla 117        17k directed door links
script events resolved        38,692 of 38,697 in tr
```

## What the last session added

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

**1. Finish the profile builds.** The user runs these.

```powershell
python build_gear_rows.py --profile tr
python build_gear_rows.py --profile tr_arce
python build_app_bundle.py
```

TR is roughly 7,000 items, so 15–20 minutes. ARCE changes only races and classes, so
`tr_arce` rows should be identical to `tr` — confirm that rather than assuming it, and
if it holds, publish them as a delta the way the bundle does.

**2. Wire the bundle into the site.** The calculators currently hold vanilla and TR
data as literal arrays inside `index.html`, combined ad hoc per tool. Replace them with
the profile-resolved bundle, and replace display-name references with stable keys,
keeping names as labels. A compatibility adapter must translate existing saved names,
because saved characters and share links are already in the wild.

**3. The rules library the calculators need.** `CATALOGS.md` is explicit that
engine-fixed targeting, no-magnitude and no-duration effect rules, harmful-effect flags
and display units are **not** synthesized. Alchemy, enchanting and spellmaking cannot
be accurate without them. This is the largest remaining gap for features 3 and 4.

**4. Travel.** `services.sqlite` already has providers, destinations, costs and directed
door links. The site's existing calculator optimizes for fewest connections; keep that
as a baseline objective and add cheapest and character-aware routing beside it, not
instead of it.

**5. Journal titles.** 326 journal topics resolve no title, about 10% of them. Feature 9
needs display names. Decide between a fallback to first-stage text and hand-authored
names, and record the decision as authored content.

**6. The user-data schema in D1.** Only `saved_characters` exists, with a 16 KB
`character_json` cap. Journal completion per character, equipped loadouts, known spells
and saved challenges will not fit in that blob. Decide blob-versus-rows now, keep the
Clerk-owned-identity and revision discipline that `cloudflare/README.md` sets out, and
put the content `snapshotId` on every row that stores a game reference.

**7. Save import.** Target OpenMW `.omwsave` first; the user's corpus is format v37 and
heavily modded. It is a separate binary format with its own version drift, and it
produces *observations* to reconcile against a planned build — not character records.

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
