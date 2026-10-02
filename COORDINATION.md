# Coordination

## Main release and recovery handoff — 2 October

Owner-authorized `672c0d3` is live as Worker `56a07cb7-4daf-4e8c-8348-9da01b18cbdc`
at 100% traffic since 2026-10-02 23:46:37 UTC (20:46 in São Paulo). This publishes
QA-31/32, QA-33–39 and the ten beginner-clarity/follow-up items below.
Selected code rollback: `73df6e58-912e-48db-9786-5866ce793efd` / `250b1b5`.
Fresh D1 bookmark captured before deployment:
`00000074-00000000-000050f8-6b7a252ad77140777ca900210cc70b77` (23:42:41 UTC).
Keep bundle `a29adea046e6086c2c7ee654`, migrations 0001–0007, existing bindings,
secrets, API-only Worker routing and configuration. No data/schema changes or
migrations ran; a code rollback switches only the Worker version. Recovery and
release evidence: site LAUNCH_VERIFICATION §§67–68. F-12's ID-only preset labels
remain deferred; the physical touchscreen-laptop check remains for freeze.
First command: `node node_modules/wrangler/bin/wrangler.js deployments list --json`.

## Beginner clarity and contained follow-ups — 2 October

Integrated into site main from `polish/beginner-clarity-batch` (`133b7ef`) and
pipeline master from docs-only `handoff/beginner-clarity-batch` (`a601a8a`).
Ten ordered item commits cover beginner
help, premade collection counts, reverse Alchemy limits, open beast helmets,
required profile usernames, version/rename limits, copy, FLOW-04/03 and F-12.
Help uses loaded catalog facts and current choices; preserve calculations,
character/world precedence, custom edits, source provenance and original saves.
Reverse pairs remain two ingredients; same-page world changes clear the recipe,
not typed calculator stats. The 120-character Vault name limit matches the API.
Travel chamber links wait for ready catalogs and remain selected while save
indices load; unavailable chambers give No Route. Propylon edges and eligibility
are unchanged: Rotheran has no direct Andasreth connection; Master Index uses
Caldera. Journal joins enforce the existing exclusion groups, while leaving and
imported conflicting memberships remain editable. Vault cards use API `cell`
before legacy `cell_name`; missing locations are Not recorded. Actual class names
remain intact; ID-only preset class lookup is explicitly deferred after launch.
No dataset/schema, bundle, migration, extraction or production changes.
Site LAUNCH_VERIFICATION §65 records item checks and full merge preparation:
1,270 site tests, 685 pipeline tests, Cloudflare build (24 pages) and 1,440
complete Chrome case executions pass. Keep the expected-404 report separate;
a physical touchscreen-laptop check remains for freeze acceptance. Disposable
local data is cleared. Both shared documents are identical across repositories.
First command: `npm run test:browser:plan`, then full BROWSER_TESTS coverage,
including the new local Worker `npm run test:vault -- --clarity` mode.
The owner authorized merging and pushing both handoffs, then the release recorded above.

## Ordered launch polish (QA-33–39) — 2 October

Integrated into site main from `fix/qa-33-39`. Gear Advisor derives its initial
hand setup from the ranked weapon (Spear/Marksman two-handed) until a player
explicitly chooses. Preserve
that choice through edits/restores, lazy catalog loading, beast eligibility,
published unchanged-premade picks and equip transfer. Kit copy describes the
current character's attributes/skills; a premade source is never its archetype.
Alchemy pagination stays outside the scroll viewport with a visible gap. Home
identity labels and loadout actions stay whole; Specialization wraps at spaces.
TransitMap uses actual panel width, contained tracked region labels and readable
text; routing/positions are unchanged. Health loss formats its signed number,
so zero has no minus; precise curves remain. Faction details use singular rank.
No exported dataset/schema, bundle, migration, extraction or release changes.
Seven ordered fixes: 1,221 site and 685 pipeline tests, Cloudflare build (24 pages)
and 1,272 complete Chrome case executions pass. LAUNCH_VERIFICATION §63 records
the expected-404 exemption and physical touchscreen-laptop check still required.
COORDINATION and UI_TRANSFORMATION remain identical in both repositories.
First command: `npm run test:browser:plan`, then the full suites in BROWSER_TESTS.
Owner authorized merging and pushing site main and the pipeline master handoff.
Deployment remains separate.

## Local saves and place search (QA-31/32) — 2 October

On `fix/qa-31-32-local-delete-search`, the Builder's browser saves use the shared
confirmation dialog. Opening, Cancel and Escape never write storage; errors stay
announced and retryable. Confirm deletes only the selected ID, then focuses the
next/previous saved character or Save this character after the list commits.
Keep local/cloud storage separate, cross-tab refresh, character/world precedence
and the modal keyboard contract. No dataset, schema, migration or rebuild changes.
Global search compares joined place names for exact/prefix matches: apostrophes,
hyphens and spaces do not split identities. Preserve displayed catalog names,
canonical stop IDs, word/keyword ranking and original-character highlight maps.
QA-31 is `2af6d1d`, QA-32 `c5eb0ab`; integrated locally into site main from
`0d91ba0`, retaining the newer browser planner. It now selects both new case groups.
Merged-checkout validation: 1,209 site tests, 685 pipeline tests, Cloudflare build
(24 pages) and 143 targeted Chrome checks passed, including 18 synthetic signed-in
Vault checks and real-touch phone checks. LAUNCH_VERIFICATION §§60–62.
First command: `npm test -- --test-concurrency=4`, then BROWSER_TESTS' `QA-31/`
and `QA-32/` cases. Pipeline master has the identical handoff. No deployment.

## Main branch live in production — 2 October

Owner-authorized `250b1b5` is live as Worker `73df6e58-912e-48db-9786-5866ce793efd`
at 100%, 2 October 04:47 UTC (01:47 in São Paulo). This release publishes QA-26
(edited premade endgame kits dynamic scoring), the twelve-item launch polish
batch, and QA-27 through QA-30 (Health display formatting without floating-point
noise, END 100 target milestone marker, phone premade category wrapping, and
selected Alchemy apparatus label widening). Bundle `a29adea046e6086c2c7ee654`
and migrations 0001–0007 are unchanged; no data rebuild or migration. Code
rollback target: `e29663d3` / `6fab4c5`; fresh database recovery bookmark
`00000073-00000000-000050f8-07bcfcc5cabac281c64e4bebf751ce41`; release verification:
site's LAUNCH_VERIFICATION §58. First command: `npm test`, then read-only browser
verification against `https://siltstrider.tools`.

## QA-27–30 main integration — 2 October locally

Four separate stacked implementation branches are combined on
`polish/qa-27-30-batch`. The owner authorized their merge into freshly fetched
main `b8eeb50` and push after all required checks passed. The clean integration
candidate retains the latest main records and all earlier fixes. No deployment.
Player-facing changes: Health forecasts show clean totals with at most one
decimal; Endurance 100 is marked at the forecast endpoint; premade category names,
counts and actions stay whole on phones; selected apparatus names and qualities
fit their controls. Both site changelogs record these changes under 2 October.

Exported dataset/schema changes: none. Bundle `a29adea046e6086c2c7ee654` is unchanged.
The Health formatter is display-only; precise curves, fractional gains and saved
starting Health remain intact. The Endurance milestone includes the target level
but does not invent an achievement at an already-maxed starting level. Native
apparatus options retain their canonical IDs and qualities, including distinct
records with the same readable name. Character/world/account precedence, source
queries, hydration safety and all earlier QA fixes remain required invariants.

Implementation commits: QA-27 `7e5b278`, QA-28 `4d9c1e0`, QA-29 `cd91229`,
QA-30 `bfc074f`. Causes, edge coverage and bounded cumulative results are in
the site's LAUNCH_VERIFICATION under QA-27–30. Screenshots and reports are in
`A:/Cache/qa27-30`. Validation: 1,184 site tests, the Cloudflare and synthetic
Vault builds, 418 Chrome cases (including 192 hydration and 34 signed-in cases)
and 685 cache-isolated pipeline tests passed. Both disposable Vault databases
contain zero saves/settings/tier overrides. Shared documents are synchronized in the isolated pipeline
handoff; other agents' checkouts are preserved. First command for the next agent:
from a main checkout, run `npm test -- --test-concurrency=4`, then the
world-filtered QA-27–30 groups in `docs/BROWSER_TESTS.md`. Release authorization
remains separate.

## Edited premade endgame kits (QA-26) — 1 October locally

QA-26 (`2b86443`) is merged into main with owner authorization; not deployed.
Named BestInSlot picks require the full original
premade identity (sameCharacter), shared with characterName. Edited/custom namesakes
use the bundle model for every slot; weapon preference restores non-weapon picks
only for unchanged premades. Keep beast gates, runner-ups, equip transfer and shared
character titles intact. No exported schema, bundle, migration or rebuild. Verify:
site LAUNCH_VERIFICATION §§52–53. First command: `npm test`, then BROWSER_TESTS' Chrome
`--suite qa --filter QA-26/` on main. Bundle and production remain unchanged.

## QA and Morrowind theme live — 1 October

Owner-authorized `6fab4c5` is live as Worker `e29663d3-68eb-45ff-bbef-13447c3b0cbf`
at 100%, 2 October 00:13 UTC (1 October, São Paulo). This includes the character,
calculation, Travel, equipment, phone-layout and copy QA fixes plus the new theme.
Keep character/world precedence, source-owned share links and hydration-safe UI.
Bundle `a29adea046e6086c2c7ee654` and migrations 0001–0007 are unchanged; no data
rebuild or migration. Code rollback: `3879ce7b` / `ef67b3e`; fresh database bookmark
and verification: site's LAUNCH_VERIFICATION §§48–49. First command: `npm test`,
then the read-only QA/touch browser suites against the live URL. Freeze acceptance
and real-phone/provider checks remain separate.

## Launch QA integration — 1 October

Owner-authorized merge of launch/character-preservation (c065581) into main
(4f9c4bb); no conflicts, dataset/schema changes, migration or deployment.
Retain character/world precedence, exact link choices, engine-source calculation
rules, beast eligibility, display-only faction filtering and hydration-safe UI.
All implementation QA items are now on main; freeze acceptance remains separate.
Verification: LAUNCH_VERIFICATION §46. First command: `npm test`, then the local
Chrome and synthetic Vault runners in BROWSER_TESTS against the merged checkout.


## Faction display labels (QA-11) — 1 October

Filter <Deprecated> records from the Journal's roster, selection and displayed
counts; keep the full catalog for case-insensitive published relation-name lookup.
Unknown internal IDs display Unknown faction; ordinary fallback names still work.
Keep saved memberships, relation adjustments and bundle records unchanged. No
exported schema, dataset or rebuild. First command: `npm test`, then Chrome
QA-11 in BROWSER_TESTS (three worlds, both themes, desktop/phone). Verification:
§44. Next authorized work: QA-15; push after each completed item.


## Premade explanations (QA-12) — 1 October

Each premade card has plays-like/trade-off copy, full Major/Minor skill labels
and a specialization explanation. Keep choices and save/link shapes unchanged.
Playstyle groups use category copy; race/ARCE groups use the first Major skill
for presentation only. Null/unknown inputs use generic copy; frozen inputs stay
untouched. No exported dataset/schema/rebuild. First command: `npm test`, then
Chrome QA-12 in BROWSER_TESTS. Verification: §43. Next: QA-11, then QA-15; push
after each authorized item.

## Morrowind Game Theme (DESIGN) — 1 October

Owner-authorized integration of `design/morrowind-game-theme` (`d85a931`) into
main: black windows, tan text, procedural SVG frames and the Home stats window.
Keep theme IDs unchanged, overrides scoped in `app/theme-morrowind.css`, and
both visual forms in the server-rendered DOM to avoid hydration branching.
Modern UI keeps its layout; only the theme-toggle preview changes. Preserve the
recent QA fixes, accessible character labels and semantic status colours. No
exported schema, bundle, migration or game-asset change. Verification: site's
LAUNCH_VERIFICATION §47; deployment remains separate. First command: `npm test`
in the site checkout, then the documented Chrome matrix and QA-08/09 filters.

## Obtainable apparatus (QA-06) — 1 October

Alchemy excludes apparatus_sm_ keys at the start or after a mod prefix, and
Secretmaster/Secret Master names (straight/curly apostrophes). Keep ordinary
Master/Grandmaster tools, effectiveness ordering, and immutable catalog/source
records. This is site filtering only: no exported data/schema change or rebuild.
First command: `npm test`, then Chrome QA-06 in BROWSER_TESTS. Verification: §41.
Next authorized work: regression-check the completed QA-05.

## Travel search and link origin (QA-07/25) — 1 October

Normalize apostrophes/dashes only for search comparisons, never route IDs or
catalog labels. City searches stay grouped; named rooms remain searchable.
Uncommitted picker edits hide the old dossier and map; Escape/blur cancels and
selection commits. Preserve the initial explicit link origin through the first
async save restoration; without from, the save wins, and a later imported save
can start a new journey. No dataset/schema change. First command: `npm test`,
then Chrome QA-07 and QA-25 filters in BROWSER_TESTS. Verification: §40.
Next authorized work: QA-06, then the completed QA-05 regression recheck.

## Teleport-only stop aliases (QA-16) — 1 October

When Travel node metadata is absent, buildTransitStops uses a published Places
name (or the interior cell name) and its "Town, room" prefix for a boundary alias.
Explicit Travel metadata wins; keep the full room label and exact stop ID.
Exterior coordinates remain distinct; aliases expand only origin/destination,
never graph edges or free intermediate transfers. Apply usableTeleport's quest
and held-item gates before building the network. No exported schema/rebuild.
First command: `npm test`, then Chrome `--suite qa --filter 'QA-16'` in
BROWSER_TESTS. Verification: LAUNCH_VERIFICATION §39. Next: QA-07/25, then QA-06.

## Configure help placement (QA-09) — 1 October

All five Configurator InfoTips use a body portal with fixed coordinates measured
after opening. Clamp to visualViewport and visible header/tab-bar bounds; flip
above when below is too short, and scroll long text inside the available space.
Reposition on resize, page scroll and font load; keep internal scrolling intact.
Retain stable hydration IDs, trigger/control linkage, tap-toggle, outside/focus
dismissal and Escape focus restoration. No exported schema or data change.
First command: `npm test`, then BROWSER_TESTS' QA-09 Chrome and `--touch` runs
and enforced report wrapper. Verification: LAUNCH_VERIFICATION §38.
Next authorized work: QA-16, QA-07/25, QA-06, then recheck the completed QA-05.

## Phone gear tables (QA-08) — 1 October

Claimed 20:51 UTC on `launch/character-preservation`, after QA-10 was pushed.
Early/late recommendations and expanded runner-ups stack slot, item and source
at widths up to 640 px. Keep `.gear-table`, the source cell's `data-label`, native
table headings/column scopes and accessible names; phone CSS must override
mid-word wrapping and narrow first cells. Desktop keeps its three columns.
No ranking, dataset, exported schema, migration or production change. First
command: `npm test`, then Chrome `--suite qa --filter 'QA-08'` and the enforced
report wrapper in BROWSER_TESTS. Verification: LAUNCH_VERIFICATION §37.
QA-09 popovers are still open; next priority is QA-16 after owner go-ahead.

