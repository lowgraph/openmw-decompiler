# Journal quests

Run in this project's VS Code terminal, after the journal catalog exists:

```powershell
python build_quest_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\quests\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Quests` catalog. See `quest-types.ts` for
the app contract, with reference `trackableQuests` and `questComplete`.

## What a record is

One journal topic: what the game calls it, the stages its entries can set, and which
of those finish it. A character's own progress is a stage number per key, which belongs
in D1, not here.

```json
{"key":"a1_10_mehramilo","name":"Meet Mehra Milo","nameSource":"record",
 "trackable":true,"stages":[10,20,30,40,50],"finishesAt":[50],"restartsAt":[],
 "firstEntry":null,"entries":6}
```

```
vanilla    754 topics    530 trackable    19 KB gzipped
tr        2573 topics   1905 trackable    63 KB gzipped
tr_arce   identical to tr, so the bundle inherits it
```

**Entry prose is deliberately absent.** It is 691 KB gzipped for TR against a 988 KB
bundle — more than half the bundle again, for text that completion tracking never
reads. Book prose was split the same way, into `BookText`. If a journal *reader* is
ever built, the text belongs in its own catalog on the same pattern.

Stage numbers are bare integers rather than an object each. TR has 16,743 of them, and
a `{index, finishes, restarts}` object per stage cost more than every other field in
the catalog combined: 1,030 KB raw against 517 KB.

## "326 topics have no title" was the wrong problem

That number was the sum across all three profiles. Per profile it is 82 in vanilla and
122 in TR — and almost none of them are quests.

The discriminator is completion. A journal entry can carry `quest_status` of `name`,
`finished` or `restart`; a topic that no entry ever finishes is a journal *note*, not a
quest, and never appears in a completion list at all:

| Profile | Journal topics | Named | Unnamed, not trackable | Unnamed **and** trackable |
| --- | --- | --- | --- | --- |
| vanilla | 758 | 676 | 79 | **3** |
| tr | 2,577 | 2,455 | 107 | **15** |

The 79 and 107 are Blades contact notes, book-reading entries, and `11111 test journal`
("This is a test... You should never see this."). They need no title because nothing
tracks them. `trackable: false` says so, and the site should filter on it.

That leaves **3 and 15** genuinely untitled quests. Three of them name themselves in
their first entry — `co_estate` opens with "East Empire Company: The Factor's Estate",
`va_vampchild` with "Blood Ties" — and those are authored in
`policy/journal-titles.json`, which clears vanilla entirely. The remaining 12 in TR
open with prose rather than a title.

## Never invent a title

An unnamed topic publishes `name: null` and `firstEntry`, the first journal entry cut
to 120 characters. A UI shows the player real words from the game instead of a made-up
quest name or a raw key like `tr_m7_ns_casino_prisoner`.

Authored titles are for names that can be *verified* against the game, not for filling
gaps. They never override a name the game supplies, and the build **fails** when an
authored key names nothing in any profile:

```
1 authored journal title(s) match no untitled quest in any profile: gone
  Either the quest now names itself, or the key is wrong.
```

That matters because a TR update that starts naming a quest would otherwise leave a
stale override silently shadowing it.

## Options and verification

```powershell
python build_quest_catalog.py --profile tr
python build_quest_catalog.py --titles policy/journal-titles.json
python build_app_bundle.py --no-quests
python -m unittest test_quest_catalog -v
```

Tests cover a topic naming itself, the name entry not counting as a stage, an unnamed
topic's excerpt, a named topic carrying none, authored titles filling and never
overriding, excerpt truncation and whitespace collapsing, trackable versus note,
several finishing stages, restarts, stage ordering and deduplication, dialogue topics
being excluded, excluded topics, a stale authored title failing, and the payload counts.

## What this layer does not do

It does not evaluate the conditions that gate an entry, so a stage listed here may be
unreachable for a given character. It does not order stages by narrative, only by
number. It holds no per-character progress: that is user data, and it belongs in D1
with the content `snapshotId` beside it.
