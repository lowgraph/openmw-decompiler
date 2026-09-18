# Inventory JSON structure

The twelve category JSON files contain empty `items` arrays. No full item lists
have been exported. Their matching files in `schemas/` define item properties,
required fields, allowed types, and shared enchantment/effect structures using
JSON Schema Draft 2020-12. `examples/` contains one actual Morrowind.esm record
per inventory type; Goldbrand is the weapon example. The raw sample file is an
inspection aid, not an item dataset.

| Dataset | Record | Includes |
| --- | --- | --- |
| Weapons.json | WEAP | Melee weapons, bows, crossbows, thrown weapons, arrows, bolts |
| Armor.json | ARMO | Armor pieces and shields |
| Clothing.json | CLOT | Clothing, rings, amulets |
| Books.json | BOOK | Books, notes, skill books, scrolls |
| Potions.json | ALCH | Potions and drinks |
| Ingredients.json | INGR | Alchemy ingredients and ingredient-based food |
| Apparatus.json | APPA | Mortars, alembics, calcinators, retorts |
| Lockpicks.json | LOCK | Lockpicks |
| Probes.json | PROB | Probes |
| RepairTools.json | REPA | Repair tools |
| Lights.json | LIGH | Carryable lights only |
| Miscellaneous.json | MISC | Gold, keys, soul gems, other miscellaneous inventory objects |

## Version metadata

`GameDataVersion.ts` preserves the requested type exactly. The equivalent shared
JSON definition lives in `schemas/Common.schema.json`. Each item has a separate
`gameDataVersion` object, rather than a bare `"vanilla"` token or a gameplay
property. `schemaVersion` describes our JSON format, not the game release.

The requested dataset labels are `OpenMW 0.51.0` for `vanilla` and
`Tamriel Rebuilt 26.08.23` for `tamriel_rebuilt`. All five approved mod families
use the latter grouping; `sourcePlugin` identifies the individual plugin.
Items retain the world of their first loaded definition through overrides.
The saved samples originate in `Morrowind.esm` and use the vanilla label.

## Conventions

- IDs retain their original spelling. ID resolution must be case-insensitive.
- Numbers are JSON numbers, including `value`, `health`, and `enchantp`.
- Damage ranges use `{ "min": 10, "max": 50 }`, never `10-50` or a string.
- Range endpoints preserve their stored values, even if `min` exceeds `max`.
  For example, Bloodmoon's `shadowstrike_en` stores effect 40 as 200–100.
  The exporter does not swap or normalize these values.
- `enchantp` retains stored enchantment capacity units, matching the requested
  example: Goldbrand is `700`. Divide by ten for usable enchantment points.
- `enchantment` is `null` when absent. Otherwise it embeds the referenced ENCH
  record with ID, cast type, base cost, charge pool, auto-calculation flag, and
  effects. `charges` is the charge pool, not a count of uses. Auto-calculated
  gameplay costs can differ from stored base costs.
- Effect durations are seconds; effect areas are feet. Zero values are retained.
  `skill` and `attribute` are null when the effect does not target them.
- Ingredient effects retain their original zero-based slot. They do not invent
  magnitude, duration, or range, which are not stored in ingredient records.
- `quality`, `weight`, and other floats preserve decoded values; binary float
  precision can produce values such as `0.800000011920929`.
- Book `text` preserves the game's original markup. Light duration `-1` is the
  infinite-duration sentinel. Light color is exposed as RGB bytes.
- Armor rating and item values are base record values, not player-adjusted stats.
- `model`, `icon`, and `script` preserve asset/script references, when provided.
  Armor and clothing body parts preserve numeric slot IDs and male/female IDs.
- These are item definitions. Stack counts, current durability/charge, ownership,
  and souls contained in individual soul gems belong to a future instance schema.
- The exporter resolves plugin overrides before expanding enchantments.
  Samples have not been resolved against the active mod load order.

Goldbrand's inspected ENCH record is: when strikes, base cost 5, charge pool 50,
Fire Damage 10–30 points on touch for 1 second, area 0, auto-calculate enabled.

Weapon type codes are ordered by TES3 type index: `SB1H`, `LB1H`, `LB2H`,
`BL1H`, `BL2C`, `BL2W`, `SP2H`, `AX1H`, `AX2H`, `BOW`, `CROSSBOW`, `THROWN`,
`ARROW`, `BOLT`. Armor/clothing `type` describes the equipment piece; armor weight
class requires game-setting-dependent classification and is not guessed here.

## Sources and scripts

Sample bytes came from the local Morrowind.esm. Structural references:
[OpenMW weapons](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadweap.hpp),
[armor](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadarmo.hpp),
[clothing](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadclot.hpp),
[lights](https://raw.githubusercontent.com/OpenMW/openmw/master/components/esm3/loadligh.hpp).

`create_templates.py` generates schemas and missing empty datasets, preserving
existing dataset files. `inspect_samples.py` selects a single record of each type
plus Goldbrand's enchantment, seeking past unrelated payloads. `format_samples.py`
formats those specific samples only; it is not a general-purpose exporter.

`export_items.py` is the full exporter. See the root README for local VS Code
instructions. Its run report is metadata, not an additional inventory category.
