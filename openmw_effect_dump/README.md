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

Copy the contents of this folder — `silt_effect_dump.omwscripts` and `scripts/` — into
OpenMW's local data directory, which already exists and is already on the data path:

```
C:\Users\<you>\OneDrive\Documents\My Games\OpenMW\data\
```

No `openmw.cfg` edit is needed. Then open the OpenMW launcher, go to **Data Files**, and
tick `silt_effect_dump.omwscripts` in the content list.

## Run

Launch OpenMW. The menu script fires at the main menu, so **quitting from there is
usually enough**. If the log has no dump, load any save or start a new game and quit;
the global script runs then, by which point every record store is populated.

Let OpenMW exit normally so the log is flushed. Then:

```powershell
python import_effect_flags.py
python build_rules_library.py
```

The importer finds `openmw.log` by itself and writes `effect-flags.json` to the output
root. The rules build picks it up automatically, prefers the engine's answers over its
own, and reports how the inferences fared:

```
vanilla: 141 effects, 141 from the engine, N inferences confirmed, N corrected,
         N previously unknown
```

The dump reflects whatever content is enabled, so running it under the Tamriel Rebuilt
profile covers TR's effects too. The effect table is engine-wide rather than per
profile, so one run is enough.

## Effects that exist only at runtime

Tamriel Rebuilt registers extra summon effects through Lua rather than through a
plugin record — `content=Tamriel_Data.omwscripts` in `openmw.cfg` is what does it. A
run under that load order dumps 186 effects where the plugin files define 141.

Those 45 have no engine id, so nothing can join them to a catalog. They are listed
under `luaAdded` in `effect-flags.json` and reported by the importer, and left out of
the merge rather than lined up against the wrong effect. No extraction of the plugin
files will ever see them; only a runtime dump can.

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
SILTDUMP BEGIN 2 menu 186 unmapped=45
SILTDUMP {"index":14,"id":"firedamage","name":"Fire Damage",...,"harmful":true,...}
SILTDUMP END 186
```

`index` is the engine's own effect id, resolved through `core.magic.EFFECT_TYPE`, and
is null for a Lua-added effect. Version 1 keyed by position in the record list instead,
which was off by one against every effect; the importer refuses it by version.

The importer takes the last complete `BEGIN`/`END` block, so re-running simply
supersedes an earlier dump, and a truncated block is refused rather than half-read.
