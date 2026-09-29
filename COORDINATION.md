# Coordination

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

No game-data schema changes. Items from `docs/LAUNCH_CHECKLIST.md` (finding IDs from `docs/UX_USABILITY_AUDIT.md`), one commit each. Invariants other agents must keep:

- **LVL-1: archetype detection.** Mercantile and Speechcraft count in full toward Diplomat / Merchant only as majors (4 each, 1.5 as minors, +3 for favoured Personality, +5 with both as majors; 8 or more is a Diplomat), so the default character, a fighter with both as minors, is a Warrior and is no longer told to raise Personality first. `explainArchetype(build)` returns the archetype with a reason ("the Warrior class", "major skills Long Blade, Heavy Armor and Block", the most telling skills first) that the Level Simulator shows; `detectArchetype` still returns the archetype alone, and the Gear Advisor's `buildTraits` follows it. `test/archetype-reason.test.js`.
- **TRV-1: Guild Guides and membership.** Every Guild Guide belongs to the Mages Guild (one TR guide to `T_Cyr_MagesGuild`), and the guild's Service Refusal lines refuse anyone outside it ("same faction" = 0); guides sit at rank 1 to 3, so the "higher rank" refusal never stops a member. Without a save the Travel page keeps Mages Guild on and Conjurer off (owner decision); with one, `guildFromSave` sets both, and `guildGuideNotice` (`lib/travel-graph.mjs`) explains when the character is not a member. Guild Guide legs say "Mages Guild members only". `test/travel-guild-notice.test.js`.
- **TRV-6: "from your save".** `saveMarks` marks the Mages Guild, Conjurer and Intervention boxes while they hold the save's value (unticked ones too), and ticked carried items the save holds; `interventionSources` tells a known spell from a carried scroll, and `interventionMarkText` adds "a scroll, one use". Choices are still reset from the save on each visit; remembering them and spending scrolls are after launch. `test/travel-save-marks.test.js`.
- **BLD-1: theft is opt-in.** The Gear Advisor's options take their defaults from `DEFAULT_GEAR_TOGGLES` (`lib/gear-rows.mjs`), all off; do not give the component its own defaults. The Mentor's Ring benchmark already holds with theft on and off. `test/gear-defaults.test.js`.
- **TRV-3: one entry per town.** `matchPlaces` (`lib/travel-walk.mjs`) is the Travel pickers' place search: same-named exterior cells in one region (a town spans several; 19 in vanilla) are listed once as the most central cell, ties to the first key; rooms never merge; stops stay out. Place buttons carry `bg-transparent border-0`, as every button needs one or the browser paints its grey. `test/travel-place-search.test.js`.
- **Claims.** No page, card, search description or structured data may call the maths "verified" or "exact", or promise "inter-faction standing"; say it follows OpenMW 0.51's source, and describe the Faction Journal's reactions as how factions regard each other. `test/site-claims.test.js` scans app, components and the SEO data (past changelog entries excepted); LAUNCH_POSTS lists the removed claims.
- **HOME-2, replaced: a random premade start.** `CharacterProvider` renders `DEFAULT_BUILD` on the server and in the browser's first render (anything random there fails hydration and React discards the prerendered page), then its first effect sets a random premade from `getRandomPremadeBuild` (`lib/premade-data.mjs`: base-game races unless ARCE); links, the sign-in handoff and saves apply after it and win. Leaving ARCE with an ARCE-only race: an untouched random premade is re-drawn, a player's character keeps everything but the race (`canonicalRaceFor`). `test/random-premade-start.test.js`, `test/random-premade-build.test.js`.
- **The shell is not ready while a page hydrates.** Until then `useShell()` has `ready: false` and the prerender's world (vanilla), whatever the visitor chose; the client's world arrives in the next render. Effects that run at mount and need the world read it directly: `readVisitorProfile()` (address, then storage) or `readStoredProfile()` (storage only), both in `components/shell-context.jsx`. `CharacterProvider`'s world sync waits for `ready`. Test such code with `hydrateRoot` over a `renderToString` page (the `hydrated` helper in `test/random-premade-start.test.js`); `createRoot` hides the problem.
- **SITE-1: one name per tool on screen.** Character Builder, Level Simulator, Travel Planner, Alchemy, Enchanting, Spellmaking, Faction Journal, Challenge Runs, Cloud Vault in nav, visible headings, buttons, home cards, search and breadcrumbs. The long SEO names stay in page titles, the sr-only h1 (`lib/view-headings.mjs`), the pages' hidden guides and structured data. `test/tool-names.test.js` fails on an old name in `components/`, the home and search data, the 404 page or the challenge export.
- **LINK-1: a shared link's world wins.** A build or run link that names a world (`world` or `arce` in its query) sets it, as the world switch would; one that names none keeps the visitor's world (it would decode as vanilla). Compare with the kept world, not the hydrating shell. Tests: `test/random-premade-start.test.js` (builder), `test/share-link-world.test.js` (runs).
- **CALC-1: no results before input.** Spellmaking and Enchanting show `NO_RESULT` (a dash with sr-only "not calculated yet") for chance, cost, school and vendor prices until an effect is chosen, with a `.calc-empty-prompt`; Alchemy until `potion.isValid`. Enchanting's capacity stays a number. Effect pickers label base costs with `baseCostLabel` (float32 noise). `test/calculator-empty-states.test.js`.
- **SITE-2 / VLT-1: explanations are closed disclosures.** Each tool has exactly one `<details className="calculation-notes">` with `<summary>How this is calculated</summary>`, closed by default, in plain words with any formula inside; no "invariants", "engine rules" or implementation jargon (ArrayBuffer, SQLite, Cloudflare) in player text. `assertCalculationDisclosure` in `test/seo-phase2.test.js`. Codex's work, finished and merged by Claude.

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
   - Hero (`components/home-hub/`): a save drop zone (`home-save-drop.jsx`) is the primary action; a file dropped anywhere on the page opens too. The world picker (`home-worlds.jsx`, now compact) sits right above "Start a new build". The Challenge Runs link and the bottom "Choose your Morrowind" section are gone. With a save loaded, the character card shows the save.
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
