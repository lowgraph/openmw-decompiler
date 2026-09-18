# Two agents work on this project

Read [COORDINATION.md](COORDINATION.md) before starting, and [HANDOFF.md](HANDOFF.md)
if you are picking this up cold. You own this repository; a second agent owns the
site at `A:/Claude/morrowind-tools` and consumes the bundle you publish. Do not edit
that repository.

# Local workflow preferences

- The user runs full game-data extraction commands locally in VS Code. Build the
  code and provide commands; do not run or rebuild their real-data catalogues
  unless explicitly asked. Verify changes with synthetic fixtures instead.
- Keep generated datasets, staging databases and temporary test fixtures under
  `A:\Cache`. Set `TEMP` and `TMP` there when running tests. Avoid bytecode caches
  with `python -B`. Source code belongs in this workspace.
- Preserve separate vanilla, tr and tr_arce profiles and source provenance.
