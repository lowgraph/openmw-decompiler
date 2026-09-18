# Unified item-source query

Run locally in VS Code:

```powershell
python query_item_sources.py --item katana_goldbrand_unique
python query_item_sources.py --profile vanilla --item iron_dagger
```

This tool queries the existing world, acquisition and script-evidence databases.
**No new database build is required.** It writes JSON to stdout and does not
modify inputs or automatically create per-item files. Development tests use
synthetic fixtures; real queries are left for you to run locally.

To save a result on A: using PowerShell:

```powershell
python query_item_sources.py --item katana_goldbrand_unique | Out-File -Encoding utf8 A:\Cache\goldbrand-sources.json
```

Check that the command succeeded before consuming a redirected output file.
Errors go to stderr with a nonzero exit code. Python 3.10+ is sufficient.

## Inputs and consistency

Default files under `A:\Cache\OpenMWFoundation`:

- `world\world.sqlite`
- `acquisition\acquisition.sqlite`
- `script-evidence\script-evidence.sqlite`

The selected profile must exist identically in all three files. Snapshot IDs
must match, and both derivative inputs must refer to the current world build.
The tool requires script-evidence builder 1.0.1, including the compact-condition
fix. Mismatches fail rather than silently mixing revisions. Source scripts and
dialogue context are already included in the evidence database; the journal file
does not need to be opened again.

Override paths using `--world-database`, `--acquisition-database`, and
`--evidence-database`. All are opened read-only in SQLite read transactions.
No plugin files are read and no game scripts are executed.

## Response contract

| Field | Meaning |
| --- | --- |
| schemaVersion, snapshotId, inputBuilds | Response version and input generation identifiers |
| profile | Selected Vanilla/TR/TR+ARCE profile, with separate world/version/ARCE fields |
| item | Root item key, name, record type and revision |
| counts | Returned static placements, events, context definitions and context placements |
| static | Bounded reverse containment graph and its direct world placements |
| script.events | Command evidence targeting the item or a discovered static ancestor |
| script.contextAnchors | World definitions identified by attachments, explicit receivers, or exact dialogue actor filters |
| script.contextLinks | Event-to-context links with their explicit role |
| script.contextPlacements | Direct placements of those context definitions, not placements of the item |
| assessment | Obtainability, theft, sale status, price and early-game eligibility remain null |
| truncated, limitReasons | Any cap that left results or potential evidence unexplored |

Script events keep their original source lines, conditions, structural warnings,
unverified arguments and recipient information. Event IDs combine source revision
and line number. `relatedNodeVersionId` joins the event to the static graph;
`relationToItem` distinguishes `direct_target` and `static_ancestor_target`.
For example, a command creating a creature whose inventory contains the item is
reported as ancestor evidence, not as a direct item grant.

`effectCategory` distinguishes additions, removals, creation, list additions,
list removals and control commands. Removal events are never counted as grants.
Matching IDs are lexical evidence; the original target status/type information
remains visible, including ambiguous or invalid cases.

An attached shrine or a dialogue actor may provide useful context for a reward.
Its location does not prove the reward occurs there, is currently available,
or can be safely obtained. Explicit receivers identify definition candidates,
not unique runtime references. Player-relative and coordinate creation commands
retain raw arguments; this tool does not fabricate their resulting placements.

Definitions and context placements are deduplicated. Multiple events can link
to the same context definition through `contextLinks`. Missing or ambiguous
context definitions have an explicit status and receive no guessed placement.
Generic dialogue filtered only by class/faction/cell is not expanded into every
possibly matching NPC. Script-call chains and newly created inventory edges are
not traversed recursively.

The response is evidence for later access, merchant-stock, pricing and danger
rules. It does not apply the theft toggle, 500-gold limit or Mentor's Ring danger
benchmark. Lights come from world definitions; match the typed inventory catalog
before offering carryable/equippable choices to a character.

## Bounds

| Option | Default | CLI ceiling |
| --- | ---: | ---: |
| --max-nodes | 2,000 | 10,000 |
| --max-edges | 5,000 | 50,000 |
| --max-depth | 12 | 100 |
| --max-placements | 100 | 10,000 |
| --max-events | 100 | 1,000 |
| --max-script-targets | 200 | 10,000 |
| --max-anchors | 100 | 1,000 |
| --max-anchor-placements | 100 | 10,000 |

Depth may be zero; other limits must be positive. Attachments additionally inherit
the evidence inspector's cap of 100 per event. Every applicable truncation flag
propagates to the top-level response with a `static:` or `script:` reason.
`truncated=false` means complete within the implemented static/lexical scope,
not every possible in-game way to acquire the item.

The default profile is `tr`; use `--profile vanilla` or `--profile tr_arce` as
needed. `--type WEAP` (or another item record type) disambiguates duplicate IDs.

Synthetic regression tests:

```powershell
$env:TEMP = 'A:\Cache'
$env:TMP = 'A:\Cache'
python -B -m unittest test_item_sources
```
