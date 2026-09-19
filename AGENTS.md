# Three agents work on this project

Read [COORDINATION.md](COORDINATION.md) before starting, and [HANDOFF.md](HANDOFF.md)
if you are picking this up cold.

1. **Claude (Data Agent):** Owns this data pipeline repository (`lowgraph/openmw-decompiler`).
   Extracts game files, maintains normalized SQLite in `A:\Cache\OpenMWFoundation`,
   derives effect rules, evaluates policies, and publishes the app bundle.
2. **Codex (Site Agent):** Owns the site repository at `A:\Claude\morrowind-tools`
   and implements the web application consuming the bundle, executing the UI
   transformation set out in [UI_TRANSFORMATION.md](UI_TRANSFORMATION.md). Do not
   edit that repository.
3. **Antigravity (UI Transformation Lead):** Directs the UI/UX architecture,
   component design, and CRPG authenticity across the project.

# Local Workflow & Operational Guardrails

### 1. Shell & Environment Invariants (CRITICAL)
- **PowerShell Only:** Never emit bash chained operators (`&&`). Always use PowerShell command separators (`;`) or execute statements sequentially.
- **Temp Isolation:** All temp fixtures, staging databases, artifacts, and test caches must strictly reside in `A:\Cache`. Always prefix pipeline test invocations with:
  `$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"`
- **Scratch & Secret Isolation:** Never stage scratch files (e.g., `<scratchDir>/capture-*.js`), `Char Creation.png`, or `Hey.html`. Always clean up temporary runner scripts after visual evaluation.
- **No Real-Data Rebuilds Without Instruction:** The user runs full game-data extraction commands locally in VS Code. Build code and provide commands; do not rebuild real-data catalogues unless explicitly asked. Verify changes with synthetic fixtures instead.
- **Provenance:** Preserve separate vanilla, tr, and tr_arce profiles and source provenance.

### 2. Cross-Repo Boundary Enforcement
- **Strict Boundary:** The Pipeline agent (`OpenMW Decompiler`) must NEVER directly modify files inside `A:\Claude\morrowind-tools`.
- **Contract Sync:** Changes to game parsing outputs or schemas pass exclusively via exported JSON bundles to `public/legacy/` and synchronized updates to `COORDINATION.md` and `UI_TRANSFORMATION.md`.
- **Legacy HTML Sync Hook:** Whenever `index.html` in the site repo is modified, immediately run `npm run extract:legacy` to regenerate `public/legacy/body.html` before running tests or visual verification. Never leave Next.js running against stale extracted markup.

### 3. Verification & Adversarial QA Protocols
- **Pipeline Tests (233 suites):** Must pass cleanly with zero uncaught warnings. Summarize output; do not flood context with raw passing test logs.
- **Site Tests (155 suites) & CDP Screenshots:** Run `npm test` in `A:\Claude\morrowind-tools`. For UI modifications, execute headless visual capture via Chrome CDP on port 8765 (`node <scratchDir>/capture-*.js`) to confirm layout integrity before ticket completion.
- **Adversarial Edge Cases:** Do not approve schema/logic changes on baseline tests alone. Before marking a logic task complete, write at least 3 automated tests targeting edge conditions (malformed record tags, missing SQLite indices, null/undefined properties, or boundary values).

### 4. Two-Failure Revert & Escalation Policy
- If an automated test fails twice consecutively during a fix attempt:
  1. Immediately abort code edits.
  2. Revert the working directory to the last clean git commit (`git restore .` / `git checkout .`).
  3. Emit a concise root-cause analysis showing the failing stack trace and the exact breaking invariant.
  4. Stop and request a `/boost` escalation run. Do not accumulate speculative patches.

### 5. Handoff & Synchronization
- Keep `COORDINATION.md` and `UI_TRANSFORMATION.md` identical across both repositories.
- When completing a batch or milestone, update `COORDINATION.md` with:
  - Exported dataset schema changes.
  - Invariants assumed by the downstream Next.js / legacy JS runtime.
  - Exactly which script/command the next agent must run first.
