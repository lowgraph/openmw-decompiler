# Typed catalog builder

Run in this project's VS Code terminal:

```powershell
python build_catalogs.py
```

Or choose **Build typed catalogs** in Run and Debug. Python 3.10+ is sufficient;
there are no new dependencies. This reads the completed foundation database
read-only. It never accesses installed plugins or modifies old item JSONs.

The default input is `A:\Cache\OpenMWFoundation\game-data.sqlite`.
Output and all staging files stay under `A:\Cache\OpenMWFoundation\catalogs`.

## Outputs

`current.json` points to an immutable release directory named by a hash of the
source snapshot, builder version, and selected profiles. Read its `manifest` path
to find profile counts and missing-reference warnings. All three profiles are built
by default: `vanilla`, `tr`, `tr_arce`.

Each profile folder contains **21 catalogs**, plus `BookText`:

- Weapons, Armor, Clothing, Books, Potions, Ingredients, Apparatus, Lockpicks,
  Probes, RepairTools, Lights, Miscellaneous.
- Enchantments, MagicEffects, Spells, Races, Classes, Birthsigns, Skills,
  Attributes, GameSettings.
- `BookText` holds book prose, keyed to `Books.records[].key`. Prose is about 70%
  of a profile's bytes and no calculator reads it, so it is stored separately and
  left out of the shipped bundle by default. Book skill, scroll, value, weight and
  enchantment fields stay in `Books`. This is schema 1.1.0; in 1.0.0 `text` was a
  field of each book record.

Files contain `records` arrays, with `schemaVersion`, `snapshotId`, `recordType`,
and `profile` metadata. See `catalog-types.ts` for the app-facing TypeScript contract.
The old `items/*.schema.json` schemas describe the earlier exports, not this format.

## IDs, profiles, and joins

- `id` preserves the original record's spelling; `key` is the foundation's canonical
  case-insensitive key. Numeric SKIL/MGEF keys are decimal strings.
- Join using **record type + key**, within the same profile and source snapshot.
- `provenance.originPlugin` and `winningPlugin` identify source history. The
  `recordVersionId` links back to the foundation within this snapshot only.
- `gameDataVersion` describes the resolved profile, not the original plugin's world.
  A vanilla-origin sword in TR keeps its origin provenance but uses the TR profile
  version. This avoids combining vanilla and modded effective stats accidentally.
- Item `sourcePlugin` remains a compatibility alias for the winning plugin.
- Enchantable items use `enchantmentId` to join `Enchantments.records[].key`.
  Enchantment effects are no longer duplicated inside every item.
- Effects retain numeric `effectId` and add string `effectKey` for joining MagicEffects.
  For alchemy, the identity includes the effect ID **and its skill/attribute target**.
- Races and birthsigns reference Spells using `spellIds`. Skills use both the numeric
  source key and the semantic `skill` identifier used by skill bonuses/classes.

## Fields and limits

The twelve item categories retain existing decoded properties, including raw
`enchantp` capacity units and unswapped damage endpoints. Carryable lights are
included; world-only lights remain available in the foundation, not this inventory
catalog. No location paths are expanded.

Race attributes are male/female pairs per attribute. Class minor/major skills are
decoded from their alternating binary slots. Both playable and nonplayable
races/classes are preserved; the app should filter `playable` for character creation.

Spells include powers, abilities, and diseases, not only castable spells. `playerStart`
means eligible for starting-spell selection, not guaranteed learned by every character.
Enchantments expose stored cost, charges, effects, and auto-calculation flags.

MagicEffects exposes stored base costs, school, asset IDs, color, and raw MEDT flags.
The spellmaking/enchanting availability bits are decoded, and they are the only two the
plugin files carry: every effect's MEDT flags are either 1536 or 0. **Engine-fixed
targeting, no-magnitude/no-duration, harmful-effect, and display-unit rules are not
synthesized here.** `build_rules_library.py` now derives targeting, no-magnitude and
no-duration from content usage and publishes them as `EffectRules`; harmful-effect flags
and display units remain unavailable. See [RULES.md](RULES.md). This is data supply, not a new
implementation of alchemy or spellmaking calculations.

GameSettings preserves string/integer/float distinctions and represents an unset
record with `valueType: unset` and `value: null`. Attributes are the eight fixed
engine identifiers, with display names obtained from each profile's settings; they
are derived rows, not plugin records with invented provenance.

Binary sizes and enum bounds are checked by decoders; JSON serialization rejects
NaN/Infinity. Missing enchantment/effect/spell catalog links are reported in the
manifest rather than silently removed. Effect display-name lookup failures stop
the build. These checks are not a claim that every game reference is complete.

Only one catalog's output is accumulated at a time. The source lookup is lazy and
does not load CELL/LAND or other world-record payloads. Publication uses a versioned
directory followed by atomic `current.json` replacement, so readers do not see a
mixture of profile generations. Failed builds leave the prior active pointer intact.
Completed releases are retained; they are not deleted automatically.

## Options and verification

```powershell
python build_catalogs.py --profile vanilla
python build_catalogs.py --database A:\Cache\OpenMWFoundation\game-data.sqlite --output A:\Cache\CatalogPreview
python -m unittest test_catalogs -v
```

Repeat `--profile` to select several. An identical existing release is not overwritten;
use a different output directory to rebuild it. Close any running previous builder
before removing a stale `build.lock` left by a forced kill. Normal completion or
Ctrl+C removes its lock/staging files. A crash after release creation but before
pointer publication can leave an inactive release directory.

Tests cover race/class binary ordering, numeric settings, magic-effect/skill layouts,
profile deletions, source provenance, shared enchantment joins, and atomic publication.
The implementation was also checked read-only against all three profiles of the
existing foundation; no full catalogs were written during that verification.

Record layout references: OpenMW's `components/esm3/loadrace.cpp`, `loadclas.cpp`,
`loadspel.hpp`, `loadskil.hpp`, and `loadmgef.hpp` in the upstream source repository.
