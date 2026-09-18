import json
from pathlib import Path
import tempfile
import unittest

from import_effect_flags import SUPPORTED_DUMP, build, find_log, parse, validate
from export_items import ExportError

BASE = {'harmful': False, 'continuousVfx': False, 'hasDuration': True, 'hasMagnitude': True,
        'isAppliedOnce': False, 'casterLinked': False, 'nonRecastable': False,
        'hasAttribute': False, 'hasSkill': False, 'onSelf': True, 'onTouch': True,
        'onTarget': True, 'unreflectable': False, 'allowsSpellmaking': True,
        'allowsEnchanting': True, 'negativeLight': False}


def line(text):
    """Log lines carry a timestamp and level before the marker."""
    return f'2026-09-18 17:00:00 [Lua] {text}'


def record(index, name, **extra):
    body = {'index': index, 'id': (name or 'x').lower().replace(' ', ''), 'name': name,
            'school': 'destruction', 'baseCost': 1.0} | BASE | extra
    return line('SILTDUMP ' + json.dumps(body, separators=(',', ':')))


def block(records, version=SUPPORTED_DUMP, context='menu', declared=None, ended=None,
          unmapped=None):
    header = f'SILTDUMP BEGIN {version} {context} {declared if declared is not None else len(records)}'
    if unmapped is not None:
        header += f' unmapped={unmapped}'
    return ([line(header)] + records
            + [line(f'SILTDUMP END {ended if ended is not None else len(records)}')])


def log(*lines):
    path = Path(tempfile.mkdtemp())/'openmw.log'
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return path


class ParseTests(unittest.TestCase):
    def test_a_complete_block_is_read_through_the_log_prefix(self):
        blocks, errors = parse(log(*block([record(0, 'Water Breathing')])).read_text())
        self.assertEqual(errors, [])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['effects'][0]['name'], 'Water Breathing')
        self.assertEqual(blocks[0]['context'], 'menu')

    def test_unrelated_log_noise_is_ignored(self):
        lines = ['2026-09-18 [Info] loading content', *block([record(0, 'One')]),
                 '2026-09-18 [Warn] something else entirely']
        blocks, _ = parse(log(*lines).read_text())
        self.assertEqual(len(blocks), 1)

    def test_the_last_complete_block_wins(self):
        lines = block([record(0, 'Old')]) + block([record(0, 'New'), record(1, 'Second')])
        path = log(*lines)
        _, payload = build(path, Path(tempfile.mkdtemp()))
        self.assertEqual([r['name'] for r in payload['records']], ['New', 'Second'])
        self.assertEqual(payload['source']['blocksFound'], 2)

    def test_a_reported_error_is_surfaced_when_no_block_arrived(self):
        path = log(line('SILTDUMP ERROR menu attempt to index a nil value'))
        with self.assertRaises(ExportError) as caught:
            build(path, Path(tempfile.mkdtemp()))
        self.assertIn('attempt to index a nil value', str(caught.exception))

    def test_an_empty_log_says_what_to_do(self):
        with self.assertRaises(ExportError) as caught:
            build(log('nothing here'), Path(tempfile.mkdtemp()))
        self.assertIn('Enable silt_effect_dump', str(caught.exception))


class ValidationTests(unittest.TestCase):
    def test_version_one_is_refused_because_its_keys_were_positions(self):
        blocks, _ = parse(log(*block([record(1, 'Water Breathing')], version=1)).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('off by one', str(caught.exception))

    def test_a_truncated_block_is_refused_rather_than_half_read(self):
        blocks, _ = parse(log(*block([record(0, 'One')], declared=5)).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('Truncated dump', str(caught.exception))

    def test_a_repeated_index_is_refused(self):
        blocks, _ = parse(log(*block([record(0, 'One'), record(0, 'Again')])).read_text())
        with self.assertRaises(ExportError):
            validate(blocks[0])

    def test_missing_flags_name_the_cause(self):
        stripped = record(0, 'One')
        body = json.loads(stripped[stripped.index('{'):])
        del body['harmful']
        blocks, _ = parse(log(*block([line('SILTDUMP '+json.dumps(body))])).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('harmful', str(caught.exception))

    def test_lua_added_effects_are_recorded_but_not_joined(self):
        # Tamriel Rebuilt registers summons through Lua, so they have no engine id.
        lines = block([record(0, 'Water Breathing'), record(None, 'Summon Devourer')],
                      unmapped=1)
        _, payload = build(log(*lines), Path(tempfile.mkdtemp()))
        self.assertEqual(payload['effects'], 1)
        self.assertEqual(payload['luaAdded'], ['Summon Devourer'])
        self.assertEqual([r['name'] for r in payload['records']], ['Water Breathing'])

    def test_records_are_published_in_index_order(self):
        lines = block([record(7, 'Seven'), record(1, 'One'), record(3, 'Three')])
        _, payload = build(log(*lines), Path(tempfile.mkdtemp()))
        self.assertEqual([r['index'] for r in payload['records']], [1, 3, 7])


class LogDiscoveryTests(unittest.TestCase):
    def test_an_explicit_missing_path_is_an_error(self):
        with self.assertRaises(ExportError):
            find_log(Path(tempfile.mkdtemp())/'absent.log')

    def test_an_explicit_present_path_is_used(self):
        path = log(*block([record(0, 'One')]))
        self.assertEqual(find_log(path), path)


if __name__ == '__main__':
    unittest.main()
