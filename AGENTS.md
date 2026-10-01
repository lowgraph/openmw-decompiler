# Three agents work on this project

Read [COORDINATION.md](COORDINATION.md) before starting, and [HANDOFF.md](HANDOFF.md)
if you are picking this up cold. For canonical repository paths and recent
restructuring, read [docs/AGENT_PATH_MIGRATION.md](docs/AGENT_PATH_MIGRATION.md).

## Release sprint ownership — 29 September 2026

The owner authorizes any agent to implement release-sprint work in either repository.
The roles below describe specialties, not exclusive editing or commit permissions.
Follow the site's launch checklist at `A:\Claude\morrowind-tools\docs\LAUNCH_CHECKLIST.md`
in priority order, including its task-claim timestamps, completion records, freeze
and cut line. `C` means the agent doing the work, not Claude exclusively; `O` remains
owner work. Inspect existing changes before editing and preserve other sessions' work.
This supersedes older agent ownership restrictions in the roadmap and handoffs.
Repository architecture, verification, real-data rebuild restrictions, and separate
push/deploy authorization still apply.

1. **Claude (Data Agent):** Specializes in this data pipeline repository (`lowgraph/openmw-decompiler`).
   Extracts game files, maintains normalized SQLite databases in the local data workspace,
   derives effect rules, evaluates policies, and publishes the app bundle.
2. **Codex (Site Agent):** Specializes in the sibling web application repository (`lowgraph/siltstrider.tools`)
   and implements the web application consuming the bundle, executing the UI
   transformation set out in [UI_TRANSFORMATION.md](UI_TRANSFORMATION.md).
3. **Antigravity (UI Transformation Lead):** Directs the UI/UX architecture,
   component design, and CRPG authenticity across the project.

# Local Workflow & Operational Guardrails

### 1. Shell & Environment Invariants (CRITICAL)
- **PowerShell Only:** Never emit bash chained operators (`&&`). Always use PowerShell command separators (`;`) or execute statements sequentially.
- **Temp Isolation:** All temp fixtures, staging databases, artifacts, and test caches must strictly reside in the configured local cache directory (e.g., `A:\Cache`). Always prefix pipeline test invocations with:
  `$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"`
- **Scratch & Secret Isolation:** Never stage scratch files (e.g., `<scratchDir>/capture-*.js`), `Char Creation.png`, or `Hey.html`. Always clean up temporary runner scripts after visual evaluation.
- **No Real-Data Rebuilds Without Instruction:** The user runs full game-data extraction commands locally in VS Code. Build code and provide commands; do not rebuild real-data catalogues unless explicitly asked. Verify changes with synthetic fixtures instead.
- **Provenance:** Preserve separate vanilla, tr, and tr_arce profiles and source provenance.

### 2. Repository Architecture & Shared Ownership
- **Shared Sprint Ownership:** Any agent may edit either repository for launch-checklist work; keep site implementation in the site and extraction logic in the pipeline.
- **Contract Sync:** Changes to game parsing outputs or schemas pass exclusively via exported JSON bundles to `public/game-data/` and synchronized updates to `COORDINATION.md` and `UI_TRANSFORMATION.md`.
- **Canonical Schema Paths:** All SQL schemas reside in `schemas/`. Never recreate schema files in the repository root.

### 3. Verification & Adversarial QA Protocols
- **Pipeline Tests:** Must pass cleanly with zero uncaught warnings. Summarize output; do not flood context with raw passing test logs.
- **Site Tests & CDP Screenshots:** Run `npm test` in the site repository. For UI modifications, execute headless visual capture via Chrome CDP on port 8765 (`node <scratchDir>/capture-*.js`) to confirm layout integrity before ticket completion.
- **Adversarial Edge Cases:** Do not approve schema/logic changes on baseline tests alone. Before marking a logic task complete, write at least 3 automated tests targeting edge conditions (malformed record tags, missing SQLite indices, null/undefined properties, or boundary values).

### 4. Handoff & Synchronization
- Keep `COORDINATION.md` and `UI_TRANSFORMATION.md` identical across both repositories.
- When completing a batch or milestone, update `COORDINATION.md` with:
  - Exported dataset schema changes.
  - Invariants assumed by the downstream Next.js / legacy JS runtime.
  - Exactly which script/command the next agent must run first.
- **Changelog first.** Before committing, pushing or deploying a major change that visitors
  will notice once its bundle is staged, say so in `COORDINATION.md` in words fit for players,
  so the site's changelog (`CHANGELOG.md` and `components/views/changelog-view.jsx`) records it
  before the site release that ships it.
