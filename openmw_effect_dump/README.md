# OpenMW effect dump

A small OpenMW Lua mod that prints the engine's magic effect table to `openmw.log`,
so the rules library can use facts instead of inferences.

## Why it exists

Morrowind's plugin files carry only two of an effect's flags. Targeting, whether an
effect has a magnitude or a duration, and whether it is harmful all live in the engine.
OpenMW publishes them through `core.magic.effects.records`, documented in your own
install at `resources/lua_api/openmw/core.lua`.

The Lua sandbox has no `io`, and `openmw.vfs` is read-only, so there is no way to write
a file from inside the game. `print` goes to `openmw.log`, and that is the way out.

## There is nothing to install

Leave this folder where it is. `dump_profiles.py` passes it to the game as
`--data=<this folder>`, so the scripts are on the data path for that one run only and
nothing is copied into `My Games\OpenMW\data`, nothing is ticked in the launcher, and
`openmw.cfg` is not touched.

Copying the `.omwscripts` files on their own does not work, and is the obvious mistake:
they are two-line pointers at `scripts/silt_effect_dump/*.lua`, so without the
`scripts/` folder beside them OpenMW finds nothing to run.

## Run

From the project root:

```powershell
python dump_profiles.py
python build_rules_library.py
```

`dump_profiles.py` launches OpenMW once per profile with `--replace=content`, so
nothing from `openmw.cfg` leaks in and only that profile's own load order is present.
It watches `openmw.log`, and closes the game as soon as the dump lands — about five
seconds per profile. Each run is imported to `<root>/effect-flags/<profile>.json`, and
the rules build reads each profile's own file:

```
vanilla: 141 effects in 6s -> vanilla.json
tr:      186 effects in 4s -> tr.json
         names used more than once: Corruption, Wabbajack
```

Use `--dry-run` to see the commands without launching anything, `--profile tr` to do
one, and `--mod` if this folder is somewhere else.

**Nothing in the mod quits the game**, deliberately. An earlier version called
`core.quit()` while the menu script was still loading; the window vanished a second
after launch, which is indistinguishable from a crash. Deciding when to stop is the
driver's job, and it decides from the log.

### By hand instead

Tick `silt_effect_dump.omwscripts` in the launcher's **Data Files** — after adding this
folder as a data directory, so the scripts come with it — and play normally. The menu
script fires at the main menu, so quitting from there is usually enough; if the log has
no dump, load any save and quit, which runs the global script. Let OpenMW exit normally
so the log is flushed, then `python import_effect_flags.py --profile tr`.

Use this when you want to keep the window open. It is not the routine path: what gets
dumped is then whatever the launcher had ticked, which is easy to get wrong, and the
`--profile` you pass is a claim about that rather than something the tool arranged.

## Effects that exist only at runtime

Tamriel Rebuilt registers 45 extra effects through Lua rather than through a plugin
record — `Tamriel_Data.omwscripts` is what does it, and `Tamriel_Data.esm` contributes
no MGEF records at all. A run under that load order dumps 186 effects where the plugin
files define 141, and 39 of the 45 are available for spellmaking and enchanting.

They are real effects with real ids; they simply appear in no plugin file, so no
extraction will ever find them and only a runtime dump can. The rules library publishes
them with `extracted: false` and a null `effectId`, keyed by the engine's own string id.

This is why the dump is per profile. The engine's list is whatever the load order
produced, so one dump describes one load order — merging a TR dump into vanilla would
hand vanilla 45 effects it does not have.

## What it does not collect

Display units — whether a magnitude reads as points, a percentage, levels or feet — are
not in the effect record. OpenMW decides those in its interface. Nothing here claims
them, and the rules library leaves them absent rather than guessing.

## Safety

The scripts only read and print. They register no event handlers that change anything,
touch no game state, quit nothing, and are wrapped so a failure prints a marked error
line rather than disturbing the game. A driven run loads them for that run alone, so
there is nothing to undo afterwards.

## Reading the output by hand

Each line is one JSON object:

```
SILTDUMP BEGIN 3 menu 186
SILTDUMP {"id":"firedamage","name":"Fire Damage","school":"destruction",...}
SILTDUMP END 186
```

`id` is the engine's own key for the record, a string. There is no numeric index:
`core.magic.EFFECT_TYPE.WaterBreathing` is the string `"waterbreathing"`, whatever the
`#number` annotation in the API docs says, and iterating the record table with `pairs`
yields positions rather than ids. Version 1 published those positions, which was off by
one against every effect; version 2 published a numeric index that does not exist, and
matched nothing. The join happens on the reading side, on `name`, because two vanilla
effects — Call Wolf and Call Bear — have ids that do not match their names.

The importer takes the last complete `BEGIN`/`END` block, so re-running simply
supersedes an earlier dump, and a truncated block is refused rather than half-read.
