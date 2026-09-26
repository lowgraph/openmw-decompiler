# Journal progress: field requirements for D1

**Codex owns the migration.** This is the data side's half of the contract, as
COORDINATION.md sets out: the field requirements and the evidence behind them. The DDL
below is a proposal in your house style, not a decision.

It exists because `cloud_saves` keeps quest progress inside the packed SLT1 blob, with
only `quest_count` and `topic_count` exposed. That is fine for restoring a save and
wrong for feature 9, which is journal completion **per character** — a question you
cannot ask of a blob.

## What it keys against

The `Quests` catalog, shipped in the bundle since `3b2f5dbb7e253d0b0bb14a73`. See
[QUESTS.md](QUESTS.md) and `quest-types.ts`. A row here is a character's stage in one
quest; the catalog says what that quest is, what stages exist, and which finish it.

## The measurements

Taken from the 96 real saves in the user's corpus, parsed with
`morrowind-tools/lib/omwsave-parser.mjs`:

```
757 quest rows across 96 saves
  match a catalog key exactly        288
  match only after lowercasing       469
  match neither                        0
quest rows per save   min 1, median 4, max 19
highest stage seen    100
status values         active (564), finished (193)
```

Three things follow.

**Every quest id in every real save resolves to the catalog.** Coverage is not a
worry; there is no unmatched-key case to design around.

**Case folding is mandatory, not a nicety.** Saves store `A1_1_FindSpymaster`; the
catalog stores `a1_10_mehramilo`. 62% of real rows join *only* after lowercasing. An
exact-match join would lose most of the data and look like it worked.

**Rows are small in practice.** A completionist TR character is the 2,577-row ceiling;
a real one has four. Sizing is not the argument for rows — queryability is. For the
record, the blob equivalent measures 61 KB for a TR journal at 100%, comfortably inside
D1's 2 MB row limit, so either shape *fits*. Only one answers the question.

## Required fields

| Field | Type | Requirement |
| --- | --- | --- |
| `clerk_user_id` | TEXT | Owner, as every other table. Non-empty. |
| `character_id` | TEXT | Which character. References whatever `saved_characters`/`cloud_saves` row owns this progress; your call which. |
| `quest_key` | TEXT | **Lowercased on ingest.** Joins `Quests.key`. |
| `stage` | INTEGER | The journal index reached. `>= 0`; real saves top out at 100. |
| `finished` | INTEGER | 0/1. Derivable from `stage` against the catalog's `finishesAt`, but the save states it directly, so store what the save said rather than recomputing. |
| `status` | TEXT | `active` or `finished`. Those are the only two values the parser emits. |
| `world` | TEXT | `vanilla` or `tr`. TR and vanilla share quest keys with different stage sets; without this a TR stage can be read against a vanilla quest. |
| `snapshot_id` | TEXT | The content snapshot the keys came from. Per HANDOFF.md's convention, every row storing a game reference carries it, so a catalog rebuild can tell a stale key from a missing one. |
| `updated_at` | TEXT | As elsewhere. |

Uniqueness is `(clerk_user_id, character_id, quest_key)` — one stage per quest per
character.

## Queries it has to answer

These are what the shape is *for*; a blob answers none of them.

1. This character's full journal, joined to titles — the journal screen.
2. How far through a quest this character is — `stage` against `finishesAt`.
3. Which of my characters finished a given quest — the cross-character view.
4. Completion percentage — finished rows over `trackableQuests(catalog).length`.

Note (4): the denominator is **trackable quests only**, 530 in vanilla and 1,905 in TR,
not all 754 and 2,573 topics. Journal notes can never be completed, so counting them
puts a ceiling below 100%: a character who finished *every quest in the game* would read
as **70.3% in vanilla and 74.0% in TR**, and nothing they did could move it further.
`trackable: false` marks them.

## A proposal, in your style

```sql
CREATE TABLE IF NOT EXISTS journal_progress (
  clerk_user_id TEXT NOT NULL CHECK (length(clerk_user_id) > 0),
  character_id  TEXT NOT NULL CHECK (length(character_id) > 0),
  quest_key     TEXT NOT NULL CHECK (quest_key = lower(quest_key) AND length(quest_key) > 0),
  world         TEXT NOT NULL DEFAULT 'vanilla' CHECK (world IN ('vanilla', 'tr')),
  stage         INTEGER NOT NULL CHECK (stage >= 0),
  finished      INTEGER NOT NULL DEFAULT 0 CHECK (finished IN (0, 1)),
  status        TEXT NOT NULL CHECK (status IN ('active', 'finished')),
  snapshot_id   TEXT NOT NULL CHECK (length(snapshot_id) = 64),
  updated_at    TEXT NOT NULL,
  PRIMARY KEY (clerk_user_id, character_id, quest_key)
);

-- One character's journal, the common read.
CREATE INDEX IF NOT EXISTS idx_journal_progress_character
  ON journal_progress (clerk_user_id, character_id, quest_key);

-- "Which of my characters finished this quest", the one a blob cannot answer.
CREATE INDEX IF NOT EXISTS idx_journal_progress_quest
  ON journal_progress (clerk_user_id, quest_key, finished);
```

The `quest_key = lower(quest_key)` CHECK is deliberate: it turns the case mistake into
a write-time failure instead of a silent empty join months later.

This DDL was executed and exercised against SQLite rather than written from memory.
Every constraint refuses what it should — a mixed-case key, an unknown world, a status
outside the two the parser emits, a short snapshot id, a negative stage, a duplicate
`(owner, character, quest)` — and the cross-character query returns both characters who
finished a quest. D1 is SQLite, but the migration is still yours to run.

## Writing it

D1 allows **100 bound parameters per query**, so a 9-column row is 11 rows per
statement. Import a save's journal as a batch of multi-row `INSERT ... ON CONFLICT DO
UPDATE`, or pass one JSON array and expand it with `json_each`, which sidesteps the cap
entirely. At a median of 4 rows per save this rarely matters; at the 2,577-row ceiling
it does.

Do not inline the values into SQL text — the statement limit is 100 KB.

## What this does not cover

Dialogue topics. A save also carries the topics a character has heard —
`otherJournalIds`, up to 66 in the corpus — and they are not quests, have no stages,
and need their own table if feature 9 ever shows them. The `Quests` catalog excludes
them by construction: it publishes `type_name = 'journal'` topics only.