## Beast equipment eligibility (QA-10) — 1 October

Claimed 20:28 UTC on `launch/character-preservation`. BestInSlot filters every
final primary/runner-up after named, dynamic, fallback and weapon-preference
paths. Beast picks need explicit `beastWearable: true`; exclude footwear and
closed-head Armor body parts. Preserve open helmets and catalog order, without
mutating bundle records. Races' boolean `beast` overrides name inference (ARCE
Suthay is not a beast). Carry it through recommendations, equip validation,
inspector and item picker; callers without it retain legacy inference.
No exported schema, dataset, migration or production change. First command:
`npm test`, then Chrome `--suite qa --filter 'QA-10/'` in BROWSER_TESTS.
Verification: LAUNCH_VERIFICATION §36. Next target: QA-16, after owner go-ahead.

## Test portability — 1 October

QA catalog tests use `staged()` in `test/helpers/qa-staged-data.cjs`: skip only
when `public/game-data/current.json` is absent. Preserve TODO metadata; a
present but malformed/incomplete bundle must fail through the normal loader.
Apply the same guard to catalog-dependent character, share, Health and hydration
cases; pure/synthetic tests still run. The BestInSlot fallback fixture includes
weapon type, boots warnings and runner-ups. No runtime or dataset changes.
First command: `npm test`; stage a bundle to run the catalog checks too.
Verification: LAUNCH_VERIFICATION §35. Next target: QA-10, after owner go-ahead.

## Character identity labels (QA-05) — 1 October

Rechecked after QA-16/07/25/06: all three views retain edited identity in three
worlds, both themes and phone/desktop. Chrome must use native randomness; a
global constant Math.random override interferes with React event handling.
Exclude only Next dev's toolbar (nextjs-portal) when testing the phone Home tab;
production has no toolbar. Deterministic hydrateRoot tests remain. Verification:
§42; first command remains `npm test`, then the QA-05 browser filter.

Claimed 19:50 UTC on `launch/character-preservation`. Computed sheets retain
raceName/signName, gender, class and class choices for normalization; catalog
race/sign objects are facts, not the selected display labels (ARCE especially).
Builder, Home and Simulator use `characterName`. New premades carry optional
`premadeSource`; validate it against the known pool and retain it in build links,
sanitizing and snapshots. An edited premade title reads "Based on …"; custom
names and legacy names without that marker remain names. Keep first hydration
fixed; random draws happen in effects. No exported dataset, migration or
production change. First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`,
then Chrome `--suite qa --filter 'QA-05/'` as in BROWSER_TESTS. Verification: §34.

## Level Health preservation (QA-03/04) — 1 October

Claimed 19:34 UTC on `launch/character-preservation`. OpenMW 0.51.0
`NpcStats::levelUp` keeps fractional Endurance gains; `updateHealth` sets the
creation base in `MechanicsManager::buildPlayer`, not on later level-ups.
Keep existing Health and attributes when normalizing a sheet or normalized
state with catalogs. Bitter Cup applies once and never recalculates creation
Health; changed Endurance affects future gains. The chart uses that same state;
Endurance 30 with +5 per level reaches 100 at level 15. Keep the marker label
inside the phone chart. No dataset, extraction, migration or production change.
First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`, then Chrome
`--suite qa --filter '/level-health/'` as in BROWSER_TESTS. Verification: §33.

## Enchanting running costs (QA-01/02) — 1 October

Claimed 19:11 UTC on `launch/character-preservation`. Follow OpenMW 0.51.0
`Enchanting::getEffectCosts/getEnchantPoints/getEnchantChance/getEnchantPrice`.
Retain each cumulative float cost: clamp to 1 before Target ×1.5; Constant uses
the profile's duration multiplier. Capacity adds each cost's floor, chance adds
the precise costs, and base price truncates only the final cost × value multiplier.
Chance uses Enchant + 0.2 Intelligence + 0.1 Luck, the profile's chance penalty,
full fatigue for this UI and the Constant chance multiplier; truncate, then clamp
to 0–100. Never feed capacity points into chance or price. Consume the staged
GameSettings; no bundle, extraction, migration or production change. Two 5/5
Constant effects need 75 capacity points and 50,050 base gold; the 5/5, 5-second
Target example needs 1 capacity point and 1,912 base gold (70% at 50/40/40 stats).
First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`, then Chrome
`--suite qa --filter '/enchanting/'` as in BROWSER_TESTS. Verification: §32.

## Character world preservation (QA-21/22/23) — 1 October

`launch/character-preservation` was taken over at 18:14 UTC and includes main's
QA-24 sign-out fix. Vault modal/workstation loads use `loadBuild`, await the
build's profile catalogs, and retain the current character/save if validation
or fetching fails. Legacy builds without a world keep the current world.
Account settings version 2 adds `worldChosen`; only the account control chooses
a Preferred world. Header/save/build loads change this session, not the account
preference. Read version 1 as unchosen without writing it; preserve other settings.
Keep shared-link/current-edit priority, guest/account isolation and fixed first
hydration render. Existing version 1 preferences need an explicit choice again;
old code rejects version 2 documents, so account rollback needs a compatible reader.
QA-22 sharing fetches the full stored save, resolves its own profile catalogs and
refuses unresolved or invalid class choices; it never applies the save or borrows
the active character. Build links carry creation choices, not saved progression.
Challenge links use the run's profile (legacy seeds supply it); seedless links
capture their opening world before cleaning the URL. Preserve run profile in
storage and sanitizing. No header-world substitution when copying an existing run.
No bundle, extraction, D1 migration or deployment. First command: `npm test` in
`A:/Claude/mt-calc-4-main-merge`, then `--character-preservation` and
`--signout-preservation` in `docs/BROWSER_TESTS.md`, then QA-22's Vault and ordinary
Chrome cases. Verification: LAUNCH_VERIFICATION §§30–31.

## Character through sign-out (QA-24) — 1 October

QA-24 (`aebd6c0`, branch tip `bce1401`) is integrated into main from `0c55696`
with owner authorization on 1 October; QA-21/23 remain in the other session's
`launch/character-preservation`. Before Clerk
sign-out, dispatch `SIGN_OUT_EVENT`. Keep an unsaved build in the separate
`silt-sign-out-character` tab marker; restore its character and world only on a
signed-out return within 15 minutes, then remove it. Shared build links win;
loaded saves use their existing persistence. Failed sign-out removes the marker.
Keep the fixed server/first-client render; random starts happen only in effects.
No dataset, settings-document, migration or production change. First command:
`npm test` in `A:/Claude/mt-signout-main-merge`, then the local Vault runner's
`--signout-preservation` cases in `docs/BROWSER_TESTS.md`.

## Ingredient sources (CALC-4) — 30 September; updated 1 October

Pipeline catalog `IngredientSources` (`build_ingredient_sources.py`; contract
`contracts/ingredient-source-types.ts`; docs/stages/INGREDIENT_SOURCES.md) has
one record per ingredient and profile: shops with cell, stock and restocking;
regrowing plants with harvest chance, quantity and spread; creature drops with
level, chance and placement/spawn spread; loose/container finds with locations.
Every cell is a Places key. No source is `{key, name}`. Theft, NPC inventories,
random loot, scripts, quest rewards and holding/test cells are excluded by the
builder. Chances follow OpenMW 0.51.0's pinned `getLevelledItem` at player level 1,
or the explicit `fromLevel`. Never infer ingredient stock from merchant services.
With owner authorization on 1 October, pipeline correction `41da92c` was rebuilt
and staged locally as bundle `a29adea046e6086c2c7ee654`. Only IngredientSources
changed; the extraction snapshot and every other catalog are unchanged. Records
cover 126 vanilla and 921 TR ingredients; TR + ARCE inherits TR. Test/holding
cells and rare random creature loot are absent. The old immutable bundle remains.
With owner approval on 1 October, `launch/calc-4-reverse-alchemy` at `c2bf5d8`
merged into main `55fd07e` as `ef67b3e`: the effect finder, sources and Travel city
transfers/swimming fallback are together. Main's Cloud Vault fixes are retained.
Each filled Alchemy slot has a "Where to get it" button, plus the pair shortcut.
Load `ingredientSources` only when opened: Places required, IngredientSources
optional for older bundles.
Keep loading neutral, error Retry available, and unavailable/unknown sources
explicit. Replacing/clearing ingredients and changing worlds discard old panels.
Keep stock/restocking, locations, locked finds and level qualifiers; never combine
variants with different chances, quantities or levels. Catalog data stays frozen.
`components/calculators/alchemy/ingredient-sources.jsx` shares source content with
the finder; synthetic tests cover lazy loading, provenance/inheritance, malformed
records, draw distinctions, old bundles, retry and selected-ingredient lifecycle.
First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`, then the full Chrome
and local Vault suites in `docs/BROWSER_TESTS.md` on a newly started local server.
Owner-authorized `ef67b3e` is live as `3879ce7b-c397-4698-83c4-e9d185d9ed5c`
at 100% (1 October 05:22 UTC), with bundle `a29adea046e6086c2c7ee654`.
Reload existing tabs because the loader pins a release for each page lifetime.
CALC-4 is complete and live. The owner requested closing the test servers;
8792, 8793 and 8794 are stopped. Code rollback: `d523b9ba` / `216cd90`,
preserving additive migration 0007. No migration or new extraction.

## Travel city transfers — 30 September

`launch/travel-city-stop-walks` at `f07425c` is integrated into its original
CALC-4 parent, `launch/calc-4-reverse-alchemy`, on 1 October with owner approval.
Cities stay merged in search, links and unspecified journey endpoints. Specific
hall, district, service or provider queries reveal precise locations. The router
chooses city boundary platforms without phantom legs; cities must never become
free intermediate connections. Journeys through cities show arrival/departure
stops and timed outdoor transfer walks, including the doors into guild halls.
Published Travel cells/positions, Access exits and teleport/Intervention markers
already retain these distinctions; no extraction, bundle/schema or D1 change.
Outdoor stop IDs use cell plus rounded positions; indoor IDs use cell plus Access
exits, never local indoor coordinates as world positions. Missing positions or
exits cannot imply a free transfer. Preserve terrain, membership, quest, inventory,
Magicka and scroll limits. Indoor time and mesh obstacles remain uncounted.
Old town links stay town choices; exact-stop links retain their selection.
Picker drafts survive equivalent option lists recreated by late character data;
changing worlds or endpoints cancels the draft. The effect finder stays intact.
1 October: optimize the restricted walking network first. Only a failed route
retries with long endpoint/place walks and open-water swimming, using the same
objective, character, membership, quest, inventory and spell/scroll budgets.
Valid normal journeys must not gain a one-leg walk for Fewest legs or Cheapest.
There is no new toggle, warning or stored preference. Walking off still forbids
both phases. Mixed legs time land at run speed and water at swim speed (run speed
with Water Walking). Keep terrain barriers, sparse local transfers and bounded
search work; missing exits cannot imply connections. The parent's Alchemy finder
and ingredient-source lookup are both included; preserve their lazy loading.
The owner retired the two-failure/boost rule in both AGENTS.md files.
First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`, then the Travel
Chrome cases in `docs/BROWSER_TESTS.md` on a newly started local server.
The combined branch is merged, pushed and live as `ef67b3e` / `3879ce7b`.
The owner requested closing the test servers on 1 October; they are stopped.
Data rebuild remains a separate request.

## Reverse alchemy (CALC-4) — 30 September

`launch/calc-4-reverse-alchemy` starts from main `f5b1f56`. Choose up to four
effects to find pairs in the current profile; each distinct ingredient must
carry every target, including its attribute/skill identity. Show additional
shared effects, then rank by fewer extras and ingredient base value, never a
merchant quote. Using a pair replaces all four slots and focuses potion output.
Keep the existing calculator, obtainable apparatus, typed stats and world-reset
behavior. No exported schema/bundle, extraction, API or migration changes.
Published Merchants has no ingredient stock; the integrated source lookup
consumes IngredientSources, as described above. Do not infer sellers from service
flags or rebuild real data. This implementation is live as `ef67b3e` / `3879ce7b`.
First command: `npm test` in `A:/Claude/mt-calc-4-main-merge`;
then the `Alchemy effect finder` cases in `docs/BROWSER_TESTS.md`.

## Account settings and tool polish live — 30 September

Owner-authorized main `216cd90` is live as Worker `d523b9ba` at 100% (1 October
00:11 UTC, 30 September locally). Recovery target: `3ef09493`; rollback leaves
additive migration 0007 intact. Bundle and historical records are unchanged.
Keep identity/revision guards, explicit guest adoption, shared-link/current-edit
priority, save-derived Travel precedence and resource budgets. Loading is neutral;
Secretmaster stays hidden only in the adapter; Constant Effect requires soul 400.
Compact navigation includes all three calculators. Earlier pending-release notes
below are history. Verification and recovery record: LAUNCH_VERIFICATION §16.
First command: `npm test` in `A:/Claude/mt-account-main-merge` before any commit.

## Production account settings migration — 30 September

The owner authorized remote 0007, applied at 23:56 UTC from main `254c76f`.
Production now has migrations 0001–0007 and none pending. The empty settings
table was added; all historical schema objects, counts and actual records match
the verified private backup. Recovery bookmark and evidence: the site's
`docs/LAUNCH_VERIFICATION.md` §15. Keep private SQL exports/restored files out of
Git and public assets. The older pending-migration notes below are history.
No Worker deployment or bundle/extraction change. Existing Workers ignore the
new table; code rollback does not undo it. Settings deployment is a separate ask.
First command: `npm test` in `A:/Claude/mt-account-main-merge`, before any commit;
for a future release, follow `docs/DEPLOYMENT.md` and refresh recovery metadata.

## Account settings and tool polish on main — 30 September

The owner authorized PR #1: `feature/account-settings-preparation` at `6dc207e`
merged to main in `b45f686` (ACC-1, ACC-2 and the tool polish). Earlier branch
status notes below are history. No extraction or exported bundle change.
Keep account identity/generation and revision guards, explicit guest adoption,
shared-link/current-edit priority, and save-specific settings precedence. The
least-real-time route still respects scroll/Magicka budgets and leaves loading,
menus and indoors uncounted. Keep the published apparatus records intact and
Constant Effect gated at soul size 400. Compact menus contain all calculators.

Production is unchanged. Migration 0007 remote apply remains a separate owner
step with a fresh recovery bookmark, before any settings API deployment.
ACC-1/ACC-2 code items are complete; ACC-1 production remains open.
First command: `npm test` in `A:/Claude/mt-account-main-merge`; then the full
browser suite in `docs/BROWSER_TESTS.md` on that checkout. Merge checks:
`docs/LAUNCH_VERIFICATION.md` §14 (887 unit tests, 153 Chrome cases, 24 pages,
Worker dry-run). Do not treat this merge as a deployment.

## Small tool polish — 30 September

`launch/small-polish` starts at `db9def9` from `mt-account-settings`; keep its
account/save/shared-link precedence. No exported dataset, schema or extraction
change. Unsaved unlinked Travel starts Seyda Neen → Balmora. Objective `real`
minimizes outdoor movement seconds, then transitions, legs, gold and game hours;
unknown movement is not zero, and scroll/Magicka budgets still constrain routes.
Menus, loading and indoors remain uncounted. Pending data shows Loading, while
genuine network failures retain Retry. Account defaults and shared links accept
`real`; the settings format remains version 1 before its first public release.

Alchemy hides Secretmaster apparatus in the site adapter and sorts remaining tools
by quality descending, preserving published records and the Journeyman default.
Enchanting accepts typed nonnegative integer soul sizes; below 400, Constant
Effect is disabled and returns to When Used. At 1440 px and wider, all calculators
are direct links; compact desktop and phone menus group Alchemy, Enchanting and
Spellmaking. Header rules target `.topbar`, not the removed `#react-header-slot`.

