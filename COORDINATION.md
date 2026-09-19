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

## Current split of work

**Antigravity (UI Transformation Lead)**

1. Maintain and evolve `UI_TRANSFORMATION.md` roadmap.
2. Review site UI implementation against CRPG design system and responsive mobile standards.
3. Specify Phase 2 (modernized skill picker) and Phase 3 (cross-tool calculator state integration).

**Codex (Site agent)**

1. Execute the UI transformation specified in `UI_TRANSFORMATION.md` (Phase 1: two-pane Character Builder, decoupled Gear Advisor, and mobile sticky Vitals HUD; Phase 2: modernized skill pickers; Phase 3: cross-tool state integration).
2. Fix the mobile navigation drawer conflict (`legacy.css` suppressing `.hamburger`).
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
