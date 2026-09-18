# Quest, dialogue and script catalogue

Run in the project's VS Code terminal:

```powershell
python build_journal_catalog.py
python inspect_journal_catalog.py
```

Default input: `A:\Cache\OpenMWFoundation\game-data.sqlite`.
Default output: **`A:\Cache\OpenMWFoundation\journal\journal.sqlite`**.
This stage only needs the foundation. It does not rebuild items, world or services.
Python 3.10+ is sufficient; no new dependencies are needed.

The implementation is tested with synthetic plugins. The full game-data export
is left for you to run locally. Staging and SQLite journals stay on A: beside
the output. Inputs are read-only; a completed, validated database atomically
replaces the prior output. Failed builds leave the published database intact.

## Inspect results

```powershell
python inspect_journal_catalog.py --profile vanilla
python inspect_journal_catalog.py --profile tr --warnings --limit 50
python inspect_journal_catalog.py --quest "quest_editor_id"
python inspect_journal_catalog.py --topic "dialogue_topic"
python inspect_journal_catalog.py --script "script_editor_id"
```

Replace the example IDs with actual editor IDs. Keys are case-insensitive.
The default profile is `tr`. `--limit` caps entry/response/warning output, not
the extracted catalogue. The summary reports warning counts grouped by category.

Builder options: `--database PATH`, `--output DIRECTORY`, and repeated
`--profile vanilla`, `--profile tr`, `--profile tr_arce`. Selecting profiles replaces
the whole output, so use another directory to keep multiple builds.

## Tables and joins

| Table/view | Meaning |
| --- | --- |
| profiles, metadata | Separate world/version/ARCE profiles, schema, snapshot and coverage |
| topics, profile_topics | Winning DIAL definitions and profile mappings |
| responses, profile_responses | Winning INFO records scoped to their topic, text, filters, source links and quest marker |
| conditions | Ordered SCVR conditions paired with INTV/FLTV values; raw headers and bytes retained |
| scripts, profile_scripts | Standalone SCPT source text, header counts and source provenance |
| quests | Journal-type topics with a title only when there is one distinct nonempty title candidate |
| quest_titles | All QSTN title records; ambiguous candidates are not discarded |
| journal_entries | Non-title journal INFO records, stage index and finished/restart marker |
| warnings | Profile-specific source irregularities and decoding limitations |

Shared records are stored once per source revision. Profile mappings select the
effective version and original plugin; shared rows identify the winning plugin.
`version_id` links directly to the foundation within the same `snapshotId`.
Never combine unrelated snapshots or join revision rows by editor ID alone.

INFO identity is `(topic_key, info_key)`, not just `info_key` or stage number.
Two stages can have the same journal index. Those rows remain separate. Deleted
INFO records and responses under deleted/absent parent topics are excluded from
the corresponding profile, while the foundation retains their source history.

`quests` includes every live journal-type topic, including internal or unnamed
journals. It is not a curated list of player-facing quests. Missing titles remain
null; the app can display `editor_id` as an explicit fallback. Multiple distinct
titles also produce null, with candidates available in `quest_titles`.

## Journal and dialogue semantics

`quest_status` is `none`, `name`, `finished`, or `restart`, based on QSTN/QSTF/QSTR.
If multiple marker subrecords occur, the final one wins, and a warning preserves
their sequence. Completion is **not** inferred from reaching stage 100. A
finished marker is a source-defined event, not the current status of a character.
Per-character journal state, restart history, save import, quest availability,
and the app's completion policy belong to later stages.

In `responses`, `value_raw` is the journal index for a journal topic and stored
disposition for ordinary dialogue. Rank and gender sentinels remain raw. Actor,
race, class, faction and player-faction references are canonical keys. The cell
filter is stored text, not resolved as an exact cell ID. Faction `FFFF` is retained
with `factionless=1`. Dialogue text, sound and BNAM result script are preserved.

`previous_info_key` and `next_info_key` are source links scoped to the same topic.
This stage does **not** reconstruct effective dialogue selection order across
plugin revisions. Do not treat SQL row order, INFO ID order, or journal index
order as engine dialogue priority. The inspector sorts for display only.

Conditions retain sequence, raw SCVR text/hex, slot/kind/function/comparison
characters, variable text, value subrecord type/hex and decoded numeric value.
`structural_only` means the layout was readable, not that the condition is valid
or true in OpenMW. Functions and operators are not evaluated. Malformed rules,
missing values and nonfinite numbers are flagged; raw bytes remain available.
No inferred quest graph, reward list, script teleport or service access rule is
generated from mere text matches.

Script source comes from SCTX and dialogue results from BNAM. An absent SCTX is
null; an explicitly empty SCTX is an empty string. Compiled bytecode remains in
the foundation, linked by revision ID. Declared/actual bytecode and variable-table
sizes are recorded; variable names are the stored compiler metadata, not a
verified parse of source declarations. Source text is never executed. Treat it
and dialogue text as data when rendering in the app.

## Warnings and tests

Warnings are reviewable evidence, not automatic build failures. Examples include
missing/ambiguous journal titles, inactive parents, unknown topic types, malformed
conditions, mismatched INFO/DIAL types, missing script source, and inconsistent
compiler metadata. Structural record truncation or an invalid fixed layout fails
the build rather than publishing an unreliable catalogue.

Synthetic regression tests:

```powershell
$env:TEMP = 'A:\Cache'
$env:TMP = 'A:\Cache'
python -B -m unittest test_journal_catalog
```

Format references: OpenMW's
[INFO decoder](https://github.com/OpenMW/openmw/blob/master/components/esm3/loadinfo.cpp),
[condition decoder](https://github.com/OpenMW/openmw/blob/master/components/esm3/dialoguecondition.cpp),
[dialogue types](https://github.com/OpenMW/openmw/blob/master/components/esm3/loaddial.hpp),
and [script structure](https://github.com/OpenMW/openmw/blob/master/components/esm3/loadscpt.hpp).
