# Script and dialogue acquisition evidence

Run locally in VS Code after the journal and world catalogues:

```powershell
python build_script_evidence.py
python inspect_script_evidence.py
python inspect_script_evidence.py --item katana_goldbrand_unique
```

Output: **`A:\Cache\OpenMWFoundation\script-evidence\script-evidence.sqlite`**.
Inputs are the existing `journal/journal.sqlite` (1.0.0) and `world/world.sqlite`
(1.1.1) under the foundation output directory. Their snapshots and selected
profile definitions must match. No real-data export is run during implementation;
verification uses synthetic fixtures. Python 3.10+ is sufficient.

## Evidence supplied

Builder 1.0.1 recognizes compact `if(...)`, `elseif(...)`, and `while(...)`
headers and distinguishes declared local variables/assignment targets from
command occurrences. Original source text and the database schema stay unchanged.
Re-run `python build_script_evidence.py` to regenerate contexts and warnings;
the world and journal catalogues do not need rebuilding. The output metadata
records `builderVersion` separately from `schemaVersion`.

The scanner reads standalone SCPT source and INFO dialogue result scripts.
It recognizes these commands at the beginning of a physical line, optionally
preceded by a receiver and `->`:

- `AddItem`, `RemoveItem`
- `PlaceItem`, `PlaceItemCell`, `PlaceAtPC`, `PlaceAtMe`
- `AddToLevItem`, `RemoveFromLevItem`, `AddToLevCreature`, `RemoveFromLevCreature`
- `Journal`, `SetJournalIndex`, `StartScript`, `StopScript`

Commands and ID lookup are case-insensitive. Quoted IDs, commas and semicolon
comments are supported. Command-looking text in comments or quoted messages is
not treated as an instruction. Other commands, compiler extensions, Lua, compiled
bytecode, multiline statements and more complex syntax are outside coverage.
The scanner is not the OpenMW compiler and does not validate a full program.

Each event retains the source revision, line number, complete line, command,
arguments, candidate target ID, explicit receiver (if any), literal count when
simple, and lexical context. Negative counts remain negative. Expressions are
not calculated. `target_status=resolved` only confirms a compatible target
definition exists; it does not prove the command is valid or reachable.

Inventory additions and removals are separate event kinds. A removal is not an
acquisition source. An explicit `player` receiver is distinguished from an
implicit script/dialogue context; implicit recipients are never assumed to be
the player. Creation commands retain coordinate/destination arguments without
inventing world placements. List mutations retain both list and target arguments;
only the target object receives profile resolution in this version.

Context retains enclosing `if`/`elseif`/`else`/`while` blocks, previous branches
of the current conditional, and preceding return/break/continue statements with
their enclosing blocks. These are raw evidence, **not evaluated path conditions**.
In particular, an `else` branch is not treated as unconditional, and a preceding
`return` does not automatically make later code unreachable. The complete source
text remains in the `sources` table for further analysis.

Dialogue context includes actor/race/class/faction/cell filters, raw numeric
criteria, quest markers and ordered SCVR conditions from the journal catalogue.
A topic is not automatically a quest or a quest reward. Script attachments identify
world object definitions referencing a script; they are not runtime references,
proof of script execution, or item locations.

## Tables

| Table | Contents |
| --- | --- |
| metadata, profiles | Source snapshot/build metadata, command coverage, separate Vanilla/TR/ARCE profiles |
| sources | Shared script/result revisions, full source, provenance and dialogue context |
| profile_sources | Profile membership and original plugin |
| events | Shared lexical command events with source lines, arguments and context |
| profile_events | Target resolution in the selected profile |
| script_attachments | World definition revisions attached to standalone scripts |
| warnings | Shared parser warnings and profile-specific target/argument warnings |

Revision IDs refer to the same foundation snapshot as the other catalogues.
Rebuild this evidence catalogue after rebuilding its inputs. It does not rewrite
the static acquisition index or expand command evidence into acquisition paths.
Consumers should show static sources and script evidence with their distinct
coverage and uncertainty.

## Inspection and warnings

```powershell
python inspect_script_evidence.py --profile vanilla --item katana_goldbrand_unique
python inspect_script_evidence.py --warnings --limit 50
```

The item query returns additions, removals and other matching target events with
their kinds intact. `--limit` defaults to 30 events and caps at 1,000. `truncated`
reports extra matching events. Attachments cap at 100 per event and expose
`attachmentsTruncated` separately. This query can also find a script/journal ID
used by the supported control commands, despite the option name `--item`.

The summary groups warnings for the selected profile. Missing script source,
malformed blocks/quotes, unsupported command positions, unfamiliar argument
shapes, nonliteral counts, missing targets and wrong target types are reviewable
evidence. They are not silently promoted into definite grants. Shared parser
warnings have a null stored profile and are included through profile membership
by the inspector. A clean summary does not establish full compiler validity.

This stage does not traverse script calls, infer reward locations, evaluate quest
access, or apply the theft/danger/spending rules. A source can contain a command
without any playthrough executing it. Definitions spawned or changed by commands
remain evidence for a later analysis layer.

Builder options: `--journal-database PATH`, `--world-database PATH`, `--output DIR`,
and repeated `--profile vanilla`, `--profile tr`, `--profile tr_arce`. All profiles
are included by default. A profile selection replaces the entire output. Input
databases are read-only; staging and journals stay beside the destination on A:.
Failed or cancelled builds preserve the previously published database.

Tests: set `TEMP` and `TMP` to `A:\Cache`, then run
`python -B -m unittest test_script_evidence`.

Supported command argument layouts were checked against the
[OpenMW compiler registrations](https://github.com/OpenMW/openmw/blob/master/components/compiler/extensions0.cpp).