First command: `npm test` in `A:/Claude/mt-small-polish`; then the `polish` suite in
`docs/BROWSER_TESTS.md`. Verification: `docs/LAUNCH_VERIFICATION.md` §13. Keep this
branch separate from main and production until the owner requests integration.

## Account settings branch verification — 30 September

The earlier proposal note below is preserved as history. On the branch inherited
by this polish, `feature/account-settings-preparation`, `db9def9` has incorporated
main `11c1c96`; migration 0007 lives in `cloudflare/migrations`, and the settings
API, provider and controls are implemented. The owner decides integration and
production apply separately. No remote migration or account deployment ran here.

ACC-1 verification: the table retains its reviewed shape; schema tests use
`node:sqlite` with `--experimental-sqlite` to retain Node >=22.11. The SQLite
experimental warning remains visible. After the main merge, local migrations
0001–0007 passed with no pending migrations and 28 historical schema objects
unchanged; 808 tests passed and the Cloudflare build generated 24 static pages.
Details in `docs/ACCOUNT_SETTINGS.md`.
ACC-2 now adds the owner-bound settings API/provider/account controls and connects
World, theme, Travel, Gear Advisor and Challenge defaults/reset actions on the same
unmerged branch. Guest preferences stay separate; adoption is explicit. Late loads,
in-flight edits and account switches cannot overwrite newer choices or another
account's preferences. Shared routes/seeds and current edits keep priority, and
Travel's spell/scroll checks still apply. No release registry or gear-row changes:
modpack/version controls remain unavailable and the two future gear filters hidden.
Verification details: `docs/LAUNCH_VERIFICATION.md` §12. No remote apply or deployment.
Latest main `11c1c96` incorporated without rebasing: 876 tests, 24 static pages,
33 local browser cases and fresh local migrations passed; only settings work differs.
Owner decides the merge to main and applies production separately.

## Account settings table before launch — 2026-09-30

No game-data schema changes yet. The owner decided the `account_settings` D1 table is
created before launch, while there are no real users (checklist ACC-1; the API and page are
ACC-2 in section 4). Design, contract and draft SQL: `docs/ACCOUNT_SETTINGS.md`,
`lib/account-settings.mjs` and `cloudflare/proposals/account_settings.sql` on
`feature/account-settings-preparation`, which was started from the Travel branch and must
take `main` before it merges. Invariants other agents must keep:

- **Its own table.** One row per Clerk account: the ID, a JSON document of at most 16 KiB
  with an integer `version`, a `revision`, timestamps. No username needed, no save-vault
  slot used, no change to `cloud_saves` or `account_profiles`. Never edit 0007 once applied;
  a later change is a new migration.
- **Applied apart from releases.** Remote apply is an owner step with a fresh Time Travel
  bookmark, never inside a Worker deploy. Workers before 0007 ignore the table, so rollback
  targets stay valid.
- **The format is the contract.** The JSON shape lives in `lib/account-settings.mjs`
  (`ACCOUNT_SETTINGS_VERSION` 1); once ACC-2 writes real rows, a change is a version bump
  with a reader for the old one. Shared links and edits in the open tool win over account
  defaults; stored `false` is a real choice; theft stays off unless the player turns it on.
- **Tests run anywhere.** The schema test uses `node:sqlite`, not Python or a Windows path.

Asking the pipeline, not yet a contract change: modpack and mod-version settings need a
published release registry (stable modpack IDs, immutable release IDs mapped to bundles),
and the Gear Advisor's quest-reward and difficult-encounter settings need gear-row fields
that tell those picks apart. Until then those settings stay unavailable.

QA-15 (1 October): About credits LowGraph, links the code repository and names
AGPL-3.0-or-later for the code only. Keep the game/mod-data and branding exclusions,
Pelagiad's separate OFL credit and AI-assistance disclosure. No exported schema,
dataset or rebuild. Verification: LAUNCH_VERIFICATION §45; first command remains
`npm test`, then Chrome QA-15 in BROWSER_TESTS. All three authorized items are
complete on the site branch; freeze acceptance remains a separate step.

First verification command: `npm test` in the site repository.

## Travel task-first — 30 September

TRV-2, TRV-4/5, TRV-6, TRV-7 and TRV-8 are merged to main (`e3ab542`).
Main `2c113b8` was deployed at 20:32 UTC, rolled back at 20:47 after two mobile
saved-choice failures, then restored unchanged at 21:30 with the owner's explicit
authorization to reproduce on live. Those releases are history: current main
`216cd90` is live as `d523b9ba` (§16). The failed 375 px version `3ef09493` and
last fully accepted pre-Travel version `24bd4ac1` both support additive migration
0007; leave the rollback choice for the freeze. The live rerun passed, but the
root cause is unconfirmed. Diagnostics from `19bdd92` are merged to main: check
each edited control and all four stored choices before navigating, then check
restoration and profile isolation. Application persistence is unchanged.
Evidence: `docs/LAUNCH_VERIFICATION.md` §§9–10. Bundle `3da03202` is unchanged.
This documentation/test-runner merge passed 887 site tests and the saved-Travel
case twice each at 1366/375 px on the dev server; current evidence is in §17.
No application code or deployment is part of the housekeeping merge.
No bundle schema,
loader, extraction or save-format changes. Invariants other agents must keep:

- One picker per endpoint joins towns, stops and places; typing does not reroute.
  Keep canonical stop names and place IDs for routing and shared links.
- Journey inputs and results precede closed options, quick places and rules.
  Keep guild/overload warnings beside the answer and one loading/error/Retry line.
- Browser edits are keyed by save snapshot and profile. Reset only that pair;
  denied storage keeps session edits. Replanning never spends the imported save.
- Scroll uses and known current Magicka constrain the whole route. Cast chances
  use published spells; unknown data must not imply a reliable cast.
- Real Time Approximation counts outdoor movement seconds separately from
  transport/spell transitions; omit combat, menus, loading and indoor time.
  Cheapest compares Fewest legs with identical options and consumable budgets.
- Keep main's unfaded restricted equipment/rank cards, danger-7 warnings, fg-14
  labels and fg-9 preset descriptions; do not reintroduce fg-16/fg-17 small print.

First command in the site repository: `npm test`, before every commit. Browser
command/scope: `docs/BROWSER_TESTS.md`; results: `docs/LAUNCH_VERIFICATION.md` §§8–10.
Further deployment needs a separate owner request.

## Release sprint ownership — 2026-09-29

The owner authorizes any agent to implement release-sprint work in either repository.
Agent roles are specialties, not exclusive editing or commit permissions. The site's
`docs/LAUNCH_CHECKLIST.md` sets priorities, task-claim timestamps, completion records,
the freeze and the cut line. `C` means whichever agent does the work; `O` remains
owner work. Inspect existing changes and preserve other sessions' work. This policy
supersedes older agent ownership restrictions in the roadmap and handoffs.

The architecture boundary stays: extraction belongs in the pipeline and the site
consumes published JSON bundles. Verification, explicit authorization for real-data
rebuilds, and separate push/deploy authorization still apply. No dataset schema or
runtime changes. Next agent: read the launch checklist and claim the next available
item; first verification command is `npm test` in the site repository.

## UX pass for launch — 2026-09-29

HOME-1/MOB-2, SITE-4, SITE-3, MOB-1/MOB-4, HOME-3, ENC-1, CALC-3, CHL-2, LVL-2/LVL-3, the header menus, the Cloud Vault hash check, the phone tab bar's Travel tab and the Vault header's account line are merged to main (`d4e96bd`), not deployed.

No game-data schema changes. Items from `docs/LAUNCH_CHECKLIST.md` (finding IDs from `docs/UX_USABILITY_AUDIT.md`), one commit each. Invariants other agents must keep:

