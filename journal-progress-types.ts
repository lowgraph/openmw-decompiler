/**
 * Contract for journal progress — a character's stage in each quest.
 *
 * This is user data, so it lives in D1 rather than the bundle, and Codex owns the
 * migration. See JOURNAL_PROGRESS.md for the field requirements and the measurements
 * behind them; this file is the wire shape the two sides agree on.
 *
 * Progress joins the `Quests` catalog on `questKey`. Saves spell ids in mixed case
 * (`A1_1_FindSpymaster`) and the catalog lowercases them, so **normalize on ingest**:
 * 469 of 757 rows in the real corpus join only after lowercasing.
 */
import type { Profile } from "./catalog-types";
import type { Quest, QuestCatalog } from "./quest-types";

export type QuestStatus = "active" | "finished";

export type JournalProgressRow = {
  characterId: string;
  /** Lowercase. Joins `Quest.key`. */
  questKey: string;
  /** Which world's quest keys these are; TR and vanilla share keys with different
   *  stage sets, so a row without this can be read against the wrong quest. */
  world: "vanilla" | "tr";
  /** The journal index reached. Real saves top out at 100. */
  stage: number;
  /** What the save said, not what we recomputed. */
  finished: boolean;
  status: QuestStatus;
  /** The content snapshot these keys came from. */
  snapshotId: string;
  updatedAt: string;
};

/** One quest as the journal screen shows it: the catalog's facts plus this character's. */
export type JournalEntry = {
  quest: Quest;
  progress: JournalProgressRow | null;
  /** Null when the character has not started it — distinct from started-and-unfinished. */
  complete: boolean | null;
};

/** Normalize a quest id from a save before it is stored or joined. */
export function questKeyOf(saveQuestId: string): string {
  return saveQuestId.toLowerCase();
}

/**
 * Completion for a character, over quests that can actually be completed.
 *
 * The denominator is `trackable` quests only — 530 of 754 in vanilla, 1,905 of 2,573
 * in TR. Journal notes can never be completed, so counting them caps the figure below
 * 100%: a character who finished every quest would read as 70.3% in vanilla, 74.0% in
 * TR, and be stuck there.
 */
export function completion(
  catalog: QuestCatalog,
  rows: readonly JournalProgressRow[],
): { finished: number; total: number; fraction: number } {
  const byKey = new Map(rows.map(row => [row.questKey, row]));
  const trackable = catalog.records.filter(quest => quest.trackable);
  const finished = trackable.filter(quest => byKey.get(quest.key)?.finished).length;
  return {
    finished,
    total: trackable.length,
    fraction: trackable.length ? finished / trackable.length : 0,
  };
}

/** The journal screen's rows, quests the character has touched first. */
export function journalFor(
  catalog: QuestCatalog,
  rows: readonly JournalProgressRow[],
): JournalEntry[] {
  const byKey = new Map(rows.map(row => [row.questKey, row]));
  return catalog.records
    .filter(quest => quest.trackable)
    .map(quest => {
      const progress = byKey.get(quest.key) ?? null;
      return {
        quest,
        progress,
        complete: progress ? progress.finished : null,
      };
    });
}

/** Guard: a profile's catalog and a row's world must describe the same content. */
export function worldOf(profile: Profile["id"]): "vanilla" | "tr" {
  return profile === "vanilla" ? "vanilla" : "tr";
}
