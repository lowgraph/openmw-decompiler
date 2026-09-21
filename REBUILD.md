# Rebuilding after an update

Nothing here needs running while the inputs stay the same. On unchanged inputs the
pipeline reproduces the same data; only the file hashes differ, because every output is
timestamped.

Rebuild when one of these changes:

| What changed | What to rerun |
|---|---|
| The site's premade builds, `lib/premade-data.mjs` | Run [the check](#the-sites-builds); it says what |
| `policy/late-game.json` | `build_best_in_slot_catalog.py`, then [publish](#publish) |
| `policy/early-game.json` | `build_gear_rows.py` once per profile and `build_best_in_slot_catalog.py`, then publish |
| `policy/travel.json` | `build_travel_catalog.py`, then publish |
| `policy/journal-titles.json` | `build_quest_catalog.py`, then publish |
| A plugin: Tamriel Rebuilt, Tamriel_Data, Project Tamriel or ARCE | [Everything](#full-rebuild) |
| OpenMW itself | Everything, plus [the hand checks](#after-an-openmw-update) |

Run everything from this folder, in PowerShell.

## The site's builds

```powershell
python build_best_in_slot_catalog.py --check
```

It builds nothing. It compares the site's current builds with the digest carried by the
catalog, the bundle and the copy the site serves, exits 0 when all three match, and
otherwise prints the commands still needed, starting from the first stale stage.

Run it whenever the site's builds may have changed, because nothing else notices. A new
build is harmless — the site scores it in the browser — but a build that keeps its name
and changes its skills goes on showing the picks for its old self.

## Publish

Every change ends with these two:

```powershell
python build_app_bundle.py
node A:\Claude\morrowind-tools\scripts\stage-game-data.mjs
```

Both publish atomically, so a failure anywhere leaves the previous bundle live.

## Full rebuild

Before running anything after a plugin update:

1. **Point OpenMW at the new version.** Extraction reads the `data=` lines of your
   `openmw.cfg`, and a later folder wins, as it does in the game. The folder name must
   still start with one of `allowedModPrefixes` in `export_config.json`.
2. **Update `versions` in `export_config.json`.** Every record carries this label and
   nothing checks it: forget it, and the new data ships labelled as the old version.
3. **If the release adds, drops or renames a plugin,** update `plugins` for each profile
   in `foundation_config.json`, and `allowedPlugins` in `export_config.json`. Extraction
   refuses a listed plugin it cannot find, but it cannot know about one nobody listed.

Then, in order:

```powershell
python extract_foundation.py
python build_catalogs.py
python build_world_catalog.py
python build_journal_catalog.py
python build_acquisition_index.py
python build_script_evidence.py
python build_services_catalog.py
python dump_profiles.py
python build_rules_library.py
python build_gear_rows.py --profile vanilla
python build_gear_rows.py --profile tr
python build_gear_rows.py --profile tr_arce
python build_travel_catalog.py
python build_quest_catalog.py
python build_merchant_catalog.py
python build_places_catalog.py
python build_faction_catalog.py
python build_best_in_slot_catalog.py
python build_app_bundle.py
node A:\Claude\morrowind-tools\scripts\stage-game-data.mjs
```

- Every step takes all three profiles by default except `build_gear_rows.py`, which takes
  one and defaults to vanilla. Hence three lines.
- `dump_profiles.py` launches OpenMW once per profile. A window opens for a few seconds
  and closes itself.
- **Skipping a catalog step cannot produce a quietly stale bundle.** Every catalog is
  pinned to the extraction's snapshot, and the bundler refuses one built from another.
- **The effect dump is not pinned that way, so never skip it.** The rules step refuses a
  dump that lacks an effect the catalogs have, but a dump with the same effects and
  changed flags would pass.
- The JSON exporters (`export_items.py`, `export_locations.py`) are earlier prototypes
  and play no part in the bundle.

Then verify:

```powershell
python build_best_in_slot_catalog.py --check
$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"
python -c "import json; from pathlib import Path; c=Path('A:/Cache/OpenMWFoundation/catalogs'); r=c/json.loads((c/'current.json').read_text())['releaseId']; g={p: {s['key']: s['value'] for s in json.loads((r/p/'GameSettings.json').read_text(encoding='utf-8'))['records']} for p in ('vanilla','tr','tr_arce')}; d=sorted(k for k in set().union(*g.values()) if len({g[p].get(k) for p in g})>1); print(d or 'Game settings are identical in every profile')"
```

and `npm test` in the site. The last line matters to the site more than to this
repository. The site hardcodes formulas derived from game settings — the level-up
multipliers in `lib/level-math.mjs`, armour, encumbrance — and those hold in every
profile only because, as of September 2026, no Tamriel plugin and not ARCE contains a
single game setting. If it prints setting names instead, tell Codex which ones.

## When a guard stops the run

Several steps check the hand-written policy against the new data and refuse to publish
rather than quietly drop something. After an update, a stop is a question for you, not
a crash, and the previous bundle stays live.

| The message says | Step | What happened | Edit |
|---|---|---|---|
| `constant effect(s) appear on candidates but the late-game policy does not cover them` | best-in-slot | A new item carries an effect with no tier | Add it to `effects` or `drawbacks` in `policy/late-game.json` |
| `effect(s) in policy/late-game.json appear on no candidate` | best-in-slot | The last item carrying it is gone | Remove it, or check its spelling |
| `Conjurer edge(s) in policy/travel.json match nothing` | travel | A city was renamed, or its guide changed | `conjurerRank.cities` in `policy/travel.json` |
| `The guild guide rule assumes a provider never mixes` | travel | A guide now mixes guild and other destinations | The guild guide rule in `policy/travel.json` |
| `authored journal title(s) match no untitled quest` | quests | The quest now names itself, or its key changed | Remove or correct it in `policy/journal-titles.json` |
| `near-start place(s) in the policy match no cell` | gear rows | A starting town was renamed | `earlyGame.nearStart.places` in `policy/early-game.json` |
| `Benchmark cell ... has no hostiles` | gear rows | The danger benchmark moved or emptied | `earlyGame.danger` in `policy/early-game.json` |
| `was built from a different snapshot than the catalogs` | bundle | A step was skipped | Rerun the catalog it names |
| `cell(s) named by ... are not in Places` | bundle | Two catalogs from different extractions | Rebuild both |

Then resume from the step that stopped. Each policy file is read only by the step that
refused it or by later ones, so the earlier output is still good.

## After an OpenMW update

Update `openmwExecutable` and `versions.vanilla` in `export_config.json`, then do the
full rebuild. Three pieces of the pipeline are transcribed from OpenMW's source rather
than read from data, and no rebuild can update them. Compare each with the new
version's source; if that code is unchanged, there is nothing to do.

| Transcribed in | From |
|---|---|
| `BARTER_FORMULA` in `build_merchant_catalog.py` | `MechanicsManager::getBarterOffer`, `apps/openmw/mwmechanics/mechanicsmanagerimp.cpp` |
| `autocalc.py` | `autoCalculateAttributes` and `autoCalculateSkills`, `apps/openmw/mwclass/npc.cpp` |
| `effect_names.py` | `sGmstEffectIds`, `components/esm3/loadmgef.cpp` |

The effect dump goes through OpenMW's Lua API. If that API changes, `dump_profiles.py`
stops with `No dump appeared within 600s` or `OpenMW closed without printing a dump`
rather than guessing.
