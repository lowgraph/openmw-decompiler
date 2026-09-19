import json
from pathlib import Path
import tempfile
import unittest

from import_effect_flags import SUPPORTED_DUMPS, build, find_log, parse, validate
from export_items import ExportError

BASE = {'harmful': False, 'continuousVfx': False, 'hasDuration': True, 'hasMagnitude': True,
        'isAppliedOnce': False, 'casterLinked': False, 'nonRecastable': False,
        'hasAttribute': False, 'hasSkill': False, 'onSelf': True, 'onTouch': True,
        'onTarget': True, 'unreflectable': False, 'allowsSpellmaking': True,
        'allowsEnchanting': True, 'negativeLight': False}


def line(text):
    """Log lines carry a timestamp and level before the marker."""
    return f'2026-09-18 17:00:00 [Lua] {text}'


def record(ident, name, **extra):
    body = {'id': ident, 'name': name, 'school': 'destruction', 'baseCost': 1.0} | BASE | extra
    return line('SILTDUMP ' + json.dumps(body, separators=(',', ':')))


def block(records, version=SUPPORTED_DUMPS[-1], context='menu', declared=None, ended=None):
    header = f'SILTDUMP BEGIN {version} {context} {declared if declared is not None else len(records)}'
    return ([line(header)] + records
            + [line(f'SILTDUMP END {ended if ended is not None else len(records)}')])


def log(*lines):
    path = Path(tempfile.mkdtemp())/'openmw.log'
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return path


class ParseTests(unittest.TestCase):
    def test_a_complete_block_is_read_through_the_log_prefix(self):
        blocks, errors = parse(log(*block([record('waterbreathing', 'Water Breathing')])).read_text())
        self.assertEqual(errors, [])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['effects'][0]['name'], 'Water Breathing')
        self.assertEqual(blocks[0]['context'], 'menu')

    def test_unrelated_log_noise_is_ignored(self):
        lines = ['2026-09-18 [Info] loading content', *block([record('one', 'One')]),
                 '2026-09-18 [Warn] something else entirely']
        blocks, _ = parse(log(*lines).read_text())
        self.assertEqual(len(blocks), 1)

    def test_the_last_complete_block_wins(self):
        lines = block([record('a', 'Old')]) + block([record('a', 'New'), record('b', 'Second')])
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
    def test_an_earlier_dump_is_still_usable_because_id_never_changed(self):
        blocks, _ = parse(log(*block([record('waterbreathing', 'Water Breathing')],
                                     version=1)).read_text())
        effects, _ = validate(blocks[0])
        self.assertEqual(list(effects), ['waterbreathing'])

    def test_an_unknown_dump_version_is_refused(self):
        blocks, _ = parse(log(*block([record('one', 'One')], version=99)).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('Unsupported dump version 99', str(caught.exception))

    def test_a_truncated_block_is_refused_rather_than_half_read(self):
        blocks, _ = parse(log(*block([record('one', 'One')], declared=5)).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('Truncated dump', str(caught.exception))

    def test_a_repeated_id_is_refused(self):
        blocks, _ = parse(log(*block([record('one', 'One'), record('one', 'Again')])).read_text())
        with self.assertRaises(ExportError):
            validate(blocks[0])

    def test_a_repeated_name_is_reported_as_unjoinable(self):
        # Tamriel Rebuilt ships two Wabbajack effects with distinct ids.
        lines = block([record('t_wabbajack', 'Wabbajack'), record('t_wabbajack_helper', 'Wabbajack'),
                       record('one', 'One')])
        _, payload = build(log(*lines), Path(tempfile.mkdtemp()))
        self.assertEqual(payload['ambiguousNames'], ['Wabbajack'])
        self.assertEqual(payload['effects'], 3, 'all three are still published')

    def test_missing_flags_name_the_cause(self):
        stripped = record('one', 'One')
        body = json.loads(stripped[stripped.index('{'):])
        del body['harmful']
        blocks, _ = parse(log(*block([line('SILTDUMP '+json.dumps(body))])).read_text())
        with self.assertRaises(ExportError) as caught:
            validate(blocks[0])
        self.assertIn('harmful', str(caught.exception))

    def test_effects_a_lua_mod_added_are_published_like_any_other(self):
        # Tamriel Rebuilt registers summons through Lua; they are real effects with ids,
        # they simply have no counterpart in any plugin file.
        lines = block([record('waterbreathing', 'Water Breathing'),
                       record('t_summon_devourer', 'Summon Devourer')])
        _, payload = build(log(*lines), Path(tempfile.mkdtemp()))
        self.assertEqual(payload['effects'], 2)
        self.assertIn('Summon Devourer', [r['name'] for r in payload['records']])

    def test_records_are_published_in_id_order(self):
        lines = block([record('c', 'Three'), record('a', 'One'), record('b', 'Two')])
        _, payload = build(log(*lines), Path(tempfile.mkdtemp()))
        self.assertEqual([r['id'] for r in payload['records']], ['a', 'b', 'c'])


class ProfileTests(unittest.TestCase):
    def test_a_profile_gets_its_own_file_because_the_list_depends_on_load_order(self):
        output = Path(tempfile.mkdtemp())
        destination, payload = build(log(*block([record('one', 'One')])), output, 'tr')
        self.assertEqual(destination, output/'tr.json')
        self.assertEqual(payload['profile'], 'tr')

    def test_profiles_do_not_overwrite_one_another(self):
        output = Path(tempfile.mkdtemp())
        build(log(*block([record('one', 'One')])), output, 'vanilla')
        build(log(*block([record('one', 'One'), record('two', 'Two')])), output, 'tr')
        counts = {p.stem: json.loads(p.read_text(encoding='utf-8'))['effects']
                  for p in sorted(output.glob('*.json'))}
        self.assertEqual(counts, {'vanilla': 1, 'tr': 2})

    def test_without_a_profile_the_shared_name_is_kept(self):
        output = Path(tempfile.mkdtemp())
        destination, payload = build(log(*block([record('one', 'One')])), output)
        self.assertEqual(destination, output/'effect-flags.json')
        self.assertIsNone(payload['profile'])


class LogDiscoveryTests(unittest.TestCase):
    def test_an_explicit_missing_path_is_an_error(self):
        with self.assertRaises(ExportError):
            find_log(Path(tempfile.mkdtemp())/'absent.log')

    def test_an_explicit_present_path_is_used(self):
        path = log(*block([record('one', 'One')]))
        self.assertEqual(find_log(path), path)


if __name__ == '__main__':
    unittest.main()
