# OpenMW inventory exporter

> **Three-agent project:** Three agents collaborate across Silt Strider. **Claude** owns this data pipeline repository, **Codex** owns the site frontend (`A:\Claude\morrowind-tools`), and **Antigravity** leads UI transformation architecture. See [COORDINATION.md](COORDINATION.md) and [AGENTS.md](AGENTS.md).

**Picking this up cold? Start with [HANDOFF.md](HANDOFF.md)** for the project scope,
what exists, the rules that cost real debugging, and the ordered next steps.

**New foundation:** start with [FOUNDATION.md](FOUNDATION.md) and run
`python extract_foundation.py`. It preserves plugin records and resolves Vanilla,
TR, and TR + ARCE profiles in `A:\Cache\OpenMWFoundation\game-data.sqlite`.
The JSON exporters documented below are earlier prototypes, not prerequisites.

**After the foundation:** run `python build_catalogs.py` to create the typed
profile catalogs. See [CATALOGS.md](CATALOGS.md) for the output layout and
`catalog-types.ts` for the application contract.

**Effect flags from the engine:** run `python dump_profiles.py`. It launches OpenMW
once per profile with [openmw_effect_dump](openmw_effect_dump/README.md) on `--data`,
so nothing is installed, and imports each result. This turns the inferences below into
facts, adds `harmful` and definitive targeting, which content cannot reveal, and picks
up the 45 effects Tamriel Rebuilt registers through Lua and no plugin file defines.

**Effect rules:** run `python build_rules_library.py` to derive the per-effect behaviour
the plugin files omit — targeting, no-magnitude and no-duration — from how the game's own
content uses each effect. The spell cost formula branches on the last two. See
[RULES.md](RULES.md) and `rules-types.ts`.

**Gear rows:** run `python build_gear_rows.py --profile vanilla` after the policy is
settled. It writes one row per equipment slot per toggle combination, with the closest
source first and a stronger "or" from farther away. See [ROWS.md](ROWS.md) and
`gear-rows-types.ts`.

**Ship to the site:** run `python build_app_bundle.py` after the catalogs to write
the browser-facing bundle. See [BUNDLE.md](BUNDLE.md) and `bundle-types.ts`. It excludes
book prose and publishes ARCE as a delta over TR, and reads no extraction databases.

**World data:** run `python build_world_catalog.py` to produce the normalized
world database on A:. See [WORLD_CATALOG.md](WORLD_CATALOG.md). It stores linked
inventories, lists, cells, actors and placements without expanding acquisition paths.

**Services and travel:** run `python build_services_catalog.py` after the world
builder. See [SERVICES_CATALOG.md](SERVICES_CATALOG.md) for service flags, provider
locations, transport destinations, directed teleport doors, and coverage limits.

**Quests, dialogue and scripts:** run `python build_journal_catalog.py` to decode
journal stages, quest markers, dialogue filters/conditions and script source.
See [JOURNAL_CATALOG.md](JOURNAL_CATALOG.md). Full extraction runs are performed
locally by the user in VS Code; development verification uses synthetic fixtures.

**Acquisition evidence:** run `python build_acquisition_index.py`, then query with
`python inspect_acquisition_index.py --item katana_goldbrand_unique`.
See [ACQUISITION_INDEX.md](ACQUISITION_INDEX.md) for bounded reverse queries through
inventories and leveled lists, without expanding location paths.

**Script acquisition evidence:** run `python build_script_evidence.py`, then
`python inspect_script_evidence.py --item katana_goldbrand_unique`.
See [SCRIPT_EVIDENCE.md](SCRIPT_EVIDENCE.md) for command coverage and uncertainty.

**Acquisition policy:** add `--policy` to `query_item_sources.py` to fill in the
`assessment` block: obtainability, theft, sale status, price and early-game eligibility.
See [POLICY.md](POLICY.md) and `policy-types.ts`. The rules are authored in
[policy/early-game.json](policy/early-game.json) and versioned separately from any
extraction snapshot, so a rule change never costs a re-extraction. Without `--policy`
the assessment stays null.