- **LVL-1: archetype detection.** Mercantile and Speechcraft count in full toward Diplomat / Merchant only as majors (4 each, 1.5 as minors, +3 for favoured Personality, +5 with both as majors; 8 or more is a Diplomat), so the default character, a fighter with both as minors, is a Warrior and is no longer told to raise Personality first. `explainArchetype(build)` returns the archetype with a reason ("the Warrior class", "major skills Long Blade, Heavy Armor and Block", the most telling skills first) that the Level Simulator shows; `detectArchetype` still returns the archetype alone, and the Gear Advisor's `buildTraits` follows it. `test/archetype-reason.test.js`.
- **TRV-1: Guild Guides and membership.** Every Guild Guide belongs to the Mages Guild (one TR guide to `T_Cyr_MagesGuild`), and the guild's Service Refusal lines refuse anyone outside it ("same faction" = 0); guides sit at rank 1 to 3, so the "higher rank" refusal never stops a member. Without a save the Travel page keeps Mages Guild on and Conjurer off (owner decision); with one, `guildFromSave` sets both, and `guildGuideNotice` (`lib/travel-graph.mjs`) explains when the character is not a member. Guild Guide legs say "Mages Guild members only". `test/travel-guild-notice.test.js`.
- **TRV-6: "from your save".** `saveMarks` marks the Mages Guild, Conjurer and Intervention boxes while they hold the save's value (unticked ones too), and ticked carried items the save holds; `interventionSources` tells a known spell from a carried scroll, and `interventionMarkText` adds "a scroll, one use". Choices are still reset from the save on each visit; remembering them and spending scrolls are TRV-6 in the launch checklist, section 4. `test/travel-save-marks.test.js`.
- **BLD-1: theft is opt-in.** The Gear Advisor's options take their defaults from `DEFAULT_GEAR_TOGGLES` (`lib/gear-rows.mjs`), all off; do not give the component its own defaults. The Mentor's Ring benchmark already holds with theft on and off. `test/gear-defaults.test.js`.
- **TRV-3: one entry per town.** `matchPlaces` (`lib/travel-walk.mjs`) is the Travel pickers' place search: same-named exterior cells in one region (a town spans several; 19 in vanilla) are listed once as the most central cell, ties to the first key; rooms never merge; stops stay out. Place buttons carry `bg-transparent border-0`, as every button needs one or the browser paints its grey. `test/travel-place-search.test.js`.
- **Claims.** No page, card, search description or structured data may call the maths "verified" or "exact", or promise "inter-faction standing"; say it follows OpenMW 0.51's source, and describe the Faction Journal's reactions as how factions regard each other. `test/site-claims.test.js` scans app, components and the SEO data (past changelog entries excepted); LAUNCH_POSTS lists the removed claims.
- **HOME-2, replaced: a random premade start.** `CharacterProvider` renders `DEFAULT_BUILD` on the server and in the browser's first render (anything random there fails hydration and React discards the prerendered page), then its first effect sets a random premade from `getRandomPremadeBuild` (`lib/premade-data.mjs`: base-game races unless ARCE); links, the sign-in handoff and saves apply after it and win. Leaving ARCE with an ARCE-only race: an untouched random premade is re-drawn, a player's character keeps everything but the race (`canonicalRaceFor`). `test/random-premade-start.test.js`, `test/random-premade-build.test.js`.
- **The shell is not ready while a page hydrates.** Until then `useShell()` has `ready: false` and the prerender's world (vanilla), whatever the visitor chose; the client's world arrives in the next render. Effects that run at mount and need the world read it directly: `readVisitorProfile()` (address, then storage) or `readStoredProfile()` (storage only), both in `components/shell-context.jsx`. `CharacterProvider`'s world sync waits for `ready`. Test such code with `hydrateRoot` over a `renderToString` page (the `hydrated` helper in `test/random-premade-start.test.js`); `createRoot` hides the problem.
- **SITE-1: one name per tool on screen.** Character Builder, Level Simulator, Travel Planner, Alchemy, Enchanting, Spellmaking, Faction Journal, Challenge Runs, Cloud Vault in nav, visible headings, buttons, home cards, search and breadcrumbs. The long SEO names stay in page titles, the sr-only h1 (`lib/view-headings.mjs`), the pages' hidden guides and structured data. `test/tool-names.test.js` fails on an old name in `components/`, the home and search data, the 404 page or the challenge export.
- **LINK-1: a shared link's world wins.** A build or run link that names a world (`world` or `arce` in its query) sets it, as the world switch would; one that names none keeps the visitor's world (it would decode as vanilla). Compare with the kept world, not the hydrating shell. Tests: `test/random-premade-start.test.js` (builder), `test/share-link-world.test.js` (runs).
- **CALC-1: no results before input.** Spellmaking and Enchanting show `NO_RESULT` (a dash with sr-only "not calculated yet") for chance, cost, school and vendor prices until an effect is chosen, with a `.calc-empty-prompt`; Alchemy until `potion.isValid`. Enchanting's capacity stays a number. Effect pickers label base costs with `baseCostLabel` (float32 noise). `test/calculator-empty-states.test.js`.
- **SITE-2 / VLT-1: explanations are closed disclosures.** Each tool has exactly one `<details className="calculation-notes">` with `<summary>How this is calculated</summary>`, closed by default, in plain words with any formula inside; no "invariants", "engine rules" or implementation jargon (ArrayBuffer, SQLite, Cloudflare) in player text. `assertCalculationDisclosure` in `test/seo-phase2.test.js`. Codex's work, finished and merged by Claude.
- **Contrast: fg-12 to fg-15.** The muted tokens in `app/globals.css` (Morrowind UI) and `app/theme-ashfall.css` (Modern UI) reach 4.5:1 on the surfaces they sit on; unselected Challenge presets are no longer faded (`opacity-75`). fg-14 still falls short on the Faction Journal's tinted states (surface-13, -18, -19, success-surface-2), so text there uses fg-12. Before putting a muted token on a new surface, add the pair to `test/contrast-tokens.test.js`.
- **Level Simulator reorder buttons are 24px** (`w-6 h-6` in `attribute-priority-ranker.jsx`), the minimum target size; do not shrink them. `test/level-simulator-ui.test.js`.
- **Headings nest without gaps on the Level Simulator and Vault:** tool title h2, sections h3, items h4, in both workstations and the Vault modal (its title is its h2). Pages add no h1: the sr-only one from `lib/view-headings.mjs` stays first in `<main>`. `test/heading-hierarchy.test.js`.
- **FAC-3: faction quests by name.** `getFactionQuests` keeps named quests only, as the game's quest list does; a topic without a name is a journal note (the Mages Guild's dues reminder), and no quest shows its key or stage numbers. Status reads Completed, In progress or Available. `test/faction-math.test.js`, `test/journal-factions-ui.test.js`.
- **MOB-3: the Ctrl K hints are for keyboards.** One rule in `app/globals.css` hides both (header and home) under `(max-width: 899px), (hover: none) and (pointer: coarse)`; a touchscreen laptop keeps them. `test/header-hints.test.js`.
- **SITE-5: ARCE is All Races and Classes Enabled** (the mod's own name, not "Aran Rebuilt"). The TR + ARCE button's tooltip and description (`#world-arce-help`, shown in the phone menu) say so; `test/header-hints.test.js` fails on any other expansion.
- **BLD-2: the Gear Advisor ranks by itself.** The ranking (`gearRanking`, needing no catalogs) runs whenever the build or attributes change; its key leaves out the name, so typing it does not re-rank. The `gear` and `bestInSlot` catalogs load only when `#gear-advisor` is within about a screen (IntersectionObserver), on a gear button, or at once without an observer: on every Builder visit they would add about 180 KB compressed in vanilla and 530 KB in TR (docs/DATA_LOADER.md). Defaults stay `DEFAULT_GEAR_TOGGLES`. `test/automatic-gear-advisor.test.js`, `test/gear-advisor-loading.test.js`.
- **CALC-2: your own numbers in the calculators.** Alchemy, Enchanting and Spellmaking show "Using {character}: {skill} … — change" and editable skill, attribute and Luck fields; every field goes through `statNumber` (`lib/calculator-stats.mjs`: whole, 0 to 1000). Typed numbers are kept per tool by `typedStats` (same module) until "Reset to character sheet": a world switch keeps them (Alchemy, remounted per profile, reads them back), and the sheet sets only the fields not typed (owner, 30 September). CALC-1's `NO_RESULT` and one closed disclosure per tool still hold. `test/editable-calculator-skills.test.js`, `test/calculator-custom-stats.test.js`.
- **BLD-4: "Save this character" without an account.** `local-characters-panel.jsx` saves to `LOCAL_SAVES_KEY` and lists with load and delete; the Cloud Vault's local tab reads the same list through `loadLocalCharacters` (records only) and follows `silt-local-saves-changed`. Storage is read through `browserStorage()`, which is null where a browser blocks site data; names and fields show as text only. Loading checks the character with `sanitizeBuild`, keeps the visitor's world and the saved loadouts, and clears a loaded .omwsave. Keys stay distinct from the sign-in handoff and the active save. `test/local-character-save.test.js`, `test/local-save-review.test.js`.
- **Acceptance re-run (30 September): text contrast rules.** fg-16 and fg-17 are not for text (2.6 to 3.1:1 on the equipment panels); use fg-14 or lighter there. Do not fade text that is read (`opacity-*` on it or on its card): it measured below 4.5:1 on faction ranks and Travel stop labels. Every checkbox has a name (the Challenge objectives use their text). `test/acceptance-a11y.test.js`; the axe, keyboard and regression method is in docs/LAUNCH_VERIFICATION.md §5 item 4.
- **BLD-3: premade builds first for newcomers.** `character-builder-root.jsx` opens on the Premade Builds Catalog while `isNewcomer()` (`lib/builder-first-visit.mjs`: no `siltstrider-builder-visited`, no kept save, no saved characters; blocked storage is not a newcomer) and the context's `isStarter` (the character is still the untouched random start) both hold. It decides in the first render when opened from another page, and in effects when the page hydrates; a shared link, save or sign-in character that replaces the start switches it to the Custom Class Builder, and any tab or build the visitor picks stops the switching. The flag is written on the first mount. Change tabs through `chooseTab`, not `setActiveTab`. `test/builder-first-visit.test.js`.
- **HOME-1 / MOB-2: two equal first steps on Home.** `home-hero.jsx` renders `.home-steps`: "Start a character" (`.home-start`, to the Builder) then the save drop zone (`.home-save.home-step`), each with one primary button. They sit side by side where the column fits two 17rem cards and stack below that, in page order: the character first on phones, and for keyboards and screen readers everywhere. Do not reorder them with CSS (`order`, reversed flex). With a save loaded only its panel shows. The compatibility notice sits once under both steps, or inside the loaded panel. `test/home-hub-ui.test.js`.
- **SITE-4: the character's name opens the Builder.** Wherever a tool names the active character, use `<ActiveCharacterLink build={build} />` (`components/active-character-link.jsx`): the name from `lib/character-name.mjs`, the same as Home's card, then "· change"; `href="/builder"`, a plain click goes through `shell.navigate` (a full load would draw a new random start and lose an unsaved character), a modified click is left to the browser. Travel's link is its header's "Planning for" line, since the folded options' `<summary>`, which also names the character, cannot hold a link. Tests that load a tool through a hand-made import map register `test/helpers/active-character-link.cjs`. The legacy `.hidden { display: none !important }` in globals.css beats `sm:block` and the like, so "hide on phones" is `max-sm:hidden`; the Cloud Vault header's account line (`.cloud-vault-account`: name, tier, saves) was the last case and shows from 640 px (`test/cloud-vault-ui.test.js`). `test/active-character-link.test.js`.
- **SITE-3: nav order by use.** `PRIMARY_VIEWS` in `site-header.jsx` (the nav row and the phone menu) and `HOME_TOOLS` in `lib/home-data.mjs` (Home's cards and footer) lead with Character Builder, Level Simulator, Travel Planner, Alchemy. The phone tab bar is Home, Build, Level, Travel: Travel replaced Alchemy once TRV-4/5 led its phone layout with the journey (owner, 30 September); Alchemy is in the phone menu. `test/nav-order.test.js`.
- **MOB-1 / MOB-4: phone header and Builder sections.** Below 900 px the header is one row: `.brand` (taglines hidden), `.header-actions` (theme, search as an icon whose label is visually hidden, not `display: none`, and the account button, which leaves the row below 360 px) and then `.hamburger`, which now follows the actions in the markup so the keyboard order matches. Below 1024 px the Builder shows `.builder-phone-tabs` (Configure, Sheet, Loadouts, Premades; `aria-pressed`) instead of the three wide tabs and the Configurator / Character Sheet toggle; "hide on phones" there is `max-lg:hidden`, as the legacy `.hidden` rule beats `lg:grid`. `test/phone-layout.test.js`.
- **HOME-3: outcomes, not counts, on Home.** The strip under the hero reads `HOME_OUTCOMES` (`lib/home-data.mjs`): four fixed statements of what the site does for the character, the same in every world and state; no count of skills, restrictions or stops. Every claim there must stay true of the tools (the Level Simulator's ×5 plans, Travel's walking legs and fares, the Gear Advisor's sources). The values are words, so `.home-fact-value` scales with its tile (`cqi`) instead of wrapping. `test/home-hub-ui.test.js`.
- **CALC-3: one searchable box per Alchemy slot.** `components/calculators/alchemy/ingredient-combobox.jsx` (ARIA combobox with a listbox popup: `aria-activedescendant`, arrows, Enter or a click chooses, Escape or blur restores, a polite match count) replaces each slot's `<select>` and "Search..." field; the workstation passes the slot's pool (other slots' ingredients and the Slot 1 filter already applied) and keeps no search state. Matching is `rankOptions` in `lib/option-search.mjs` (name start, then word start, then anywhere). Tests that load the workstation through an import map register `test/helpers/ingredient-combobox.cjs`, whose `pickIngredient` types a name and presses Enter. `test/ingredient-combobox.test.js`.
- **CHL-2: one lock per rolled item.** The locks are only on the sheet, beside what they keep: `components/challenge-runs/lock-toggle.jsx` (`aria-pressed`, a fixed "Lock <item>" name) in the character card's race, class and birthsign rows (each with its Roll) and in the major objective, restrictions and minor objectives headers; a locked item's Roll is disabled. The configurator has no lock buttons: "Choose instead of rolling" pickers go through `chooseCharacterSlot` (`lib/challenge-choice.mjs`), which locks a choice and only unlocks on "Roll it"; a picker always lists the value its slot keeps. The race row shows the race alone (the race lock does not keep the gender). `test/challenge-locks.test.js` and app-shell's CHL-2 test.
- **Cloud Vault: a save's hash is checked on load.** `handleGetSave` (`cloudflare/routes/saves.mjs`) hashes the stored `packed_payload` (SHA-256, the same `computeSha256Sync` that wrote `payload_hash`) and compares it with `payload_hash`, in any letter case, before unpacking. A mismatch, or a stored hash that is not 64 hex digits, answers 422 `INTEGRITY_ERROR` with a plain message and a reference (a 5xx would become "please try again", which cannot help), sends nothing of the save, and logs only `{ event: 'save_integrity_failed', requestId, route }`. Loading and exporting both go through it. Tests at the end of `test/cloud-save-api.test.js`.
- **VAULT-TEST: signed-in Vault tests.** `scripts/local-stack.cjs` runs this checkout with `wrangler dev --local` from `wrangler.local.jsonc` (no routes, no account, a placeholder D1) and pages built into `.next-export-local` (Clerk development key from `.env.local`, passed with `--env-file`; live keys refused) or `.next-export-vault`; never deploy with that config or those folders. `scripts/test-vault.cjs` needs no Clerk: `CLERK_JWT_KEY` from a per-run key, a placeholder secret (Clerk's library wants one; with a JWT key it checks offline), and a `window.Clerk` stand-in installed before the site's scripts; `ensureClerk` returns any pre-set `window.Clerk` that is `loaded` or has `addListener` without `load`, so keep that. Its axe pass found the Vault card's Rename and Delete painted browser grey (plain buttons need `bg-transparent border-0`), an unnamed rename box, and an `h3` under the account page's `h1` (now an `h2`, sized by `.account-page .account-premium h2` so the settings panel's heading keeps `.account-page h2`). Commands: docs/BROWSER_TESTS.md, "Signed-in Cloud Vault". `test/local-stack.test.js`.

First verification command: `npm test` in the site repository.

## Accessibility and crash fixes from the second audit — 2026-09-29

No game-data schema changes. Site commits `93b7edf` through this entry; findings from re-running the Gemini audit (axe-core, keyboard, forced colors, adversarial inputs) against the 15:31 release. Invariants other agents must keep:

- **Character tables have no prototype.** `adaptCharacterCatalogs` builds races, classes, signs, spell lists and `specSkills` with `Object.create(null)`, so a shared build naming "constructor" or "__proto__" finds nothing instead of Object's built-ins (that crashed the whole app). Do not rebuild them as plain objects. `test/character-catalogs.test.js`.
- **The Ashfall focus ring is an outline** (2px accent, 2px offset), never a box-shadow: state rules clear box-shadow at higher specificity and Windows high contrast drops it. Do not add `outline: none` to a `:focus-visible` rule except the text-field rule, and keep the forced-colors block last in `app/theme-ashfall.css`. `test/a11y-focus-and-state.test.js`.
- **Overlays are dialogs.** Anything that covers the page uses `useModalDialog` (`components/use-modal-dialog.js`) on an element with `role="dialog"`, `aria-modal="true"`, `aria-labelledby` and `tabIndex={-1}`: focus in, Tab wraps, Escape closes, focus returns. A layer opened on top (Clerk sign-in from inside the Cloud Vault, the search palette) keeps the keyboard. `test/modal-dialog.test.js`.
- **Tool headings live in `<main>`.** `lib/view-headings.mjs` holds each tool view's sr-only h1; `AppShell` renders it first inside `<main>` for the view on screen. Pages must not render their own h1. Unknown addresses use `app/not-found.jsx`.
- **Security headers** for pages and assets are in `public/_headers` (nosniff, frame denial, referrer policy, host-only HSTS). No `script-src` policy until Clerk and the analytics beacon are tested against one. `/api/*` responses come from the Worker and are unaffected.

Left for the UX pass, with the same audit as its acceptance test: text contrast of `fg-13`–`fg-15` on the panels they sit on (Faction Journal, Equipped Loadouts, premade catalog, Challenge), the Level Simulator's 20px attribute buttons, heading levels on the Level Simulator and Vault, focus moving into header menus on open. The Cloud Vault never checks a save's stored SHA-256 on load (low risk).

First verification command: `npm test` in the site repository, then `npm run build:cloudflare`.

## Licences — 2026-09-29

No game-data schema changes. The site is `AGPL-3.0-or-later` and the pipeline `GPL-3.0-or-later`: `LICENSE` in each repository, a Licence section at the end of each README, and `"license"` in the site's `package.json`. Invariants other agents must keep:

- **The licence covers the code only.** Never add game or mod data to either repository beyond the pipeline's existing `items/examples/` excerpts; the data bundles stay generated and uncommitted. The Pelagiad font keeps the SIL OFL 1.1 (notice in `app/globals.css`), and the Silt Strider name, logo and social card are not licensed for reuse.
- **Dependencies must stay compatible.** New runtime dependencies need a licence that can be combined with the AGPL or GPL (MIT, BSD, Apache-2.0, ISC, LGPL, GPL-3.0 are fine); ask the owner before adding anything proprietary, source-available, or GPL-2.0-only.
- **"Open source" means the code.** Public wording (About, structured data, launch posts) may say open source and name the licence, never that the game or mod data is. `test/license.test.js` checks the licence file, the README exclusions and `package.json`.

First verification command: `npm test` in the site repository.

## Launch fixes: cookies, Worker routing, sign-in handoff — 2026-09-29

No game-data schema changes. Site commits `5bd4e04` through `29cadd8`. Invariants other agents must keep:

- **Only `/api/*` runs the Worker.** `wrangler.jsonc` `assets.run_worker_first` is `["/api/*"]`; pages, scripts and game data are served by the asset store and do not count against the Workers request allowance (about 18 requests for a first visit to `/builder` used to). `www` pages are redirected by the zone's Redirect Rule "www to root" (wildcard `https://www.siltstrider.tools/*` → `https://siltstrider.tools/${1}`, 301, query preserved); the Worker's own redirect covers `/api/*` on `www`. `request_failed` logs and error references cover API failures only. `test/worker-routing.test.js` holds the config. See `docs/DEPLOYMENT.md`.
- **Clerk loads on demand.** Loading Clerk sets its cookies, and the Privacy Policy says a visit without signing in sets none. On mount, call `ensureClerkIfSignedIn()` (it loads Clerk only when `hasClerkSession()` finds Clerk's `__client_uat` above 0); call `ensureClerk()` only from a user action such as Sign in. `AccountProvider` and the Cloud Vault attach through the `silt-auth-ready` event when Clerk loads later.
- **Sign-in keeps the builder's character.** Google and Discord sign-in reloads the page, which reset an unsaved character to the default (a TR + ARCE Khajiit was saved as the default Dark Elf). Every sign-in button must dispatch `SIGN_IN_EVENT` (`silt-before-sign-in`, `lib/sign-in-handoff.mjs`) before opening Clerk. `CharacterProvider` keeps the character in the tab's session storage and restores it once on a signed-in return within 15 minutes; `AccountProvider` drops it when an email sign-in completes on the page. A loaded OpenMW save is not kept (it survives reloads already), and a shared build link still wins.
- **Privacy wording.** The Privacy Policy has "Cookies, local files and browser storage" (no advertising or tracking cookies; Clerk's only once you sign in; Cloudflare Web Analytics without cookies or storage) and its own date (September 29; Terms keep theirs). Structured data must not promise that nothing leaves the browser: `test/seo-workstations-h1-metadata.test.js` checks all of it.
- **Data.** A full D1 backup was taken and restore-checked on 29 September (encrypted, in the owner's storage). The three cloud saves in SLT1 envelope version 1 were deleted by the owner.

Assessment of the Antigravity verification, open issues and read-only checks: `docs/LAUNCH_VERIFICATION.md`. Launch post copy with claims checked against the live site: `docs/LAUNCH_POSTS.md`.

First verification command: `npm test` in the site repository, then `npm run build:cloudflare`.

## Launch notice and operations preparation — 2026-09-28

Site changes add the shared OpenMW-only / vanilla, TR and TR + ARCE compatibility notice at both importers and About, a bug-report email template in the footer/About, and Worker 5xx reporting with user-visible reference IDs. Wrangler observability is configured with query redaction, custom failure logs, and sampled traces; it takes effect only when deployed. No game-data schema, equipment optimizer, or save-format changes. Recovery procedures are in `docs/LAUNCH_OPERATIONS.md`: production D1 Time Travel was checked and a schema-only export restored locally; no full private-data export, production restore, or rollback was performed. Automatic approval review declined the full private-data export; the owner can run the documented backup command.

First verification command: `npm test` in the site repository, then `npm run build:cloudflare`. At preparation, 558 tests passed, zero failed, and the existing TR gear benchmark remained TODO pending new data. Home/vault/About checks passed in both themes at desktop/mobile widths, as did the Worker deployment dry run. These checks do not replace the final frozen-code-and-bundle acceptance pass after Claude's equipment work and Discord setup. This preparation is not yet deployed. Rechecked the same day after the equipment release (`7e72528`, bundle `3da03202`): 559 tests pass with the TR gear benchmark enforced, and the Cloudflare build and Worker dry run pass; the equipment work is finished, so the acceptance pass can use that bundle. Still for the owner: Discord in Clerk, the full D1 export, and the production sign-in and cloud-save checks.

## Build-aware gear ranking and two rings — 2026-09-28

Additive to gear-row schema 1.0.0 (`contracts/gear-rows-types.ts`). Clothing rows answering `power` carry `candidates`, a shortlist of at most 40 picks: what the row chose, the blank piece with the most room, and for each effect (attribute or skill, constant apart from charged) the piece carrying the most of it, close and far apart. Each enchantment effect carries its own `worth` and `value`. Pipeline `2dc71d0`, site `32e7fa2` (majors before minors for weapon and armour), `72bdb15` (benchmark), `e236b1f` (ranking).

Site: `lib/build-traits.mjs` reads a build with the leveler's `detectArchetype`, counts a caster by casting schools (two per major, one per minor, four or more), and weighs each effect for the build. The Gear Advisor merges each slot from the shortlists, offers a second, different ring (`slotKey: ring_2`, equipped on the right hand), and notes why a piece suits the build. Rows without shortlists rank as before. `test/gear-benchmark.test.js` requires every caster class and a custom caster to be shown Mentor's Ring; TR is TODO until the staged rows carry shortlists, then it is enforced.

Rebuild before release: `python build_gear_rows.py` (about 20 minutes per profile), then the bundle and `npm run data:stage`. First verification command: `npm test` in the site repository; the TR benchmark must pass, not stay TODO.

## Current-only site contract — 2026-09-28

The user authorized removal of pre-release compatibility. Site sharing uses canonical paths and query parameters; hash aliases are retired. The SLT1 envelope now requires format version 2 and all snapshot sections; original OpenMW import remains supported. No game-data catalog schema changed. Standalone index.html, archive/legacy, global catalog hooks and the prototype test API were removed; database history and stored rows were not modified. Migration 0006 is prepared but not applied: production saved_characters was verified empty, and the migration refuses populated tables before removing it. First verification command: `npm test` in the site repository, then `npm run build:cloudflare`. Old version 1 cloud payloads need reimport from the original OpenMW save after deployment.

Three agents work on Silt Strider in parallel. This file is identical in both
repositories. If you change it, change both copies in the same session.

## Agent specialties (shared ownership during the release sprint)

| | Antigravity (UI Lead) | Codex (Site Agent) | Claude (Data Agent) |
| --- | --- | --- | --- |
| Repository / Focus | Architecture, Design & Specs (`UI_TRANSFORMATION.md`) | Web Application (`lowgraph/siltstrider.tools`) | Data Pipeline (`lowgraph/openmw-decompiler`) |
| Specializes in | UI/UX specifications, design tokens, component hierarchy, CRPG aesthetic standards | Next.js 16 App Router, React 19, Tailwind CSS, UI implementation, Clerk, `cloudflare/`, D1 routes & migrations | Extraction, catalogs, policy, gear rows, rules library, engine dumps, app bundle publication |
| Reads | User feedback, in-game references (`Char Creation.png`), legacy runtime | `UI_TRANSFORMATION.md`, `public/game-data/`, legacy workbench | Plugin files, OpenMW engine dumps, local staging workspace |

**Coordinate shared work.** Any agent may implement and commit launch-checklist work in either repository. Claim the item before starting, preserve concurrent changes, and keep application and extraction code in their respective repositories.

## The contract is the bundle

The site consumes `public/game-data/<bundleId>/`: a content-addressed, hash-verified
release described by `manifest.json` and selected by `current.json`. It is the only
interface between the two halves. The site never reads `world.sqlite`,
`acquisition.sqlite`, `services.sqlite`, `journal.sqlite` or `game-data.sqlite`.

`bundle-types.ts`, `catalog-types.ts`, `policy-types.ts` and `gear-rows-types.ts`
live in the data repository and are the written form of that contract. At runtime
the manifest is the real contract and `lib/bundle-loader.mjs` validates it, so drift
cannot ship silently — but keep the two in step deliberately, not by luck.

## What the loader accepts and rejects

Measured against the real bundle, not assumed:

```
ACCEPTS   extra field on every record
ACCEPTS   extra top-level field in a payload
ACCEPTS   extra field in the manifest

REJECTS   schemaVersion bumped          -> "manifest version/snapshot mismatch"
REJECTS   catalog declared, not emitted -> "missing/ambiguous catalog <name>"
REJECTS   record count drift            -> "record count mismatch"
```

So: **additive changes to schema 1.0.0 are safe and need no site change.** A new
catalog ships for free provided it is emitted for every profile, and stays inert
until the site adds it to `FEATURE_CATALOGS`. Everything else is breaking, fails
loudly at staging with a readable message, and requires a version bump agreed on
both sides in the same session.

`test/bundle-contract.test.js` in the site repository pins these outcomes, so a loader
change that tightens validation is caught here before it blocks a data release. It also
asserts the case the data side depends on most: **a wholly new catalog loads with no
site change**, provided every profile emits or inherits it.

## The pin

`npm run data:stage` validates every hash and reconstructs every delta before it
switches `current.json`. Until someone runs it, the site keeps serving the release it
already has. A rebuild on the data side therefore cannot break a working site by
accident — which is what makes parallel work safe rather than merely possible.

Every artifact carries the `snapshotId` it came from and refuses to mix revisions.
Keep that property in anything new.

## Operational Guardrails & Quality Protocols

### 1. Shell & Environment Invariants (CRITICAL)
* **PowerShell Only:** Never emit bash chained operators (`&&`). Always use PowerShell command separators (`;`) or execute statements sequentially.
* **Temp Isolation:** All temp fixtures, artifacts, and test caches must strictly reside in `A:\Cache`. Always prefix pipeline test invocations with:
  `$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"`
* **Scratch & Secret Isolation:** Never stage scratch files (e.g., `<scratchDir>/capture-*.js`), `Char Creation.png`, or `Hey.html`. Always clean up temporary CDP runner scripts after visual evaluation.

### 2. Repository Architecture & Shared Ownership
* **Shared Sprint Ownership:** Any agent may edit either repository for launch-checklist work; keep site implementation in the site and extraction logic in the pipeline.
* **Contract Sync:** Changes to game parsing outputs or schemas pass exclusively via exported JSON bundles to `public/game-data/` and synchronized updates to `COORDINATION.md` and `UI_TRANSFORMATION.md`.
* **Legacy HTML Extraction (Retired):** The former prebuild hook (`extract:legacy`) was retired in Phase 13; the application is fully native React. `index.html` is retained strictly as a regression fixture for `test/site.test.js` and `archive/legacy/scripts/dev-server.cjs`.

### 3. Verification & Adversarial QA Protocols
* **Pipeline Tests (233 suites):** Must pass cleanly with zero uncaught warnings. Output should be summarized; do not flood context with raw passing test logs.
* **Site Tests (155 suites) & CDP Screenshots:** Run `npm test` in `A:\Claude\morrowind-tools`. For UI modifications, execute headless visual capture via Chrome CDP on port 8765 (`node <scratchDir>/capture-*.js`) to confirm layout integrity before ticket completion.
* **Adversarial Edge Cases:** Do not approve schema/logic changes on baseline tests alone. Before marking a logic task complete, write at least 3 automated tests targeting edge conditions (malformed record tags, missing SQLite indices, null/undefined properties, or boundary values).

### 4. Two-Failure Revert & Escalation Policy
* If an automated test fails twice consecutively during a fix attempt:
  1. Immediately abort code edits.
  2. Revert only the task's own specific changes (e.g. via targeted patch/hunk reversal or `git checkout -p`). Whole-file restore (`git restore <file>` / `git checkout -- <file>`) is permitted ONLY when that file contains no other concurrent modifications from other agents or tasks. Never perform blanket rollbacks (`git restore .` / `git checkout .`).
  3. Emit a concise root-cause analysis showing the failing stack trace and the exact breaking invariant.
  4. Stop and request a `/boost` escalation run. Do not accumulate speculative patches.

### 5. Handoff & Synchronization
* Keep `COORDINATION.md` and `UI_TRANSFORMATION.md` identical across both repositories.
* When completing a batch or milestone, update `COORDINATION.md` with:
  - Exported dataset schema changes.
  - Invariants assumed by the downstream Next.js / legacy JS runtime.
  - Exactly which script/command the next agent must run first.

## Current split of work

**Antigravity (UI Transformation Lead)**

1. Maintain and evolve `UI_TRANSFORMATION.md` roadmap.
2. Review site UI implementation against CRPG design system and responsive mobile standards.
3. Completed Phase 1 through Phase 11: Two-Pane Character Builder, Skill Matrix, Cross-Tool State, Challenge Runs Overhaul, 4 Specialized Workstations, Level Simulator & Build Progression Optimizer, Cloud Character Vault & OpenMW Binary Save Ingestion, Home Hub & Tool Directory Overhaul, Equipped Loadouts & Equipment Inspector, Bundle Rewiring & Live Game-Data Integration, and Faction Journal & Promotion Deficit Engine.
4. ~~Phase 12: Modern App Shell & Architecture Decoupling~~ **Done.** (Phase 12A Pure Permalink Codec & Shell State Engine, Phase 12B Static Views & Challenge Engine Decoupling, Phase 12C Native AppShell Layout Mounting & Asset Ingestion, and Phase 12D Legacy Extraction Deprecation & Test Re-anchoring).
5. ~~Phase 13: Legacy Cleanup & Architecture Archival~~ **Done.** Cleaned up and archived obsolete transition harnesses into `archive/legacy/`, decoupled entry points, and bundled styling natively.

**Codex (Site agent)**

1. ~~Execute Phase 1-9 UI transformations specified in `UI_TRANSFORMATION.md`.~~ **Done.**
   All interactive workstations, the Home Hub, and Equipped Loadouts Inspector (Character Builder, Challenge Runs, Enchanting, Spellmaking, Alchemy, Travel, Level Simulator, Cloud Character Vault, Home Hub, Equipped Loadouts & Inspector) are fully implemented, verified via CDP, and covered by 247 passing unit tests.
2. ~~Rewire legacy calculators to the loader and complete remaining bundle integrations (Phase 10).~~ **Done.**
   All 4 specialized workstations (Enchanting, Spellmaking, Alchemy, Travel) and Gear Advisor now connect directly to `useGameData` / `FEATURE_CATALOGS` (`travel`, `enchanting`, `spellmaking`, `alchemy`, `gear`) with live status indicators and graceful fallback to static tables.
3. ~~Build the three-toggle UI: steal early gear, endgame gear early, near starting areas.~~ **Done.**
   Added `#gear-near-start` toggle in legacy `index.html` and synchronized in React `gear-advisor.jsx` with full 3-toggle policy resolution matching `GearRows`.
4. ~~Implement Faction Journal & Promotion Deficit Engine (Phase 11).~~ **Done.**
   Added `components/journal-factions/` (`JournalFactionsRoot`, `FactionRoster`, `FactionDetailView`), `lib/faction-math.mjs`, `FEATURE_CATALOGS.factions`, mounted in `#panel-factions`, registered across header dropdown/mobile drawer/Home Hub directory (9 canonical tools), verified with 262 passing site test suites, zero byte budget regression (48,906 bytes < 50,000 budget), and verified via headless Chrome CDP.
5. ~~Wire Best-In-Slot bundle and late-game gear advisor recommendations.~~ **Done.**
   Added `bestInSlot: Object.freeze(['BestInSlot','Armor','Clothing','Weapons'])` to `FEATURE_CATALOGS` in `lib/bundle-loader.mjs`, implemented client-side scoring engine in `lib/best-in-slot.mjs` (pre-computed build picks + dynamic custom build scoring with drawback severities and beast race filters), created `components/character-builder/best-in-slot-view.jsx`, wired `useGameData('bestInSlot')` into `GearAdvisor`, and verified across 275 passing tests (including 3 adversarial QA tests in `test/best-in-slot.test.js` reading `public/game-data/current.json`).
6. ~~Repoint `scripts/stage-game-data.mjs` away from its `A:/Cache/OpenMWBundlePreview`
   default to `A:/Cache/OpenMWFoundation/app-bundle`.~~ **Done.**
7. ~~Commit or delete the untracked `lib/character-catalogs.mjs`.~~ **Done.** Tracked and committed.
8. ~~D1 schema and routes for journal progress, equipped loadouts, known spells and
   saved challenges.~~ **Done.** Implemented dual-format SLT1 binary codec (~96% compression) and fallback JSON in `cloudflare/schema.sql`, `cloudflare/routes/saves.mjs`, and `cloudflare/routes/entitlements.mjs`.
9. ~~Phase 12A - Modern App Shell & Architecture Decoupling: Pure Permalink Codec & Shell State Engine.~~ **Done.**
   Implemented pure ESM `lib/permalink-codec.mjs`, modernized `components/shell-context.jsx`, and authored comprehensive unit and adversarial QA tests (`test/permalink-codec.test.js`).
10. ~~Phase 12B - Modern App Shell & Architecture Decoupling: Static Views & Challenge Engine Decoupling.~~ **Done.**
     Implemented native modern React components `components/views/about-view.jsx` and `components/views/changelog-view.jsx`, extracted pure ESM challenge generation engine `lib/challenge-engine.mjs`, and authored comprehensive unit and adversarial QA tests (`test/challenge-engine.test.js`).
11. ~~Phase 12C - Modern App Shell & Architecture Decoupling: Native `AppShell` Layout Mounting & Asset Ingestion.~~ **Done.**
     Implemented `components/app-shell.jsx`, `components/site-footer.jsx`, ingested Pelagiad font and procedural 9-slice textures into `public/fonts/` and `public/textures/`, updated `app/globals.css`, switched `app/page.jsx` to render `AppShell`, and authored unit/adversarial QA tests in `test/app-shell.test.js` (297 tests passing).
12. ~~Phase 12D - Modern App Shell & Architecture Decoupling: Legacy Extraction Deprecation & Test Re-anchoring.~~ **Done.**
     Retired `scripts/extract-legacy.cjs` from `predev` and `prebuild` hooks in `package.json`, removed `manifest.json` dependency from `app/page.jsx`, verified Next.js production build succeeds cleanly (788ms compile time), and verified all 297 site tests pass.
13. ~~Phase 13 - Legacy Cleanup & Architecture Archival.~~ **Done.**
     Archived legacy adapters (`components/legacy-workbench.jsx`), extraction and dev scripts (`extract-legacy.cjs`, `connect-character-runtime.cjs`, `connect-alchemy-runtime.cjs`, `dev-server.cjs`), and migration bridges (`shell-bridge.js`, `character-bridge.js`) into `archive/legacy/`. Ingested baseline styling into native `app/legacy-compat.css`, removed `/legacy/legacy.css` link from `app/page.jsx`, decoupled `scripts/build-cloudflare.cjs`, cleaned `public/legacy/` from disk, and verified all 297 site tests pass.


**Claude (Data agent)**

1. ~~Ship gear rows through the bundle as a `GearRows` catalog.~~ **Done.**
   `build_app_bundle.py` publishes them automatically, keyed per row, with the policy
   that produced them travelling as payload fields.
2. ~~The rules library.~~ **Done.** `build_rules_library.py` derives targeting,
   no-magnitude and no-duration from content usage and ships them as the `EffectRules`
   catalog, with the spell cost formula's engine literals authored alongside.
3. ~~The travel graph as a shipped catalog, from `services.sqlite`.~~ **Done.** Shipped via `Travel` and `Places` catalogs in the app bundle.
4. ~~Merchant barter pricing, for "gold price per merchant".~~ **Done.** Shipped via `Merchants` catalog in the app bundle.
5. ~~The 326 journal topics with no resolvable title.~~ **Done.** Titles resolved and published across quest and topic journal records.
6. ~~Save import for OpenMW `.omwsave`, format v37.~~ **Done.** Client-side ESM parser `lib/omwsave-parser.mjs` extracts character attributes, skills, dynamic vitals, inventory, quests, cell, and gold directly in the browser.
7. ~~Publish BestInSlot catalog and resolve UTF-8 em-dash name encoding.~~ **Done.**
   Rebuilt BestInSlot catalog with correct UTF-8 encoding for em-dash keys (`\u2014`), published active bundle `6e0a65192ebad50ce66c117b` referenced by `public/game-data/current.json`.
8. ~~Open a real `.omwsave` in the site, not only in the vault.~~ **Done, in the site repository at the user's request.**
   Codex, these are your files; nothing else about them changed. Tested against seven modded Total Overhaul saves (TR profile, custom class, levels 1\u20134).
   - `lib/omwsave-parser.mjs`: additive `identity.gender` (NPC_ `FLAG` bit 0) and `identity.class.specialization` / `favoredAttributes` (CLAS `CLDT`).
   - `lib/cloud-save-codec.mjs`: SLT1 gains an optional trailing section (gender, specialization, favoured attributes). `FORMAT_VERSION` stays 1; old payloads decode with those fields `null` / `[]`.
   - `lib/omwsave-import.mjs` (new, pure): `profileForSave`, `buildFromSave`, `sheetFromSave`, `rulesCheck`, `loadoutFromSave`. Unknown mod classes, races and signs keep the current build's value and are listed, never replaced by defaults.
   - `components/character-context.jsx`: `loadSave(save)`, `clearSave()`, `activeSave` (in memory only; a reload clears it). The vault's `OPENMW_SAVE` branch and a new sign-in-free "Open a Save" file input (`components/character-vault/open-save-panel.jsx`) both go through `loadSave`.
   - Readers of `activeSave`: `SaveImportNotice` in the builder, the Equipment Studio ("Worn by <name>" loadout, the save's own skills and attributes), the Level Simulator ("Plan from: the save / the build") and the Journal (factions and quests from the save).
   - `test/omwsave-import.test.js` uses a synthetic save; three codec fixtures gained the new identity fields.
9. ~~Front page and nav: lead with the save, weight the tools by use.~~ **Done, in the site repository at the user's request.**
   Antigravity, Codex: a layout change in your files, from the user's UX review.
   - Hero (`components/home-hub/`): two equal first steps, "Start a character" and then the save drop zone (`home-save-drop.jsx`; HOME-1 / MOB-2 above); a file dropped anywhere on the page opens too. The world picker (`home-worlds.jsx`, now compact) follows them, under the compatibility notice. The Challenge Runs link and the bottom "Choose your Morrowind" section are gone. With a save loaded, the character card shows the save.
   - Tool grid: Build Optimizer and Level Simulator, then Alchemy and Travel at equal weight (Alchemy has a live brew-chance preview), then Enchanting, Spellmaking and Faction Journal; Challenge Runs and Cloud Vault are a slim row with no preview.
   - Header (`components/site-header.jsx`): the nav row is Build Optimizer, Level Simulator, Alchemy, Travel, Faction Journal; Challenge Runs moved to More; Calculators holds Enchanting and Spellmaking; the Cloud Vault is an account button (`.vault-trigger`) after search. Phone tabs: Home, Build, Level, Alchemy, Menu.
   - `lib/omwsave-import.mjs` `readSaveFile(file)` is the one path for picked and dropped saves (the vault uses it too); it refuses a Morrowind.exe `.ess` by name.
   - Styles in `app/globals.css` and `app/theme-ashfall.css`, both themes.
10. ~~Nine fixes from the user's testing.~~ **Done, in the site repository at the user's request.**
    - `components/challenge-run-context.jsx` (new): `ChallengeRunProvider` in `app-shell.jsx` holds the run, locks and roll settings above the views, stores the run (`silt-challenge-run`) and the preferred settings (`silt-challenge-settings`), and opens `#challenge&run=` links.
    - `lib/challenge-engine.mjs`: `generateSeededRun`, `formatRunSeed` / `parseRunSeed` (seeds carry world, bands and counts: `K7Q2M-TR-EM-R3O2`), `sanitizeRun` for links, `GRIND_MAJORS` banding of "Reach level 50".
    - `lib/permalink-codec.mjs`: Web base64 APIs before `Buffer`; the browser's Buffer polyfill has no `base64url`, so links failed in browsers only.
    - `lib/bundle-loader.mjs`: the `gear` feature also loads `GameSettings` (for `fEnchantmentMult`). Additive; a bundle without it fails `loadFeature('gear')`, as for any feature catalog.
    - `window.siltShell` and `window.writeShareHash` are never set since Phase 13: buttons that used them now use the shell context. The remaining `window.siltShell` fallbacks in the vault are unreachable.
    - Header: the world switch has three buttons, `#react-world-vanilla`, `#react-world-tr`, `#react-world-arce`; `#react-arce` is gone.
    - Build links: `generateBuildShareUrl` (`lib/character-vault.mjs`) goes through the codec, and `sanitizeBuild` guards `#builder&build=` links, which `character-context.jsx` now opens. Links carry the character, not loadouts.

## Asking across the boundary

State the request as a contract change, not a task. Name the catalog or field, say
whether it is additive, and give the shape. The other side decides how to implement
it. If a change is breaking, both sides bump and land it together — never one alone.

When either side finishes something the other can use, say so explicitly with the
artifact name. Silence reads as "not ready yet".

## Alchemy correction, 23 September 2026

No exported schema change. The site's alchemy feature now also requires the existing
EffectRules catalog. Native alchemy joins rules by canonical effect ID, preserves
attribute/skill targets and effect-slot order, and passes catalog GameSettings into
OpenMW 0.51.0 potion calculations. Missing rules/settings block calculation. Profile
changes remount the workstation and clear ingredients/apparatus; no static fallback
is presented as live data. The retired AlchemyDataBridge is no longer mounted.

Next agent: first run `npm test` in `A:\Claude\morrowind-tools`, then `npm run build`.
Browser visual verification remains pending because automatic browser approval review
reported a usage-limit failure. No extraction or bundle rebuild is required.

## Portfolio presentation, 23 September 2026

The site README now leads with the product, human contribution and disclosed AI
assistance, current native React architecture, source evidence, setup, and limitations.
`docs/CASE_STUDY.md` documents acquisition representation and alchemy integration
tradeoffs; `docs/DEMO.md` provides a five-minute walkthrough and release checklist.
Old migration/backend setup notes are explicitly marked historical. No dataset schema
or runtime invariant changed in this documentation batch. Next agent: first run
`npm test` in the site repository, then `npm run build`; rehearse and visually verify
the intended release before adding screenshots or claiming deployment readiness.


## Native JavaScript cleanup, 27 September 2026

No exported dataset or schema changes. The production React app no longer loads
legacy-data/legacy-runtime scripts, reads legacy catalog or shell globals, or
synchronizes retired character/calculator DOM controls. Calculator stat ingestion
uses React state; vault session tokens come directly from Clerk. Unused calculator
HUD and alchemy bridge components were removed, with their obsolete tests replaced
by native state isolation tests. Current catalog service events and old permalink
formats remain supported. Shared legacy CSS and the historical index.html fixture
remain for a separate styling migration and regression coverage.

Validation: 482 site tests passed; final calculator/isolation checks and static
build passed. Browser checks rendered all 13 views without JavaScript errors or
legacy script requests, exercised stat ingestion and travel selections, and checked
desktop/mobile screenshots. No deployment in this batch.

Next agent: first run `npm test` in `A:\Claude\morrowind-tools`; next phase is
legacy CSS consolidation with visual checks. No extraction or bundle rebuild.


## Stylesheet consolidation, 27 September 2026

No schema, bundle, or extraction changes. Shared styles are consolidated in
app/globals.css; app/legacy-compat.css and its root import are removed. Retired
control selectors and duplicate definitions were pruned while preserving cascade
order, Pelagiad licensing, dynamic vital classes, and active Ashfall grouped
selectors. Theme overrides still load last. Combined CSS source shrank by about
24 KB. The full suite passed (485 tests before the final additional grouped-selector
guard), followed by 9 passing stylesheet/token checks and a successful static build.
All 52 screenshots (13 views, two themes, desktop/mobile) match the baseline
pixel-for-pixel, with no browser errors or horizontal overflow.

Correction to the earlier JavaScript audit: gear-advisor.jsx and
local-characters-panel.jsx still contain legacy DOM bridges. They were discovered
while tracing stylesheet references and are not removed in this styling batch.
The old runtime remains unloaded. Next agent: first run `npm test`, then inspect
those two builder components and remove their remaining DOM hooks while preserving
native gear recommendations and local save behavior. No extraction is needed.
Changes remain local; nothing was deployed in this batch.


## SEO architecture and multi-route static shells, 27 September 2026

No exported dataset or schema changes. Implemented Phases 1-3 of the SEO architecture plan:
1. Phase 1: High-intent metadataBase (`https://siltstrider.tools`), OpenGraph social preview (`/og-image.png`), Twitter cards, JSON-LD `WebApplication` schema, semantic `<h1>` hero hierarchy, keyword-enriched tool descriptions in `lib/home-data.mjs`, static crawler endpoints `app/robots.js` and `app/sitemap.js`.
2. Phase 2: Engine mechanics and formula documentation in `AboutView`, semantic `<h2>` workstation headings across Alchemy, Spellmaking, Enchanting, and Travel, and exact OpenMW 0.51 engine microcopy.
3. Phase 3: Dedicated static page route shells (`app/builder`, `app/leveler`, `app/alchemy`, `app/travel`, `app/enchanting`, `app/spellmaking`, `app/factions`, `app/challenge`, `app/vault`, `app/about`, `app/changelog`), allowing individual search engine indexation for each tool. Extended `lib/permalink-codec.mjs` and `components/shell-context.jsx` with `defaultView` and `initialView` props to prerender the target workstation on static export without hash dependency, while retaining 100% SPA state preservation and permalink backwards compatibility. Document access in `gear-advisor.jsx` guarded for SSR prerendering. Updated `app/sitemap.js` with all 14 canonical URLs.

Validation: 510 site tests passed (`npm test`); 498 pipeline tests passed; static production build (`npm run build`) and Cloudflare export build (`npm run build:cloudflare`) succeed cleanly (18/18 static routes prerendered).

Next agent: first run `npm test` in `A:\Claude\morrowind-tools`. No extraction or bundle rebuild required.



## Final builder DOM bridges removed, 27 September 2026

No schema or data changes. Gear Advisor no longer reads/writes legacy controls,
calls global optimizers, observes #gear-box, or injects its HTML. Native bundle
results show independent early/late loading and failure states with retries.
The local-characters panel no longer relocates old DOM nodes; its existing
silt-open-vault event still opens the native vault. Browser storage is untouched.
Concurrent Dark Brotherhood and gear-source improvements were preserved.

Validation: 522 tests passed and static build succeeded. Browser verification
covered optimization, two-handed selection, equipping early and late recommendations,
and opening the native vault; no JavaScript errors. Desktop gear and mobile vault
screenshots were inspected. Next agent: first run `npm test`; review the task's
explicit files before committing because other work shares this checkout.
No commit, push, deployment, extraction, or bundle rebuild in this batch.


## Cloud-save identity labels, 27 September 2026

No schema or extraction changes. OpenMW vault cards use lib/vault-identity.mjs to
resolve raw race/sign IDs case-insensitively against Races/Birthsigns. Save headers
have no profile field, so only unambiguous names across the three published profiles
are displayed; the selected builder profile is not used. Unknown/conflicting IDs
and unavailable catalogs retain their original values. Requests are shared per
bundle loader; full save payloads are not fetched, and stored values are untouched.

Validation: 525 tests and production build passed. Browser verification with
synthetic headers and real catalogs displayed Chimeri-Quey / The Atronach, retained
unknown IDs after switching cards, and made no save API requests. Next agent: run
`npm test` before release. No deployment or migration in this batch.

## Clean HTML5 path routing and hash migration, 27 September 2026

No exported dataset or schema changes. Transitioned workstation and tool navigation from URL hash fragments (`#builder`, `#alchemy`, `#travel`, etc.) to clean HTML5 History API path routing (`/builder`, `/leveler`, `/alchemy`, `/travel`, `/enchanting`, `/spellmaking`, `/factions`, `/challenge`, `/vault`, `/about`, `/changelog`):
1. Shell routing engine (`components/shell-context.jsx`):
   - `shell.navigate(view)` now invokes `window.history.pushState({ view }, '', targetPath)` (with `/` for home, `/${view}` for tools) and dispatches `silt-shell-change`.
   - Listens to browser `popstate` events to provide seamless native browser Back and Forward history traversal across workstations.
   - Legacy hash migration: automatically replaces incoming legacy hash fragments (e.g. `/#builder`, `/#TR`, etc.) via `window.history.replaceState` into canonical pathnames, stripping `#`.
   - Backward compatibility for permalink payloads: preserved full support for `#builder&build=...`, `#challenge&run=...`, and query string variants (`?build=...`, `?run=...`), decoding them cleanly on arrival.
2. Link and anchor elements:
   - Updated header brand link (`components/site-header.jsx`) to `href="/"`.
   - Updated tool grid cards (`components/home-hub/home-tools.jsx`), colophon links (`components/home-hub/home-colophon.jsx`), and footer links (`components/site-footer.jsx`) to clean pathnames (`/about`, `/changelog`, etc.) with SPA event prevention where appropriate.
   - Updated permalink share URL generators in `character-builder-root.jsx` and `challenge-runs-root.jsx` to build clean origin URLs.
3. Codec and state parser updates (`lib/permalink-codec.mjs`):
   - `decodeShareHash` and `profileFromLocation` accept clean pathnames, full URLs, query strings, and legacy hashes.

Validation: 533 site tests passed (`npm test` in `A:\Claude\morrowind-tools`); 555 pipeline tests passed (`python -B -m unittest` in `OpenMW Decompiler`); static production build (`npm run build`) and Cloudflare static export (`npm run build:cloudflare`) succeed cleanly (18/18 static pages prerendered). Automated test suite directly verifies popstate Back/Forward browser traversal, legacy hash auto-migration (`/#TR`, `/#ARCE`, `/#alchemy`), and clean query permalink payloads.

Next agent: first run `npm test` in `A:\Claude\morrowind-tools`. No extraction or bundle rebuild required.

## Workstation SEO Realignment, Deep Structured Data & Thin-Content Mitigation, 27 September 2026

No exported dataset or schema changes. Implemented the complete 3-phase SEO optimization sequence:
1. Workstation `<h1>` Realignment: Injected semantic `<h1 className="sr-only">{Page Title}</h1>` across all 11 tool routes (`builder`, `leveler`, `alchemy`, `travel`, `spellmaking`, `enchanting`, `factions`, `challenge`, `vault`, `about`, `changelog`), establishing proper single-h1 page hierarchy for search engine crawlers without disturbing inner `<h2>` component headings or visual layout.
2. Route-Specific Social Cards: Added `twitter: { card: 'summary_large_image', title, description, images: ['/og-image.png'] }` to all 13 route files (tools + legal pages).
3. Deep Structured Data: Added `TOOL_SCHEMAS`, `getToolJsonLd(view)`, `TOOL_FAQS`, and `getToolFaqJsonLd(view)` to `lib/seo-breadcrumbs.mjs`. Injected Schema.org `WebApplication` schemas (with comprehensive `featureList`) and `FAQPage` rich snippets on key tool routes (`leveler`, `alchemy`, `enchanting`, `travel`, `about`).
4. Thin-Content Mitigation: Enriched `app/alchemy/page.jsx` with an accessible SSR mechanics guide detailing Mortar and Pestle, Alembic, Calcinator, and Retort roles, verified OpenMW 0.51 mwmechanics formulas, and multi-world data provenance, lifting prerendered word count from 118 words to 1030 words (and >630 words across all static pages).

Validation: 553 site tests passed (`npm test` in `A:\Claude\morrowind-tools`); 555 pipeline tests passed (`python -B -m unittest` in `OpenMW Decompiler`); static production build and Cloudflare static export (`npm run build:cloudflare`) succeed cleanly (22/22 routes prerendered). Verified static `.next-export/*.html` outputs for valid semantic `<h1>`, Twitter metadata, rich JSON-LD scripts, and comprehensive word counts.

Next agent: first run `npm test` in `A:\Claude\morrowind-tools`. No extraction or bundle rebuild required.

## Early-game gear from testing, 27 September 2026

Additive to gear-row schema 1.0.0; see `contracts/gear-rows-types.ts`. Policy
`2026.09.27` in `policy/early-game.json`. Pipeline commits through `14db1a3`, site
commits through `49d01a5`.

Policy and verdicts (pipeline):
- `assumeFactionAccess` is false: faction-owned vault and chapel gear is theft.
- `uniformScripts` drops the Ordinator helmets and cuirasses (OrdinatorUniform).
- `endgame.boundSummons`: Devil/Demon/Fiend weapons are endgame and rank on the Bound
  piece they conjure. Picks carry `baseStrength` and `summons`.
- `door_access.py` reads interior pathgrids from `game-data.sqlite`. Routes carry
  `doorLock`, and a locked door is refused like a locked chest.
- Merchants sell only what they own in the active cells around them, as OpenMW's
  trade window does. Stock anywhere else is theft. `holdingCellPrefixes` refuses
  Tamriel Rebuilt's `TR_Hold_` cells.
- Picks carry `place` and `seller`.

Rows (pipeline) and site:
- `earlyGame.ambushes` adds Dark Brotherhood rows, `toggles: {darkBrotherhood: true}`,
  keyed like `armor/helmet/light/darkBrotherhood/power`, only where the level 1
  assassin wears something. The site's `rowMatches` shows them only under the new
  toggle. A site matching only the three policy toggles never selects them.
- Picks carry `enchanted` (effects and worth in enchant points). Clothing `power`
  ranks enchanted pieces first, and `enchantment` ranks blank pieces first. The site's
  `pickRank` merges slots the same way, and `enchantmentNote` shows the effects.
- Travel edges name pack guar, sky lamp and carriage modes.

Rebuild before release. The gear rows now need the rules library and
`game-data.sqlite`, both already earlier in `rebuild.py`. Run
`python build_gear_rows.py` (about 20 minutes per profile), then the travel stage,
the bundle and `npm run data:stage`. Until then the live rows lack the new fields
and the site behaves as before.

Validation: 555 pipeline tests and 559 site tests passed (the site count includes
another session's uncommitted shell changes). No deployment in this batch.

## Fast travel: towns, fares and hours, 27 September 2026

Additive to travel schema 1.0.0; see `contracts/travel-types.ts`. Policy
`2026.09.27.2` in `policy/travel.json`. Uncommitted in both repositories at the time
of writing; the user decides when it lands.

Data (pipeline):
- Nodes carry `town`, `district` and `townRule`. "Old Ebonheart, Docks" and "Old
  Ebonheart, Guild of Mages" are both Old Ebonheart; an unnamed dock joins the town
  beside it (`towns.radius` 1, ties join nothing, `towns.overrides` decide first).
  TR has 90 towns from 137 stops; `exterior:-3,-14` (Teyn or Fort Ancylis) has none.
- Edges carry `price` (before barter and followers), `hours`, `distance`, `fromPos`
  and `toPos`, from OpenMW 0.51.0's travel window, transcribed and pinned like the
  barter formula. Providers carry `barter` (record or autocalc). The payload carries
  `travelFormula` and `barterFormula`; `build_app_bundle.py` publishes both.
- `build_travel_catalog.py` now needs the catalog release (`--catalogs`, default
  `catalogs/current.json`) and stops on another OpenMW release.

Site:
- `FEATURE_CATALOGS.travel` also loads `GameSettings`.
- `lib/travel-graph.mjs`: `stopNameFor` (town first, then the old name folding, then
  region and grid for an unnamed stop), `journeyGold` (getBarterOffer at full
  fatigue), `travelDisposition` (base, shared race, Personality; no faction terms),
  `planRoute` (fewest legs, cheapest or fastest, ties broken by the other two).
  `adaptTravelGraph` keeps one edge per provider and adds its fare, hours and
  districts only when the release has them, so older bundles route as before.
- A null-mode edge is "Other Transport", not "Boat". `lib/travel-map.mjs` names stops
  through `stopNameFor`, so the map and the router agree.
- The workstation offers the three objectives and a followers count, and shows each
  leg's provider, fare, hours and where to board.

Rebuild before release: `python build_travel_catalog.py` (about four minutes), then
`python build_app_bundle.py` and `npm run data:stage`. Until then the site plans by
legs only, as before.

Validation: 583 pipeline tests and 571 site tests passed. A preview bundle built from
the real data was staged, checked in the browser at desktop and 375 px, and unstaged.

## Divine and Almsivi Intervention, 27 September 2026

A new catalog, `Intervention`, schema 1.0.0; see `contracts/intervention-types.ts` and
`docs/stages/INTERVENTION.md`. Additive: no existing catalog changes.

Data (pipeline):
- `build_intervention_catalog.py` runs OpenMW 0.51.0's `World::getClosestMarker` from
  every cell Places publishes. Records are `{key, divine, almsivi}`, indices into the
  carried `markers.divine` and `markers.almsivi` (each with cell, pos, name, town), or
  null where the spell fails. `ambiguous` lists other possible indices where the
  engine's door or cell order, which the data approximates, could decide differently.
- Vanilla: 8 Divine and 6 Almsivi markers, 18 KB gzipped. TR: 25 and 20, 71 KB;
  tr_arce inherits. 167 TR places have no answer; 6 Divine and 14 Almsivi are ambiguous.
- `rebuild.py` runs it after places; the bundle checks its keys and landing cells
  against Places. It is pinned to OpenMW 0.51.0 like the other transcriptions.

Site:
- `FEATURE_OPTIONAL_CATALOGS` in `lib/bundle-loader.mjs`: a catalog a feature uses when
  the release declares it, and does without otherwise. `travel` lists `Intervention`,
  so the code can ship before or after the data. Required catalogs are unchanged.
- `lib/travel-graph.mjs`: `addInterventionEdges` adds free, instant legs from every
  stop and landing spot; `interventionsFromSave` reads the spell or a scroll from a
  loaded save; `journeyGold` prices a `free` leg at 0; route steps carry `spell` and
  `ambiguous`.
- The workstation has Divine and Almsivi toggles (a loaded save sets them), shows
  "Cast ..." legs and warns on ambiguous ones. Forts and courtyards a spell lands in
  become destinations. The map draws spell legs only on the chosen route.

Rebuild before release: `python build_intervention_catalog.py` (seconds), then
`python build_app_bundle.py` and `npm run data:stage`.

Validation: 602 pipeline tests and 576 site tests passed. A preview bundle from the
real data was staged, checked in the browser, and unstaged.

## Every location: doors in, walking legs, 27 September 2026

A new catalog, `Access`, schema 1.0.0; see `contracts/access-types.ts` and
`docs/stages/ACCESS.md`. Additive: no existing catalog changes.

Data (pipeline):
- `build_access_catalog.py`: for every interior, `depth` (doors to the outside), `via`
  (the next room outward) and up to four `exits` (world points where the nearest way out
  opens); null depth for sealed rooms. Carries `land`, an 8 x 8 land mask per exterior
  cell from the VHGT heights, and `walking`, OpenMW 0.51.0's run speed formula.
- TR: 5,729 of 5,974 interiors reach the outside, 3,936 land cells, 127 KB gzipped.
  Vanilla 30 KB. tr_arce inherits.
- `rebuild.py` runs it after intervention; the bundle checks its keys and `via` rooms
  against Places.

Site:
- `FEATURE_OPTIONAL_CATALOGS.travel` adds `Access`.
- `lib/travel-walk.mjs`: `onLand` and `longestWater` over the mask, `runSpeed` and
  `walkHours` (Speed and Athletics, carrying nothing, timescale 30), `stopPoints`,
  `addStopWalks` (stops within 3 cells), `addPlaces` (any cell as origin or destination:
  walks to stops within 10 cells, a direct walk between two places, interventions cast
  from the place), `doorChain`. A walk crossing more than 2,048 units of water is refused.
- The workstation's searches list matching places as well as stops; a chosen place is a
  `place:<cellKey>` node. Walk legs show distance, compass direction and time; the first
  and last legs name the doors out and in. A "Walk between nearby places" toggle, on by
  default. Forts where interventions land (Wolverine Hall, Windmoth) now walk to the town
  beside them.

Rebuild before release: `python build_access_catalog.py` (seconds), after
`python build_intervention_catalog.py` if that has not been run yet, then
`python build_app_bundle.py` and `npm run data:stage`.

Validation: 618 pipeline tests and 584 site tests passed. A preview bundle from the real
data was staged, routes to tombs and ruins and out of them checked in the browser at
desktop and 375 px, and unstaged.

## Propylons and scripted teleports, 27 September 2026

A new catalog, `Teleports`, schema 1.0.0, and a new authored policy,
`policy/teleports.json` 2026.09.27; see `contracts/teleport-types.ts` and
`docs/stages/TELEPORTS.md`. Additive: no existing catalog changes. Mark and Recall
are out of scope by the user's decision.

Data (pipeline):
- `build_teleport_catalog.py` reads every `Player->PositionCell` / `Player->Position`
  in scripts and dialogue results from the script evidence sources. Kinds: propylon,
  dialogue (direct, or a script a dialogue line starts), activator (only when used),
  item (one destination). Each carries from/to cells, `requires` and `unless` item ids,
  unevaluated `conditions`, and `questGated` with `gatedBecause`.
- Everyday travel: Propylons and items gated only by what the player carries, dialogue
  gated only by an item, and the policy's `everyday` rules (Mournhold both ways).
  Everything else is published as quest-gated. A policy rule matching nothing in a
  profile it applies to fails the build.
- Vanilla: 42 teleports (30 Propylon), 5 quest-gated. TR: 138 (47 Propylon),
  78 quest-gated. About a second a profile; `CROSS JOIN` fixes the placement lookup.
- `rebuild.py` runs it after access; the bundle checks its cells against Places.

Site:
- `FEATURE_OPTIONAL_CATALOGS.travel` adds `Teleports`.
- `lib/travel-teleports.mjs`: `usableTeleport`, `heldFromSave`, `teleportItems`,
  `addTeleports` (a stop end joins the stop; any other end becomes a place joined on
  foot). Route steps carry `teleport`, `label`, `questGated` and `conditions`.
- The workstation lists "Items you carry" (Propylon indices first; a loaded save ticks
  its pack) and an "Include quest teleports" toggle, off by default. Teleport legs say
  whom to ask or what to use and what it needs; door lines show only on walking legs.

Rebuild before release: `python build_teleport_catalog.py` (seconds), then
`python build_app_bundle.py` and `npm run data:stage`.

Validation: 638 pipeline tests and 590 site tests passed. A preview bundle from the
real data was staged, Mournhold, Master Index, index-chain, amulet and TR Propylon
routes checked in the browser at desktop and 375 px, and unstaged.

## Travel from the loaded save, and shareable routes, 27 September 2026

No exported dataset or schema changes; site only. No rebuild needed.

- `lib/omwsave-parser.mjs`: additive `identity.position` (the player's own `POS_`,
  local coordinates indoors) and `identity.lastExteriorPosition` (`LKEP`). Read from
  all 141 saves in the user's corpus. The standalone `A:\Claude\omwsave-to-json.js`
  carries the same change. The SLT1 cloud codec does not store them.
- `lib/travel-walk.mjs` `placeFromSave`: indoors the save's room; outdoors the grid
  square from the position; a cloud save with no position, a town by its name.
- `lib/travel-graph.mjs` `guildFromSave` and `CONJURER_RANK` (4, as the Factions
  catalog counts): a loaded save sets the Mages Guild and Conjurer toggles.
- The workstation starts from where the save's character stands (once per load, with a
  button back to it), and warns when a route's fares exceed the gold the save carries.
- `lib/travel-link.mjs`: `from`, `to`, `plan`, `walk=0` and `quest=1` in the travel
  page's query, beside the shell's `world` and `arce`, written only while `/travel` is
  on screen; a "Copy route link" button. A link wins over the save's starting point.

Validation: 598 site tests passed. Checked in the browser with two real saves (a
Mages Guild associate standing in the Ascadian Isles, and an 87-gold character whose
route with a follower costs 165) and with a shared link through a world switch.

## The loaded save survives a page reload, 27 September 2026

No exported dataset or schema changes; site only. No rebuild needed.

- `lib/active-save-store.mjs`: `rememberSave`, `recallSave` and `forgetSave` keep the
  parsed save in this browser's localStorage (`silt-active-save`), packed with the SLT1
  codec (2 to 7 KB across the user's 141 saves). A record that does not decode is
  removed, never half-restored.
- `components/character-context.jsx`: `loadSave` remembers a save; a remembered save is
  restored on the next page load (`loadSave(save, { restored: true })`, which leaves the
  visitor's current world alone). `clearSave`, a shared build link and a new challenge
  run forget it. The builder's notice says the save is kept until cleared.
- `lib/cloud-save-codec.mjs`:
  - Section 10, an optional position extension (`identity.position`,
    `lastExteriorPosition`) after section 9. FORMAT_VERSION stays 1; older payloads
    decode with the fields absent.
  - Browser fallbacks: in a browser bundle `node:zlib` and `node:crypto` are stand-ins
    that reject a Uint8Array ("Not a string or buffer"), so `compressDeflateAsync`,
    `decompressDeflateAsync` and `computeSha256` fall back to CompressionStream,
    DecompressionStream and the pure-JS SHA-256. Packing in the browser had never run:
    the vault packs in the Worker.

Validation: 603 site tests passed; all 141 real saves stored and restored intact in
Node; in the browser a real save was stored, restored after reloads into the home page,
travel planner and builder, and forgotten by Clear save.

## Gear rows weigh enchantments by usefulness, 27 September 2026

Additive dataset change; rebuilt gear rows, best-in-slot and bundle `11120b5348547d5df9d4ec5d`.

- `policy/early-game.json` (policy 2026.09.27.2) gains `enchantmentUsefulness`: tiers
  essential 1.0, situational 0.5, convenience 0.2 and none 0, and a tier for every one
  of the 141 vanilla effects. An entry such as "Fortify Attribute: Personality" overrides
  one attribute or skill. Checked against community consensus: Resist Normal Weapons is
  situational (silver, Daedric and enchanted weapons ignore it), and a Drain on an enemy
  is convenience (it wears off; Damage Attribute lasts).
- `build_gear_rows.py`: each enchanted pick carries `enchanted.value` (engine cost times
  the tier's weight; a curse still counts in full against) and a `tier` on each effect.
  Rows rank on `value`, falling back to `worth`. The build refuses a table name the
  profile's MagicEffects lacks, and the payload lists effects that fell to the default
  tier under `policy.enchantmentUsefulness.defaulted` (none in any profile).
- `contracts/gear-rows-types.ts`: `value?` and effect `tier?`, both optional.
- Site `lib/gear-rows.mjs`: `pickRank` compares `value ?? worth`.

Effect on picks: vanilla primaries unchanged; in TR, 8 right-glove rows now pick the
Glove of the Cosmic Doorknob (Recall) over the Glove of the Dextrous Handshake (Charm).
Alternatives changed in 2 vanilla and 12 TR rows.

Validation: 75 gear-row tests and the full pipeline suite; 604 site tests passed.

## Walking follows the terrain, 27 September 2026

Access schema 1.1.0, additive: a new `walkable` field and a new authored policy,
`policy/walking.json` 2026.09.27. Bundle `5abcaf76d4b4a704e5037cb6`. See
`contracts/access-types.ts` and `docs/stages/ACCESS.md`.

Data (pipeline):
- `build_access_catalog.py` grades every exterior cell into 16 x 16 squares of 512 units
  from the VHGT heights: land, too steep (at least 60% of the square's triangles past
  OpenMW 0.51.0's 46 degree `sMaxSlope`), water within two squares of land to swim, and
  open sea. Two bits a square, base64 per cell.
- Barriers from policy: the Ghostfence's 132 fence and pylon placements joined in a
  ring as walls, the Ghostgate portcullis squares forced open. A barrier matching no
  placement fails the build. Reads `world.sqlite` for placements.
- `steepShare` calibrated on fourteen known vanilla walks; the policy records how.
- `walking.gameSettings` adds fSwimRunBase and fSwimRunAthleticsMult.
- TR: 748,087 land squares, 72,216 too steep or walled, 89,745 to swim; the Access
  catalog is 226 KB gzipped (vanilla 63 KB). About 30 seconds for all three profiles.
- `build_app_bundle.py` carries `walkable` in Access metadata.

Site:
- `lib/travel-walk.mjs`: `walkGrid`, `squareAt`, `findWalk` (A*, no corner cutting, ends
  moved up to two squares onto footing, at most 4,096 units swum), `walksFrom` (one
  search for all stops around a place), `swimSpeed` (getSwimSpeedImpl). `addStopWalks`
  and `addPlaces` take `grid` and `swim`; a place that reaches nothing within 1.5 times
  its reach searches once more, letting the path run to three times it (inside the
  Ghostfence). Only stops within the reach in a straight line count either way (fixed in
  the follow-up: the first release let the far search reach stops 30 cells off, so Dagoth
  Ur walked 29 cells to Vivec). Without a grid, the straight line as before.
- Walk legs carry `terrain`, `straight` and `water`; `planRoute` keeps them on steps.
  The leg reads "round high ground: N x the straight line" and the swim, if any.
- Fixes: the waypoint chain names places instead of printing `place:` ids, and a leg's
  kind badge no longer wraps.

Validation: 662 pipeline tests and 612 site tests passed. Checked in the browser on
the real data: Dagoth Ur to Ald'ruhn goes out by the Ghostgate (19.1 cells, 4 h), where
the straight line crossed the fence; Ilunibi to Balmora 1.2 times the straight line.

## Rooms with no door outside, 27 September 2026

Access schema 1.2.0, additive: sealed rooms (`depth` null) gain `doors`, the rooms their
doors join either way, and `derivation.sealedWithDoors`. Bundle
`a20a1f1c0ae3ffa9ab052da7`. See `contracts/access-types.ts` and `docs/stages/ACCESS.md`.

Why rooms are sealed, TR (vanilla): 83 (79) are joined by doors to an everyday
teleport's end (Mournhold with Bamz-Amschend, Magas Volar, the Subfuscous Cupola); 44
(17) to a quest teleport's end (Sotha Sil, Mortrag Glacier, Khalaan, Dusara); 118 (16)
have no way in the game offers: test cells, TR's `tr_hold_` cells, NPC holding cells,
and a few rooms a one-off quest script moves the player into. Those are left out.

Data (pipeline): `build_access_catalog.py` lists each sealed room's doors; nothing else
changes. The Teleports catalog is built after Access, so the site decides which
teleport ends count.

Site:
- `lib/travel-walk.mjs`: `roomsThrough` (the rooms a sealed room's doors lead to,
  nearest first, with the rooms passed). `addPlaces` takes `nodes` (travel nodes) and
  joins a sealed place to every room the network knows through its doors (a teleport's
  arrival or departure room, or a stop) with an Indoors leg both ways: `indoors`,
  `doors` (the rooms passed), no gold, no time. Every place is a node before any is
  linked, so two sealed rooms added together join.
- `planRoute` keeps `indoors` and `doors` on steps. The leg reads "Go through the doors:
  A → B → C", with "time indoors not counted".
- The place pickers say how a sealed room is reached: by teleport, by quest teleport, or
  no way in known.

Validation: 662 pipeline tests and 616 site tests passed. On the rebuilt data: Balmora to
Mournhold's Great Bazaar (Guild Guide, walk, transport, then indoors through the Palace
courtyard and Plaza Brindisi Dorom), and with quest teleports on, Balmora to Sotha Sil's
Central Gearworks by Almalexia in the High Chapel.

## Walking with a load, Levitate and Water Walking, 27 September 2026

No exported dataset or schema changes; site only. No rebuild needed.

- `lib/travel-movement.mjs` (new), from OpenMW 0.51.0 `Npc::getWalkSpeed`,
  `Npc::getMaxSpeed`, `Actor::getEncumbrance` and `Class::getNormalizedEncumbrance`:
  `movementFor` cuts run, swim and fly speeds by fEncumberedMoveEffect times the load
  over Strength x fEncumbranceStrMult (Feather off, Burden on), and past capacity nobody
  moves; fly speed is fMinFlySpeed + 0.01 x (Speed + Levitate) x (fMaxFlySpeed -
  fMinFlySpeed). `carriedWeight` weighs a save's pack from the item catalogs and its own
  records; `constantEffects` reads Levitate, Water Walking, Feather and Burden from worn
  constant-effect enchantments, the player's own items, abilities and diseases.
- `lib/travel-walk.mjs`: `waterWalk` makes any water, open sea too, walkable at the run
  speed with no swim limit; a `fly` speed adds a straight flight wherever it is quicker
  than the ground path, or the only way (over the Ghostfence). Legs carry `levitate` or
  `waterWalk`, and `planRoute` keeps them on steps.
- `lib/omwsave-parser.mjs`: `stuff.created`, the player-made items the player holds
  (dynamic ARMO, CLOT, WEAP and BOOK records and their ENCH): id, kind, name, weight and
  the effects of a constant enchantment. `parseCreatedItems` exposes it for tests.
- `lib/cloud-save-codec.mjs`: SLT1 section 11 carries `stuff.created`, after section 10;
  FORMAT_VERSION stays 1, older payloads decode with none, and an empty list is not
  stored.
- `lib/bundle-loader.mjs`: a `carrying` feature (the item catalogs, Enchantments,
  Spells), loaded by the travel page only while a save is loaded.
- The travel page: Carrying (of capacity), Constant Levitate and Constant Water Walking
  controls, filled from a loaded save with a note on where each came from, and a warning
  when over-encumbered.

Validation: 626 site tests passed; the user's 141 real saves parsed, every stack weighed
against the TR catalogs, and player-made items survived the codec round trip. In the
browser: Levitate 50 flies Dagoth Ur to Ald'ruhn over the Ghostfence in 53 min (walking
about 4 h); Water Walking takes Vivec to Ebonheart across the water in 29 min (58 min);
carrying 300 of 250 shows the warning and routes no walk.

## Twelve-item launch polish — 2 October 2026 UTC

Implemented locally in `A:\Claude\mt-launch-polish`, on twelve stacked branches
from `2968fa3` (the fetched `origin/main` when work began), ending at
`polish/ingredient-labels`. FLOW-01, UI-03/04/05, SS-08/09/10, SUS-02, F-7/10/13
and F10 / CALC-4-01 are merged into main with owner authorization through
`polish/launch-checklist-batch` (`8c7b98e`). Not deployed. Claims, commits, causes, tests and
acceptance limits are in the site's LAUNCH_CHECKLIST and LAUNCH_VERIFICATION.
Other agents' active site checkout was preserved. The remote-tracking main later
advanced with other agents' retest documentation; this stack retains its original
base; main integration retains the later retest and QA-26 records and fix.

For players: enchanting offers only cast styles the chosen kind supports, including
explicit custom-item kinds; successful challenge generation clears old seed errors;
a fully calculated zero potion chance displays 0%. Travel explains the different
routing-stop and mapped-location counts, and why independently rounded in-game
legs can differ from the total. The Faction Journal always identifies the selected
faction beside its details; Level Simulator and Vault phone labels stay whole;
search uses singular/plural rank labels. Deleting saves and resetting settings now
ask for accessible confirmation and preserve or recover keyboard focus. Ingredient
variants use readable catalog facts in their names, retaining their own sources.
Both site changelogs contain each player-facing fix.

Exported dataset/schema changes: none. The existing staged bundle remains
`a29adea046e6086c2c7ee654`, snapshot
`1613a1123ed9f5102fa3b266df33a4820d0128e9a9bdf680b8b7a1b40296fd1f`.
No extraction, real-data rebuild, production migration or licence change was made.

Runtime invariants: cast eligibility is derived before rendering results, with
OpenMW 0.51 rules; QA-01/02 capacity, chance and price calculations are retained.
Alchemy separates a completed calculation from potion validity without changing
its math. Ingredient labels never replace canonical selection/calculation/source
IDs or collapse distinct records; they infer no curse, quest or size from IDs.
Routing uses precise costs, and in-game estimates remain separate from real-time
approximations. Character/world/account precedence and persisted state are retained.
Confirmations use named alertdialogs with trapped focus and sensible restoration;
SSR starts with them closed. Saved-world and first-navigation hydration checks
passed, including shared builds, challenge links and synthetic loaded saves.

Validation: 1,164 site tests, the Cloudflare build, focused Chrome checks for every
item, the synthetic signed-in launch and existing Vault suites, and 288 hydration
cases passed. Pipeline: 685 tests passed using cache-isolated TEMP/TMP. Full bounded
browser groups and screenshots are recorded under `A:\Cache\launch-polish`; the
site's final verification record identifies accepted reports and excludes incomplete
runs. Shared handoff records are kept byte-identical in both
repositories. Synthetic local QA records/settings/tier overrides were removed.
No ordinary account or production API write was used.

Main integration verification is in the site's LAUNCH_VERIFICATION §54.
The Vault test runner waits for enabled shell controls and sets the next synthetic
user's account theme; timeout captures precede cleanup. No application workaround.
First command for the next agent: from a main checkout, run
`npm test -- --test-concurrency=4`, then the bounded filters documented in
`docs/BROWSER_TESTS.md`. Release authorization remains separate.
