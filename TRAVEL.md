# Fast travel network

Run in this project's VS Code terminal, after the services catalog exists:

```powershell
python build_travel_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\travel\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Travel` catalog. See `travel-types.ts` for
the app contract and a reference `usableEdges`.

## What an edge is

One journey a transport provider will sell you: the cell you speak to them in, the
cell they put you down in. Routing is a search over `records`; `nodes` and `providers`
are lookup tables for labelling what the search returns.

```
vanilla   115 edges    35 cells    37 providers   (5 guild guides)
tr        427 edges   137 cells   174 providers  (23 guild guides, 12 Conjurer edges)
tr_arce   identical to tr, so the bundle inherits it
```

4.5 KB gzipped for vanilla, 15.4 KB for TR. Only 174 of TR's 2,742 service providers
sell travel at all; the rest are merchants, trainers and spellmakers.

**Teleport doors are deliberately absent.** Walking between interiors and exteriors is
a separate graph of 17,156 links — forty times the size, with coordinates on every row
— and it answers a different question. It can be its own catalog if character-aware
routing ever needs it.

## The two toggles

| Toggle | Default | Profiles | Removes |
| --- | --- | --- | --- |
| `mageGuildMember` | **on** | all | every edge with `requiresMageGuild` |
| `conjurerRank` | **off** | `tr`, `tr_arce` | every edge with `requiresConjurer` |

Measured on the real network:

```
tr    mageGuild on,  conjurer on    427 edges
      mageGuild on,  conjurer off   415
      mageGuild off, conjurer off   367
```

`conjurerRank` is subordinate to `mageGuildMember`, and falls out of the data rather
than being special-cased: every rank-gated edge is a guild guide edge, so turning
membership off has already removed them.

The Conjurer toggle removes **edges, not providers**. Each of the four cities also has
a short-range guide who is not gated — Soril still runs Firewatch to Helnim and
Nivalis with the toggle off.

## Spotting a guild guide, and why not by class

A guild guide is **a travel provider whose every destination is a Mages Guild cell**.

The obvious rule — the NPC class `Guild Guide` — is wrong, and wrong in a way that
would have looked like a working feature. Firewatch's Conjurer-rank guide is
**Thazlorakis, a bound Daedroth**: a `CREA` record, and creatures carry no class. The
class rule finds 22 guides in TR and misses her, taking all three Firewatch long-
distance routes with her. Fittingly, the Conjurer's guide is herself a conjuration.

The destination rule finds 23. It is safe only because no provider is *partly* a guild
guide, so the builder checks that premise instead of assuming it:

```
The guild guide rule assumes a provider never mixes Mages Guild destinations with
other ones, and these do: ...
```

Both rules still run. Every disagreement is published in
`verification.classDisagreement` and printed, so the one known exception stays visible
rather than becoming folklore:

```
tr: 427 edges, 137 cells, 174 providers (23 guild guides, 12 Conjurer edges), 140 KB
  by destination True but class 'daedroth': Thazlorakis (CREA)
```

## What is authored

`profile_destinations` is `(profile, provider, entry, cell, status)` and nothing more.
**There is no faction or rank column**, because rank gating lives in dialogue
conditions rather than in the travel records. So the Conjurer requirement is authored
in `policy/travel.json`, marked `source: "authored"`, and versioned independently of
any extraction snapshot — the same discipline as `policy/early-game.json`.

The rank itself is now grounded: the `Factions` catalog carries the Mages Guild's
ranks, and Conjurer is rank 4 — reputation 30 in vanilla, 70 in Tamriel Rebuilt. See
[FACTIONS.md](FACTIONS.md). What stays authored is the claim that *these twelve
journeys* are the ones it gates, which no record states.

The twelve gated journeys, all confirmed present in the extracted data:

| City | Guide | Reaches |
| --- | --- | --- |
| Vivec | Ohmonir | Firewatch, Narsis, Old Ebonheart |
| Old Ebonheart | Barabus Inclodios | Firewatch, Narsis, Vivec |
| Narsis | Lissinia Bax | Firewatch, Old Ebonheart, Vivec |
| Firewatch | Thazlorakis | Narsis, Old Ebonheart, Vivec |

The data's job is to confirm those edges exist, not to invent the rule. The builder
**fails** when an authored edge matches nothing, because a renamed cell would
otherwise empty the toggle in silence:

```
1 Conjurer edge(s) in policy/travel.json match nothing in the tr data: vivec -> narsis
```

Travel mode is authored the same way, as a class-to-mode table. An unlisted class
publishes `mode: null` rather than a guess — 23 TR providers are one-off transports
owned by no network, and saying so beats inventing a category for them.

## Options and verification

```powershell
python build_travel_catalog.py --profile tr
python build_travel_catalog.py --policy policy/travel.json
python build_app_bundle.py --no-travel
python -m unittest test_travel_catalog -v
```

Tests cover the destination rule against a caravaner, a classless creature, and a
provider that mixes both kinds of stop; edges per origin and destination; a provider
standing where they would send you; an unplaced provider; an excluded developer cell;
key uniqueness; an unknown class publishing null; an authored edge being marked, its
reverse not being, and a missing one failing the build; vanilla gating nothing; named
and unnamed endpoint cells; and the toggles' defaults surviving into the payload.

## What this layer does not do

No prices, no schedules, and no route-finding — it publishes the graph, not the path
through it. It evaluates no dialogue and no scripts, so a provider who would refuse to
talk to you still appears. `excludedCells` drops developer cells; `interior:toddtest`
is real, and Todd's Super Tester Guy really does sell travel to it.
