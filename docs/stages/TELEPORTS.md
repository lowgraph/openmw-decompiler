# Teleports

Run in this project's VS Code terminal, after the script evidence, world and services
catalogs exist:

```powershell
python build_teleport_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\teleports\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Teleports` catalog. See `teleport-types.ts`
for the app contract and a reference `usable`.

## What it finds

Every `Player->PositionCell` and `Player->Position` a script or a dialogue result can
run, read from the full sources the script evidence catalog keeps. Each becomes a
teleport with where it leaves from, where it lands, and what it asks of the player.

```
vanilla   42 teleports   30 Propylon, 5 dialogue, 5 item, 2 activator     5 quest-gated
tr       138 teleports   47 Propylon, 68 dialogue, 17 item, 6 activator  78 quest-gated
tr_arce  identical to tr, so the bundle inherits it
```

- **Propylons.** Each chamber's activator checks the player carries the destination's
  index. With `master_index.esp`, a Master Index in the pack sends every Propylon to
  Caldera's Guild of Mages instead, and Folms Mirel there sends you to any chamber.
  Tamriel Rebuilt adds its own network, gated on `T_De_Index_*`.
- **Dialogue.** A line of dialogue that teleports the player, or starts a script that
  does: Asciene Rane's "transport to Mournhold" starts `MHTransportScript`. It leaves
  from where the speaker stands.
- **Items.** An amulet that takes its wearer to one place: the vampire clans' lairs,
  Magas Volar, Tel Fyr.
- **Activators and doors** that teleport the player when used.

## What it asks of the player

- `requires`: items the script or dialogue checks are carried; for an item teleport,
  the item itself.
- `unless`: items that send the player elsewhere first, from the branches the script
  tries before this one.
- `conditions`: every other test, as text and unevaluated. The activation itself, a
  "Teleport?" menu and its answer, and a dialogue menu choice (`Choice`, function 50 in
  `ESM::DialogueCondition`) are routine and left out.

## Everyday travel, and quest teleports

Most scripted teleports belong to a quest: a scene, a trap, a trip taken once. The
site should route through everyday travel only, so each teleport says whether it is
one. Everyday means a player can take it again whenever they like:

- a Propylon or an item gated only by what the player carries;
- a dialogue gated only by an item (Folms Mirel with the Master Index);
- anything `everyday` in `policy/teleports.json` names (Mournhold, both ways).

Anything else is `questGated`, with `gatedBecause`: `conditions` (a journal, a variable
or a script's own state), `greeting`, `dialogue topic` (a topic only a quest opens),
`activator`, or `authored` (`questOnly` in the policy, for quest teleports whose
conditions do not say so). Quest teleports are still published; the site shows them
only when asked.

Policy rules match on source, topic, speaker, `to` or kind, optionally only in the
listed profiles, and the build fails on a rule that matches nothing in a profile it
applies to, as the travel policy's Conjurer rule does.

## What is left out, and counted

`derivation.skipped` counts every teleport read and not published:

| Reason | What it is |
|---|---|
| `movesSomeoneElse` | The line moves an NPC or an object, not the player |
| `questScriptOnActor` | A script on an NPC or creature moves the player during a quest |
| `scriptNothingStarts` | No dialogue starts the script, and nothing it is attached to runs it |
| `activatorNotUsed` | An activator's script moves the player without being used: a Recall blocker, a trap |
| `itemWithSeveralDestinations` | An item that sends you to one of several places, like the Mazed Band |
| `destinationNotInProfile` | The cell does not exist in this profile, like Todd's test cells |
| `dialogueWithNoPlace`, `activatorNotPlaced` | Nothing says where it could be used |

## Options and verification

```powershell
python build_teleport_catalog.py --profile tr
python build_app_bundle.py --no-teleports
python -m unittest test_teleport_catalog -v
```

The whole build takes about a second a profile. Tests cover the branch conditions of a
real Propylon script, every spelling of an item test, routine tests, the several
spellings of `PositionCell`, destinations missing from a profile, the dialogue
condition function table, item conditions in dialogue, every gate reason, profile-
scoped rules, a dialogue starting a script, every reason a teleport is left out, and a
rule matching nothing failing the build.

## What this layer does not do

It does not evaluate conditions, run scripts, or know whether a quest has been done.
It does not follow a script started by another script, only by dialogue. Mark and
Recall are the player's own and are not here.
