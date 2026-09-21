# Rebuilding after an update

Nothing here needs running while the inputs stay the same. On unchanged inputs the
pipeline reproduces the same data; only the file hashes differ, because every output is
timestamped.

Rebuild when one of these changes:

| What changed | What to rerun |
|---|---|
| The site's premade builds, `lib/premade-data.mjs` | Run [the check](#the-sites-builds); it says what |
| `policy/late-game.json` | `build_best_in_slot_catalog.py`, then [publish](#publish) |
| `policy/early-game.json` | `build_gear_rows.py` and `build_best_in_slot_catalog.py`, then publish |
| `policy/travel.json` | `build_travel_catalog.py`, then publish |
| `policy/journal-titles.json` | `build_quest_catalog.py`, then publish |
| A plugin: Tamriel Rebuilt, Tamriel_Data, Project Tamriel or ARCE | [Everything](#full-rebuild) |
| OpenMW itself | Everything, and [compare two engine functions](#after-an-openmw-update) |

Run everything from this folder, in PowerShell.

**The mistakes this list used to warn about are refusals now.** A stale version label,
a plugin nobody listed, a skipped or stale effect dump, a smoke run landing among the
real rows, formulas copied from another engine release: each stops the step that would
have gone wrong, says what happened, and leaves the published bundle alone.
[The table below](#when-a-step-refuses) lists every one.

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

After a plugin update, two things only you can do:

1. **Point OpenMW at the new version.** Extraction reads the `data=` lines of your
   `openmw.cfg`, and a later folder wins, as it does in the game. The folder name must
   still start with one of `allowedModPrefixes` in `export_config.json`.
2. **Update `versions` in `export_config.json`.** Every record carries this label.
   Extraction checks it against the files themselves — the Tamriel Rebuilt label
   against the release `TR_Mainland.esm` states in its header, the vanilla label against
   what `openmw.exe --version` reports — and refuses a label they contradict.

If the release added a plugin, extraction names it and stops: add it to a profile in
`foundation_config.json` (and to `allowedPlugins`), or to `ignoredPlugins` in
`export_config.json` to leave it out on purpose.

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
python build_gear_rows.py
python build_travel_catalog.py
python build_quest_catalog.py
python build_merchant_catalog.py
python build_places_catalog.py
python build_faction_catalog.py
python build_best_in_slot_catalog.py
python build_app_bundle.py
node A:\Claude\morrowind-tools\scripts\stage-game-data.mjs
```

- Every step covers all three profiles unless given `--profile`. Gear rows is the slow
  one, about twenty minutes a profile.
- `dump_profiles.py` launches OpenMW once per profile. A window opens for a few seconds
  and closes itself. Each dump records the extraction and the OpenMW release it was
  taken under.
- Skipping a step cannot produce a quietly stale bundle. Every catalog is pinned to the
  extraction's snapshot and the bundler refuses one built from another; the rules step
  refuses an effect dump from another extraction, or a missing one.
- The JSON exporters (`export_items.py`, `export_locations.py`) are earlier prototypes
  and play no part in the bundle.

Then verify:

```powershell
python build_best_in_slot_catalog.py --check
$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"
```

and `npm test` in the site. Read the bundler's last line too. The site hardcodes
formulas built on game settings — the level-up multipliers in `lib/level-math.mjs`,
armour, encumbrance — which hold in every profile only because, as of September 2026,
no Tamriel plugin and not ARCE contains a single one. The bundler says
`Game settings are identical in every profile` while that holds, and names the settings
when it stops holding; tell Codex which.

## When a step refuses

After an update, a refusal is a question for you, not a crash, and the previous bundle
stays live. Resume from the step that refused: each policy file is read only by that
step or later ones, so the earlier output is still good.

| The message says | Step | What happened | What to do |
|---|---|---|---|
| `A version label in export_config.json is stale` | extraction | The label names an older release than the files | Update `versions` in `export_config.json` |
| `content file(s) in approved folders belong to no profile` | extraction | A release added a plugin or script | Add it to a profile, or to `ignoredPlugins` |
| `states no version to check the ... label against` | extraction | The header no longer says `v. 26.08` | Point `versionEvidence` at a plugin that does |
| `These plugins changed since the last extraction` | effect dump | The game would load other files than were extracted | Run `extract_foundation.py` first |
| `OpenMW reports ..., but the extraction is labelled` | effect dump | OpenMW was updated after extracting | Update `versions.vanilla`, then extract again |
| `effect dump was taken against` or `No effect dump for` | rules | The dump is stale or was skipped | Run `dump_profiles.py`, then the rules |
| `transcribed from OpenMW` | merchants | A new engine release | See [below](#after-an-openmw-update) |
| `A partial run (--limit or --category)` | gear rows | A smoke run aimed at the real rows | Pass `--output` with a scratch folder |
| `constant effect(s) appear on candidates but the late-game policy does not cover them` | best-in-slot | A new item carries an effect with no tier | Add it to `effects` or `drawbacks` in `policy/late-game.json` |
| `effect(s) in policy/late-game.json appear on no candidate` | best-in-slot | The last item carrying it is gone | Remove it, or check its spelling |
| `Conjurer edge(s) in policy/travel.json match nothing` | travel | A city was renamed, or its guide changed | `conjurerRank.cities` in `policy/travel.json` |
| `The guild guide rule assumes a provider never mixes` | travel | A guide now mixes guild and other destinations | The guild guide rule in `policy/travel.json` |
| `authored journal title(s) match no untitled quest` | quests | The quest now names itself, or its key changed | Remove or correct it in `policy/journal-titles.json` |
| `near-start place(s) in the policy match no cell` | gear rows | A starting town was renamed | `earlyGame.nearStart.places` in `policy/early-game.json` |
| `Benchmark cell ... has no hostiles` | gear rows | The danger benchmark moved or emptied | `earlyGame.danger` in `policy/early-game.json` |
| `was built from a different snapshot than the catalogs` | bundle | A step was skipped | Rerun the catalog it names |
| `cell(s) named by ... are not in Places` | bundle | Two catalogs from different extractions | Rebuild both |

## After an OpenMW update

Update `openmwExecutable` and `versions.vanilla` in `export_config.json` and do the
full rebuild. Extraction checks the label against the new binary.

Two pieces of the pipeline are transcribed from OpenMW's source rather than read from
data, and no rebuild can update them. They were checked line by line against tag
`openmw-0.51.0` (commit `f4bec41444`), including `npc.cpp`'s own `round_ieee_754`,
which rounds ties to even as Python does. `build_merchant_catalog.py` stops while the
extraction names any other release, and says what to compare:

| Transcribed in | From |
|---|---|
| `BARTER_FORMULA` in `build_merchant_catalog.py` | `MechanicsManager::getBarterOffer`, `apps/openmw/mwmechanics/mechanicsmanagerimp.cpp` |
| `autocalc.py` | `autoCalculateAttributes` and `autoCalculateSkills`, `apps/openmw/mwclass/npc.cpp` |

If both functions are unchanged in the new release, set `TRANSCRIBED_FROM` in
`build_merchant_catalog.py` to it; if not, transcribe them again. `effect_names.py` is
not on this list: it maps Morrowind's fixed effect-name settings, a property of the file
format rather than of the engine.

The effect dump goes through OpenMW's Lua API. If that API changes, `dump_profiles.py`
stops with `No dump appeared within 600s` or `OpenMW closed without printing a dump`
rather than guessing.
