# Coordination

Three agents work on Silt Strider in parallel. This file is identical in both
repositories. If you change it, change both copies in the same session.

## Who owns what

| | Antigravity (UI Lead) | Codex (Site Agent) | Claude (Data Agent) |
| --- | --- | --- | --- |
| Repository / Focus | Architecture, Design & Specs (`UI_TRANSFORMATION.md`) | `A:\Claude\morrowind-tools` | `C:\Users\tiago\OneDrive\Documents\ChatGPT\OpenMW Decompiler` |
| Owns | UI/UX specifications, design tokens, component hierarchy, CRPG aesthetic standards | Next.js 16 App Router, React 19, Tailwind CSS, UI implementation, Clerk, `cloudflare/`, D1 routes & migrations | Extraction, catalogs, policy, gear rows, rules library, engine dumps, app bundle publication |
| Reads | User feedback, in-game references (`Char Creation.png`), legacy runtime | `UI_TRANSFORMATION.md`, `public/game-data/`, legacy workbench | Plugin files, OpenMW engine dumps, `A:\Cache\OpenMWFoundation` |
| Never | Writes production backend database code | Opens raw SQLite databases or runs extractors | Writes frontend JSX, CSS, or Cloudflare route handlers |

**Respect workspace boundaries.** While agents can inspect files across folders for context, each agent only commits changes within its designated scope. Antigravity authors cross-cutting UI blueprints; Codex implements them in `morrowind-tools`; Claude implements data features in `OpenMW Decompiler`.

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

### 2. Cross-Repo Boundary Enforcement
* **Strict Boundary:** The Pipeline agent (`OpenMW Decompiler`) must NEVER directly modify files inside `A:\Claude\morrowind-tools`.
* **Contract Sync:** Changes to game parsing outputs or schemas pass exclusively via exported JSON bundles to `public/legacy/` and synchronized updates to `COORDINATION.md` and `UI_TRANSFORMATION.md`.
* **Legacy HTML Sync Hook:** Whenever `index.html` is modified, immediately run `npm run extract:legacy` to regenerate `public/legacy/body.html` before running tests or visual verification. Never leave Next.js running against stale extracted markup.

### 3. Verification & Adversarial QA Protocols
* **Pipeline Tests (233 suites):** Must pass cleanly with zero uncaught warnings. Output should be summarized; do not flood context with raw passing test logs.
* **Site Tests (155 suites) & CDP Screenshots:** Run `npm test` in `A:\Claude\morrowind-tools`. For UI modifications, execute headless visual capture via Chrome CDP on port 8765 (`node <scratchDir>/capture-*.js`) to confirm layout integrity before ticket completion.
* **Adversarial Edge Cases:** Do not approve schema/logic changes on baseline tests alone. Before marking a logic task complete, write at least 3 automated tests targeting edge conditions (malformed record tags, missing SQLite indices, null/undefined properties, or boundary values).

### 4. Two-Failure Revert & Escalation Policy
* If an automated test fails twice consecutively during a fix attempt:
  1. Immediately abort code edits.
  2. Revert the working directory to the last clean git commit (`git restore .` / `git checkout .`).
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
3. Completed Phase 1 (Two-Pane Character Builder), Phase 2 (Skill Matrix), Phase 3 (Cross-Tool Calculator State), Phase 4 (Challenge Runs Overhaul), Phase 5 (The 4 Specialized Calculators), and Phase 6 (Character Level Simulator & Build Progression Optimizer).
4. Specify Phase 7 (Cloud Character Vault - Clerk + Cloudflare D1) and Phase 8 (Home Hub & Tool Launcher Cards).

**Codex (Site agent)**

1. ~~Execute Phase 1-6 UI transformations specified in `UI_TRANSFORMATION.md`.~~ **Done.**
   All interactive workstations (Character Builder, Challenge Runs, Enchanting, Spellmaking, Alchemy, Travel, Level Simulator) are fully implemented, verified via CDP, and covered by 170 passing unit tests.
2. Next Milestone: Phase 7 (Cloud Character Vault) — implement Clerk authentication and Cloudflare D1 character schema/persistence routes for user builds and leveled progression history.
3. Rewire the legacy calculators to the loader. `DATA_LOADER.md` is explicit that
   the loader is ready and the calculators still use their verified legacy tables;
   until this lands, the bundle powers nothing.
4. Repoint `scripts/stage-game-data.mjs` away from its `A:/Cache/OpenMWBundlePreview`
   default to `A:/Cache/OpenMWFoundation/app-bundle`. The preview folder is scratch
   and will be deleted.
5. Commit or delete the untracked `lib/character-catalogs.mjs`.
6. Build the three-toggle UI: steal early gear, endgame gear early, near starting
   areas. See POLICY.md in the data repository for what each one means.
7. D1 schema and routes for journal progress, equipped loadouts, known spells and
   saved challenges. The existing 16 KB `character_json` cap will not hold them.
   The data agent supplies the field requirements; the migrations are yours.

**Claude (Data agent)**

1. ~~Ship gear rows through the bundle as a `GearRows` catalog.~~ **Done.**
   `build_app_bundle.py` publishes them automatically, keyed per row, with the policy
   that produced them travelling as payload fields. Rows must be rebuilt first: the
   packager refuses a file from another snapshot or one whose rows predate the key.
   Nothing changes on the site until `FEATURE_CATALOGS` gains a `gear` group.
2. ~~The rules library.~~ **Partly done.** `build_rules_library.py` derives targeting,
   no-magnitude and no-duration from content usage and ships them as the `EffectRules`
   catalog, with the spell cost formula's engine literals authored alongside. 134 of 141
   effects are decided, 7 report `null`. Display units and harmful-effect flags are still
   absent and are not inferable from content; see RULES.md.
3. The travel graph as a shipped catalog, from `services.sqlite`.
4. Merchant barter pricing, for "gold price per merchant".
5. The 326 journal topics with no resolvable title.
6. Save import for OpenMW `.omwsave`, format v37.

## Asking across the boundary

State the request as a contract change, not a task. Name the catalog or field, say
whether it is additive, and give the shape. The other side decides how to implement
it. If a change is breaking, both sides bump and land it together — never one alone.

When either side finishes something the other can use, say so explicitly with the
artifact name. Silence reads as "not ready yet".
