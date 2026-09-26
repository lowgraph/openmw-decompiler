# Item location exporter

Run this after the item export, in the same VS Code terminal:

```powershell
python export_locations.py
```

It uses the existing Python dependency, paths, version labels, and approved plugin
allowlist. You can also select **Export item locations** in Run and Debug and press
F5. The full location export has not been run during code creation.

Output: `A:\Cache\ItemLocations.json`. Existing item tables remain untouched. The
export includes a row for every item ID, including items with no discovered
locations. An empty array means no static placement was found, not proof that an
item cannot be obtained.

Alternative input/output:

```powershell
python export_locations.py --items-dir items --output output/ItemLocations.json
python export_locations.py --list-plugins
```

`--list-plugins` previews scope without reading plugin records or exporting data.
The normal run checks the item export report's plugin order and version labels.
Rerun the item exporter first after editing/installing plugins; the old report does
not fingerprint plugin bytes, so same-name file changes cannot be detected.

## What locations mean

- **Placed:** an item reference in an interior or exterior cell.
- **Container:** an item in a placed container's winning inventory definition.
- **NPC inventory:** an item carried by a placed NPC definition. Equipped items
  and sale inventory are not distinguished by this static exporter.
- **Creature inventory:** an item carried by a placed creature, including a
  creature reached through a leveled-creature spawn.
- **Leveled loot:** recursive LEVI/LEVC paths, with entry indices, minimum levels,
  raw list flags, and chance-none values retained. `leveled_chance` describes
  conditional paths; the exporter does not solve joint level eligibility or
  calculate probabilities. Lists with 100% chance-none yield no locations.

Cell references use a stable `referenceId` combining the defining plugin filename
and reference number. Master-relative indices resolve through each plugin's MAST
list. Overrides update individual references without discarding the cell's other
placements. Deleted references/cells are excluded, and MVRF/CNDT moves use the
destination exterior cell. Position and rotation are game coordinates, with
rotation in radians. Exterior `grid` is the cell's X/Y index.

Each `path` shows how a location reaches an item. It preserves inventory counts,
list alternatives, the winning definition plugin, and attached script IDs. Repeated
paths are intentionally not collapsed: separate placements and list entries can
look similar but have different meanings. `count` is the absolute count along that
path, conditional on the path being selected. Negative inventory counts are
preserved in `path` and marked `restocking` on the location.

Each item row retains the item table's `gameDataVersion`. A location's own version
describes the plugin family that supplies its winning reference. These can differ
when a mod places or overrides a vanilla item.

## Ownership and availability

`access` preserves owner, faction, faction rank, ownership global, raw lock level,
key, and trap references. `takingIsTheft` is `conditional` for owned references or
actor inventories. `not_marked_owned` only means no explicit owner was found on
that reference; it is not a legal-access guarantee. `saleStatus` is deliberately
`not_determined`, since an actor holding an item does not prove it is for sale.

`static_definition` means the item is explicitly in the loaded definitions. It
does not guarantee availability in the current save: scripts can disable objects,
quests can change inventories, actors can travel, and the player may already have
taken an item. Container respawn behavior and merchant service/nearby-container
logic are not simulated.

`label` is display text such as “Balmora, Guild of Mages — Chest”. Use the structured
cell/source/access fields for program logic, rather than parsing that label.

## Scripts and quests

`scriptReferences` contains lexical mentions of the item ID in winning SCPT source
and dialogue INFO result scripts, with line numbers and evidence. Comments are
excluded. Mentions can be checks, dialogue strings, removals, or conditional grants;
they are explicitly `unverified_text_reference`, not asserted locations. Conditions
and control flow are not interpreted. Script references to an actor that indirectly
spawns an item, compiled-only scripts, and Lua `.omwscripts` need further analysis.
No physical location is invented for unplaced NPC/container definitions.

`coverage` lists excluded content, missing script sources, unresolved inventory
entries, and cycles. Review it after exporting. These warnings describe gaps
instead of silently suggesting the location coverage is exhaustive.

## Verification

```powershell
python -m unittest test_export_locations test_export_items -q
```

Tests operate only on saved samples and synthetic plugins. Output is checked
against `location-schema.json`, then written to a temporary file and atomically
replaced. Parsing/validation failures leave an existing location export intact.

## Progress and memory

After loading references, the exporter prints the reference count and progress
every few seconds: references processed, location paths generated, and elapsed
time. Nested random-loot lists can produce many paths for one reference, so the
reference counter may stay still while the path counter increases.

Expanded rows are validated individually and stored in a temporary SQLite database
under `A:\Cache`. The final JSON is streamed from that database,
with a separate writing-progress counter. The catalog's location arrays remain
empty in memory; definitions and cell references still require RAM. The temporary
database and staged JSON require disk space proportional to the export size.

`locationCacheDirectory` and `locationOutputDirectory` in `export_config.json`
both default to `A:/Cache` for this PC. Thus the large database, staged JSON, and
completed location JSON all stay on A:. The folder is created on the next run.
Use `--cache-dir` or `--output` to override these paths. Item-table inputs still
come from this project's `items` folder. SQLite auxiliary temp structures remain
in memory rather than spilling into the Windows temporary directory on C:.

The final JSON uses compact location rows, one per line, while preserving the same
schema and fields. Temporary data is cleaned up on normal completion or Ctrl+C.
Do not run multiple exporters at once. A forced process termination can leave an
`openmw-locations-*` temporary directory; it is not used on subsequent runs.

Binary layout references:
[OpenMW cell references](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/cellref.cpp),
[cells and moved references](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadcell.cpp),
[inventory entries](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadcont.cpp),
[leveled lists](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadlevlist.cpp).
