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

## Install

Copy the contents of this folder — both `.omwscripts` files and `scripts/` — into
OpenMW's local data directory, which already exists and is already on the data path:

```
C:\Users\<you>\OneDrive\Documents\My Games\OpenMW\data\
```

No `openmw.cfg` edit is needed, and nothing needs ticking in the launcher: the driver
below passes the content file on the command line.

## Run

From the project root:

```powershell
python dump_profiles.py
python build_rules_library.py
```

`dump_profiles.py` launches OpenMW once per profile, with `--replace=content` so
nothing from `openmw.cfg` leaks in and only that profile's own load order is present.
The auto variant quits the game as soon as it has printed, so each window opens and
closes on its own. Each run is imported to `<root>/effect-flags/<profile>.json`, and
the rules build reads each profile's own file:

```
vanilla: 141 effects, 141 from the engine, N inferences confirmed, N corrected,
         N previously unknown
tr: 186 effects, 186 from the engine, ..., 45 registered by Lua and in no plugin file
```

Use `--dry-run` to see the commands without launching anything, and `--profile tr` to
do one.

### By hand instead

Tick `silt_effect_dump.omwscripts` in the launcher's **Data Files** and play normally.
The menu script fires at the main menu, so quitting from there is usually enough; if
the log has no dump, load any save and quit, which runs the global script. Let OpenMW
exit normally so the log is flushed, then `python import_effect_flags.py --profile tr`.
Use this when you want to keep the window open, not for a routine rebuild: what gets
dumped is then whatever the launcher had ticked, which is easy to get wrong.

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
touch no game state, and are wrapped so a failure prints a marked error line rather than
disturbing the game. Untick the content file when you are done; nothing persists in a
save.

## Reading the output by hand

Each line is one JSON object:

```
SILTDUMP BEGIN 3 menu-auto 186
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
