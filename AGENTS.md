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

# Local workflow preferences

- The user runs full game-data extraction commands locally in VS Code. Build the
  code and provide commands; do not run or rebuild their real-data catalogues
  unless explicitly asked. Verify changes with synthetic fixtures instead.
- Keep generated datasets, staging databases and temporary test fixtures under
  `A:\Cache`. Set `TEMP` and `TMP` there when running tests. Avoid bytecode caches
  with `python -B`. Source code belongs in this workspace.
- Preserve separate vanilla, tr and tr_arce profiles and source provenance.
