import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_quest_catalog import (FALLBACK_LENGTH, assemble, check_authored, excerpt,
                                 load_titles, quests)
from export_items import ExportError


def titles(**overrides):
    base = {'schemaVersion': '1.0.0', 'policyVersion': 'test',
            'titles': {}, 'excludedTopics': []}
    return base | overrides


class JournalFixture(unittest.TestCase):
    """A journal database is four joined tables, so the fixture is four tables."""
    def journal(self, topics):
        """topics: {key: [(stage, quest_status, text), ...]}, or {key: (kind, entries)}."""
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE topics(version_id,topic_key,editor_id,type_raw,type_name,plugin);
          CREATE TABLE profile_topics(profile_id,topic_key,version_id,origin_plugin);
          CREATE TABLE responses(version_id,topic_key,info_key,editor_id,previous_info_key,
            next_info_key,type_raw,value_raw,npc_rank_raw,gender_raw,pc_rank_raw,actor_key,
            race_key,class_key,faction_key,factionless,pc_faction_key,cell_filter,sound,
            response_text,result_script,quest_status,plugin);
          CREATE TABLE profile_responses(profile_id,topic_key,info_key,version_id,origin_plugin);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        for index, (topic, rows) in enumerate(topics.items(), 1):
            kind = 'journal'
            if rows and isinstance(rows, tuple):
                kind, rows = rows
            db.execute('INSERT INTO topics VALUES(?,?,?,?,?,?)',
                       (index, topic, topic, 0, kind, 'p'))
            db.execute('INSERT INTO profile_topics VALUES(?,?,?,?)', ('tr', topic, index, 'p'))
            for entry, (stage, status, text) in enumerate(rows):
                info = f'{topic}-{entry}'
                db.execute('INSERT INTO responses VALUES('
                           '?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (index, topic, info, info, None, None, 0, stage, 0, 0, 0, None,
                            None, None, None, 0, None, None, None, text, None, status, 'p'))
                db.execute('INSERT INTO profile_responses VALUES(?,?,?,?,?)',
                           ('tr', topic, info, index, 'p'))
        db.commit()
        return db

    def one(self, rows, rules=None, key='q'):
        collected, _ = quests(self.journal({key: rows}), 'tr', rules or titles())
        return collected[key]


class NamingTests(JournalFixture):
    def test_a_topic_that_names_itself_uses_that_name(self):
        record = self.one([(0, 'name', 'Meet Mehra Milo'), (10, 'none', 'She asked me to come.')])
        self.assertEqual(record['name'], 'Meet Mehra Milo')
        self.assertEqual(record['nameSource'], 'record')

    def test_the_name_entry_is_not_a_stage(self):
        # quest_status 'name' carries the title, not a step the player reaches.
        record = self.one([(0, 'name', 'Title'), (10, 'none', 'First.')])
        self.assertEqual(record['stages'], [10])

    def test_an_unnamed_topic_publishes_no_name_and_an_excerpt(self):
        record = self.one([(10, 'none', 'Caius says Elone the Scout can be found in Balmora.')])
        self.assertIsNone(record['name'])
        self.assertIsNone(record['nameSource'])
        self.assertEqual(record['firstEntry'],
                         'Caius says Elone the Scout can be found in Balmora.')

    def test_a_named_topic_carries_no_excerpt_because_it_needs_none(self):
        record = self.one([(0, 'name', 'Title'), (10, 'none', 'Body text.')])
        self.assertIsNone(record['firstEntry'])

    def test_an_authored_title_fills_an_unnamed_topic(self):
        rules = titles(titles={'co_estate': "East Empire Company: The Factor's Estate"})
        record = self.one([(0, 'none', 'Whatever.'), (10, 'finished', 'Done.')],
                          rules, key='co_estate')
        self.assertEqual(record['name'], "East Empire Company: The Factor's Estate")
        self.assertEqual(record['nameSource'], 'authored')

    def test_an_authored_title_never_overrides_the_game(self):
        rules = titles(titles={'q': 'My Better Name'})
        record = self.one([(0, 'name', 'The Real Name'), (10, 'none', 'Body.')], rules)
        self.assertEqual(record['name'], 'The Real Name')
        self.assertEqual(record['nameSource'], 'record')

    def test_an_excerpt_is_cut_rather_than_shipped_whole(self):
        record = self.one([(10, 'none', 'word ' * 200)])
        self.assertLessEqual(len(record['firstEntry']), FALLBACK_LENGTH + 1)
        self.assertTrue(record['firstEntry'].endswith('…'))

    def test_an_excerpt_collapses_the_whitespace_the_journal_uses(self):
        self.assertEqual(excerpt('one\n\ttwo   three'), 'one two three')

    def test_an_empty_entry_gives_no_excerpt_rather_than_an_empty_string(self):
        self.assertIsNone(excerpt('   '))