**Unified item sources:** run `python query_item_sources.py --item katana_goldbrand_unique`.
This combines the existing static index and script evidence with bounded context
location lookups. No new database build is needed. See [ITEM_SOURCES.md](ITEM_SOURCES.md).

Exports the 12 inventory item categories into the existing `items/*.json` files.
Python 3.10+ is required. The game and mods do not need to be running.

## Run in Visual Studio Code

Open this project folder in VS Code. In its terminal, run:

```powershell
python -m pip install -r requirements.txt
python export_items.py --list-plugins
python export_items.py
```

The first command installs the JSON Schema validator. The second previews the
approved active plugin paths without parsing them or writing files. The third
performs the full export and replaces the 12 category JSON files. It also writes
`items/export-report.json` with the load order, excluded content, and item counts.

Use the same Python interpreter for installation and export. With VS Code's
Python debugger available, select **Export all inventory JSONs** in Run and Debug
and press F5. A separate launch configuration previews the approved plugins.

Paths and version labels are already set for this PC in `export_config.json`.
When installing a new approved plugin, add its filename to `allowedPlugins` and
enable it in `openmw.cfg`. Only active plugins in both the file allowlist and the
approved data directories are read. Other mods and `.omwscripts` are excluded.

To save a separate export:

```powershell
python export_items.py --output output
```

Each output directory receives schemas alongside its tables. Game-data paths
are opened for reading only. Output inside the base-data or mods tree is rejected.

## Data rules

- `vanilla` has version `OpenMW 0.51.0`.
- `tamriel_rebuilt` has version `Tamriel Rebuilt 26.08.23`.
- The second world is the requested two-world grouping for all five approved mod
  families, including Tamriel_Data, Cyr_Main, Sky_Main, and ARCE. These are dataset
  version labels, not assertions about those individual mods' release versions.
- An item's world is determined by the earliest loaded definition of that item.
  Overrides keep that origin while `sourcePlugin` identifies the winning plugin.
- Plugins load in `content=` order. Later approved data directories resolve file
  collisions. Later records replace earlier records, and deleted records are removed.
- Master dependencies must already appear in the approved load order. The program
  fails instead of silently reading an unapproved dependency.
- Enchantments resolve against the final winning ENCH records, including overrides.
  Effect display names resolve from the final GMST records. There are no network
  lookups while exporting.
- Base item stats are exported; player-dependent prices, auto-calculated costs,
  running scripts, and saved-game inventory instances are not evaluated.
- All inventory definitions are included, including unnamed/script-use records;
  world-placed lights are excluded unless their carry flag is set.
- Every dataset must pass its JSON Schema before publication. Missing enchantments,
  missing effect names, malformed binary data, and unsupported enum values cause a
  descriptive failure. Existing tables survive parsing or validation failures.
- Files are staged before publication, with an atomic replacement per file.
  Replacement of the entire set is not a single transaction; a disk failure or
  process interruption during publication can leave a mixed set. Rerun to complete.

The config reader supports this PC's flat `openmw.cfg`, including quoted data
paths, `content`, and `encoding`. Chained `config=` and `replace=` directives are
rejected explicitly; supply a flattened configuration in that case.

See [items/README.md](items/README.md) for field conventions and categories.

## Verify the code

```powershell
python -m unittest test_export_items -v
```

Tests use the already-saved examples and temporary synthetic plugins. They cover
all 12 record types, enchantment overrides, deletion, dependency errors, directory
priority, scope exclusions, malformed records, carryable lights, and JSON output.
They do not parse the installed game/mod files or populate your full tables.

The full export has deliberately not been run as part of creating this code.

## Locations

After populating the item tables, run `python export_locations.py` to generate
`A:\Cache\ItemLocations.json`. Temporary location data also goes to `A:\Cache`.
See [LOCATIONS.md](LOCATIONS.md) for ownership,
leveled-list, script-reference, and coverage details. This does not modify item tables.
