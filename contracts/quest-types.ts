/**
 * Contract for quests schema 1.0.0 — the journal, as something to track against.
 *
 * A record is one journal topic: what the game calls it, the stages its entries can
 * set, and which of those finish it. That is what journal completion per character
 * needs; a character's own progress is a stage number per key, stored in D1.
 *
 * Entry prose is not here. It is 691 KB gzipped for Tamriel Rebuilt against a 988 KB
 * bundle, and completion needs the numbers rather than the words. If a journal reader
 * is ever built, the text belongs in its own catalog, the way book prose does.
 */
import type { Profile } from "./catalog-types";

export type Quest = {
  /** The journal topic id, lowercase, as scripts and saves refer to it. */
  key: string;
  /** Null when the game never names the topic. Show `firstEntry` instead; do not
   *  invent a title, and do not fall back to the key. */
  name: string | null;
  /** How the name was obtained. Null when there is no name. */
  nameSource: "record" | "authored" | null;
  /** True when some stage finishes it. **False means this is not a quest** — a Blades
   *  contact note, a book-reading entry — so it should not appear in a completion list
   *  at all. That is why most untitled topics need no title. */
  trackable: boolean;
  /** Every stage number the topic's entries can set, ascending. */
  stages: number[];
  /** The subset of `stages` that complete it. More than one is normal: a quest can end
   *  several ways. Empty exactly when `trackable` is false. */
  finishesAt: number[];
  /** Stages that put the quest back in progress after it finished. */
  restartsAt: number[];
  /** First journal entry, to at most 120 characters. Present only when `name` is null,
   *  so a UI has real words from the game to show in place of a title. */
  firstEntry: string | null;
  /** How many journal entries the topic has, including its name entry. */
  entries: number;
};

export type QuestCatalog = {
  schemaVersion: "1.0.0";
  profile: Profile["id"];
  snapshotId: string;
  /** The authored titles file's own version, independent of the snapshot. */
  policyVersion: string;
  derivation: {
    method: string;
    topics: number;
    trackable: number;
    namedByRecord: number;
    namedByAuthor: number;
    unnamed: number;
    /** The ones that matter: completable but never named. 0 in vanilla, 12 in TR. */
    unnamedButTrackable: string[];
    stages: number;
  };
  coverage: string;
  records: Quest[];
};

/** What belongs in a completion list: quests, not journal notes. */
export function trackableQuests(catalog: QuestCatalog): Quest[] {
  return catalog.records.filter(quest => quest.trackable);
}

/**
 * Whether a character has finished a quest, given the stage their save reached.
 * Null when the quest was never started, so a caller can tell "not begun" from
 * "in progress" rather than showing both as 0%.
 */
export function questComplete(quest: Quest, stage: number | undefined): boolean | null {
  if (stage === undefined) return null;
  return quest.finishesAt.some(finish => stage >= finish);
}