class TrackingTests(JournalFixture):
    def test_a_topic_that_can_finish_is_trackable(self):
        record = self.one([(10, 'none', 'Started.'), (100, 'finished', 'Done.')])
        self.assertTrue(record['trackable'])
        self.assertEqual(record['finishesAt'], [100])

    def test_a_topic_that_never_finishes_is_a_note_not_a_quest(self):
        # The Blades contact entries and book notes: real journal text, no completion.
        record = self.one([(0, 'none', 'Elone gave me a guide to Vvardenfell.')])
        self.assertFalse(record['trackable'])
        self.assertEqual(record['finishesAt'], [])

    def test_a_quest_can_end_several_ways(self):
        record = self.one([(10, 'none', 'Start.'), (50, 'finished', 'One ending.'),
                           (60, 'finished', 'Another.')])
        self.assertEqual(record['finishesAt'], [50, 60])

    def test_a_restart_stage_is_recorded_separately(self):
        record = self.one([(10, 'none', 'Start.'), (50, 'finished', 'Done.'),
                           (60, 'restart', 'Not so fast.')])
        self.assertEqual(record['restartsAt'], [60])
        self.assertEqual(record['finishesAt'], [50])

    def test_stages_are_ascending_and_deduplicated(self):
        record = self.one([(30, 'none', 'c'), (10, 'none', 'a'), (30, 'none', 'c again'),
                           (20, 'none', 'b')])
        self.assertEqual(record['stages'], [10, 20, 30])

    def test_entries_counts_every_response_including_the_name(self):
        record = self.one([(0, 'name', 'Title'), (10, 'none', 'a'), (20, 'none', 'b')])
        self.assertEqual(record['entries'], 3)


class SelectionTests(JournalFixture):
    def test_only_journal_topics_are_published(self):
        # The same table holds dialogue topics, greetings and voice lines.
        db = self.journal({'quest': [(10, 'finished', 'Done.')],
                           'chatter': ('topic', [(0, 'none', 'Hello.')])})
        collected, _ = quests(db, 'tr', titles())
        self.assertEqual(sorted(collected), ['quest'])

    def test_an_excluded_topic_is_dropped(self):
        rules = titles(excludedTopics=['11111 test journal'])
        db = self.journal({'11111 test journal': [(0, 'none', 'You should never see this.')],
                           'real': [(10, 'finished', 'Done.')]})
        collected, _ = quests(db, 'tr', rules)
        self.assertEqual(sorted(collected), ['real'])


class AuthoredTitleTests(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp())/'journal-titles.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_an_unreadable_schema_is_refused(self):
        with self.assertRaises(ExportError):
            load_titles(self.write(titles(schemaVersion='9.9.9')))

    def test_an_empty_title_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            load_titles(self.write(titles(titles={'q': '   '})))
        self.assertIn('q', str(caught.exception))

    def test_a_title_that_names_nothing_fails_the_build(self):
        # Otherwise a quest that starts naming itself leaves a stale override behind.
        rules = titles(titles={'gone': 'A Quest That Moved On'})
        with self.assertRaises(ExportError) as caught:
            check_authored(rules, {'tr': set()})
        self.assertIn('gone', str(caught.exception))

    def test_a_title_used_by_any_profile_is_enough(self):
        rules = titles(titles={'co_estate': 'Something'})
        check_authored(rules, {'vanilla': {'co_estate'}, 'tr': set()})

    def test_the_shipped_titles_file_loads(self):
        loaded = load_titles(Path(__file__).parent/'policy/journal-titles.json')
        self.assertIn('co_estate', loaded['titles'])
        self.assertIn('11111 test journal', loaded['excludedTopics'])


class PayloadTests(JournalFixture):
    def test_the_payload_counts_what_a_reviewer_needs(self):
        db = self.journal({'named': [(0, 'name', 'A Quest'), (10, 'finished', 'Done.')],
                           'note': [(0, 'none', 'Just a note.')],
                           'orphan': [(10, 'finished', 'Done, unnamed.')]})
        payload = assemble(db, 'tr', titles(), 'snap')
        counts = payload['derivation']
        self.assertEqual(counts['topics'], 3)
        self.assertEqual(counts['trackable'], 2)
        self.assertEqual(counts['namedByRecord'], 1)
        self.assertEqual(counts['unnamed'], 2)
        self.assertEqual(counts['unnamedButTrackable'], ['orphan'],
                         'the note needs no title; the orphan does')

    def test_every_record_has_the_key_the_bundle_joins_on(self):
        payload = assemble(self.journal({'q': [(10, 'finished', 'Done.')]}), 'tr',
                           titles(), 'snap')
        self.assertTrue(all(isinstance(r.get('key'), str) and r['key']
                            for r in payload['records']))
        self.assertEqual(payload['snapshotId'], 'snap')


if __name__ == '__main__':
    unittest.main()
