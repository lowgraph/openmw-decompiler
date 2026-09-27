import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_teleport_catalog import (FUNCTIONS, activated, assemble, branches, build, describe_conditions,
                                    dialogue_items, gate_reason, gates, item_tests, load_policy,
                                    parse_destination, resolve_cell)
from export_items import ExportError

WARP = '''begin Warp_Andra
if ( menumode == 1 )
	return
endif
if ( OnActivate == 1 )
	if (  Player->GetItemCount, "Index_Master" > 0 )
		Player->PositionCell, 763, 702, 412, 60, "Caldera, Guild of Mages"
	elseif (  Player->GetItemCount, "Index_Andra" > 0 )
		Player->PositionCell, 540, 630, -368, 270, "Andasreth, Propylon Chamber" ; the chamber
	else
		MessageBox "You do not have the Index for this Propylon."
	endif
endif
end'''


def line_of(text, needle):
    return next(i for i, line in enumerate(text.splitlines()) if needle in line)


class ScriptTests(unittest.TestCase):
    def test_branches_know_what_each_line_runs_under(self):
        conditions = branches(WARP)
        positive, negative = conditions[line_of(WARP, 'Andasreth, Propylon')]
        self.assertEqual(len(positive), 2, 'OnActivate, then the Andra index')
        self.assertIn('Index_Master', negative[0], 'the Master branch was passed over first')

    def test_a_propylon_needs_its_index_unless_the_master_index_diverts(self):
        conditions = branches(WARP)
        self.assertEqual(gates(*conditions[line_of(WARP, 'Andasreth, Propylon')]), (['index_andra'], ['index_master'], []))
        self.assertEqual(gates(*conditions[line_of(WARP, 'Caldera')]), (['index_master'], [], []))

    def test_item_tests_read_every_spelling_of_carrying(self):
        self.assertEqual(item_tests('player->GetItemCount "Index Of Old" >= 1'), [('index of old', True)])
        self.assertEqual(item_tests('GetItemCount key_x == 0'), [('key_x', False)])
        self.assertEqual(item_tests('GetItemCount, "a" != 0'), [('a', True)])
        self.assertEqual(item_tests('GetItemCount "a" > 5'), [('a', True)], 'more than five still means carrying one')
        self.assertEqual(item_tests('GetItemCount "a" == 3'), [], 'an exact count says nothing either way')

    def test_routine_tests_are_not_conditions_but_quest_state_is(self):
        self.assertEqual(gates(['( OnActivate == 1 )', '( MenuMode )', '( button == 0 )'], []), ([], [], []))
        self.assertEqual(gates(['( state == 10 )'], [])[2], ['( state == 10 )'])

    def test_activation_is_what_makes_an_activator_travel(self):
        self.assertTrue(activated(['( OnActivate == 1 )']))
        self.assertFalse(activated(['( CellChanged == 1 )']), 'a Recall blocker runs on its own')


class DestinationTests(unittest.TestCase):
    CELLS = {'interior:caldera, guild of mages': 'Caldera, Guild of Mages',
             'interior:raven rock, bar': 'Raven Rock, Bar', 'exterior:-11,11': 'Gnisis'}

    def test_positioncell_arguments_in_their_several_spellings(self):
        self.assertEqual(parse_destination('PositionCell', ', 763, 702, 412, 60, "Caldera, Guild of Mages"'),
                         ('Caldera, Guild of Mages', 763.0, 702.0))
        self.assertEqual(parse_destination('PositionCell', '-87017 95351 1226 283 "Gnisis"'), ('Gnisis', -87017.0, 95351.0))
        self.assertEqual(parse_destination('PositionCell', '"Raven Rock, Bar" 4480.000 3968.000 15820.000 0'),
                         ('Raven Rock, Bar', 4480.0, 3968.0), 'the name may come first')
        self.assertEqual(parse_destination('PositionCell', '-828927 100235 3086 0 vos ;comment'), ('vos', -828927.0, 100235.0),
                         'an unquoted name')
        self.assertEqual(parse_destination('Position', '-79616, 95004, 1736, 260'), (None, -79616.0, 95004.0))
        self.assertIsNone(parse_destination('Position', 'nothing here'))

    def test_a_destination_resolves_to_a_cell_of_the_profile(self):
        self.assertEqual(resolve_cell('Caldera, Guild of Mages', 1, 1, self.CELLS), 'interior:caldera, guild of mages')
        self.assertEqual(resolve_cell('Gnisis', -87017, 95351, self.CELLS), 'exterior:-11,11',
                         'an exterior named by the cell it is in, found by position')
        self.assertIsNone(resolve_cell("Todd's Interior Wonderland", 0, 0, self.CELLS))


def condition(kind, function, comparison, value, variable=''):
    return {'rule_raw': f'0{kind}{function}{comparison}', 'value_json': json.dumps(value), 'variable_raw': variable}


class DialogueTests(unittest.TestCase):
    def test_the_function_table_follows_the_engine_enum(self):
        self.assertEqual((FUNCTIONS[0], FUNCTIONS[50], FUNCTIONS[73]), ('FacReactionLowest', 'Choice', 'PcWerewolfKills'))

    def test_a_menu_choice_is_not_a_condition_and_items_are_published_apart(self):
        context = {'conditions': [condition('1', '50', '0', 3), condition('5', 'X0', '3', 1, 'Index_Master'),
                                  condition('4', 'X0', '4', 15, 'BM_WildHunt')]}
        self.assertEqual(describe_conditions(context), ['journal BM_WildHunt < 15'])
        self.assertEqual(dialogue_items(context), (['index_master'], []))

    def test_an_item_that_must_be_absent_diverts(self):
        self.assertEqual(dialogue_items({'conditions': [condition('5', 'X0', '0', 0, 'Ring')]}), ([], ['ring']))
        self.assertEqual(dialogue_items({'conditions': [condition('5', 'X0', '0', 'x', 'Ring')]}), ([], []),
                         'an unreadable value is left alone')


POLICY = {'everyday': [{'match': {'speaker': 'asciene rane'}, 'why': 'service'}],
          'questOnly': [{'match': {'topic': 'must be stopped'}, 'why': 'quest'}]}


class GateTests(unittest.TestCase):
    def reason(self, **record):
        return gate_reason({'kind': 'dialogue', 'conditions': [], 'requires': [], 'profile': 'vanilla'} | record, POLICY)

    def test_everyday_travel(self):
        self.assertIsNone(self.reason(kind='propylon', requires=['index_andra']))
        self.assertIsNone(self.reason(kind='item', requires=['amulet']))
        self.assertIsNone(self.reason(requires=['index_master']), 'a dialogue gated only by an item')
        self.assertIsNone(self.reason(speaker='asciene rane'), 'named in the policy')

    def test_quest_travel_says_why(self):
        self.assertEqual(self.reason(topic='must be stopped'), 'authored')
        self.assertEqual(self.reason(kind='propylon', conditions=['journal x > 1']), 'conditions')
        self.assertEqual(self.reason(topic='greeting 1'), 'greeting')
        self.assertEqual(self.reason(topic='food for us'), 'dialogue topic')
        self.assertEqual(self.reason(kind='activator'), 'activator')

    def test_a_rule_scoped_to_other_profiles_does_not_apply(self):
        policy = {'everyday': [], 'questOnly': [{'match': {'topic': 'x'}, 'profiles': ['tr'], 'why': 'q'}]}
        record = {'kind': 'propylon', 'conditions': [], 'requires': [], 'topic': 'x'}
        self.assertIsNone(gate_reason(record | {'profile': 'vanilla'}, policy))
        self.assertEqual(gate_reason(record | {'profile': 'tr'}, policy), 'authored')


class PolicyTests(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp())/'teleports.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_malformed_rules_are_refused(self):
        base = {'schemaVersion': '1.0.0', 'everyday': [], 'questOnly': []}
        for broken in ({'questOnly': [{'match': {'npc': 'x'}, 'why': 'y'}]},
                       {'everyday': [{'match': {'topic': 'x'}}]},
                       {'everyday': [{'match': {}, 'why': 'y'}]},
                       {'questOnly': [{'match': {'topic': 'x'}, 'why': 'y', 'profiles': ['skyrim']}]},
                       {'everyday': 'x'}, {'schemaVersion': '9'}):
            with self.assertRaises(ExportError, msg=repr(broken)):
                load_policy(self.write(base | broken))

    def test_the_shipped_policy_loads(self):
        policy = load_policy(Path(__file__).parent/'policy/teleports.json')
        self.assertTrue(any(r['match'].get('topic') == 'transport to mournhold' for r in policy['everyday']))


class Databases(unittest.TestCase):
    def dbs(self, sources, attachments=(), placed=(), cells=()):
        evidence, world, services = (sqlite3.connect(':memory:') for _ in range(3))
        for db in (evidence, world, services):
            self.addCleanup(db.close)
        evidence.executescript("""
          CREATE TABLE sources(version_id,kind,source_key,topic_key,plugin,source_text,dialogue_context_json);
          CREATE TABLE profile_sources(profile_id,version_id,origin_plugin);
          CREATE TABLE script_attachments(profile_id,script_key,object_version_id,record_type,object_key);""")
        for index, (kind, key, topic, text, context) in enumerate(sources, 1):
            evidence.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?)',
                             (index, kind, key, topic, 'p', text, json.dumps(context) if context else None))
            evidence.execute('INSERT INTO profile_sources VALUES(?,?,?)', ('vanilla', index, 'p'))
        for index, (script, rtype, obj) in enumerate(attachments, 1):
            evidence.execute('INSERT INTO script_attachments VALUES(?,?,?,?,?)', ('vanilla', script, index, rtype, obj))
        world.executescript("""
          CREATE TABLE placements(version_id,reference_key,object_key,cell_key,x,y,z);
          CREATE TABLE profile_placements(profile_id,reference_key,version_id,origin_plugin);
          CREATE TABLE objects(version_id,record_type,object_key,editor_id,name,plugin,script_key,model);
          CREATE TABLE profile_objects(profile_id,record_type,object_key,version_id,origin_plugin);""")
        for index, (obj, name, cell) in enumerate(placed, 1):
            world.execute('INSERT INTO placements VALUES(?,?,?,?,?,?,?)', (index, f'r{index}', obj, cell, 100, 200, 0))
            world.execute('INSERT INTO profile_placements VALUES(?,?,?,?)', ('vanilla', f'r{index}', index, 'p'))
            world.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?)', (index, 'X', obj, obj, name, 'p', None, None))
            world.execute('INSERT INTO profile_objects VALUES(?,?,?,?,?)', ('vanilla', 'X', obj, index, 'p'))
        services.execute('CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic)')
        for key, name in cells:
            services.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)', ('vanilla', key, name, 1, None, None, None, 0))
        return evidence, world, services

    CELLS = [('interior:caldera, guild of mages', 'Caldera, Guild of Mages'),
             ('interior:andasreth, propylon chamber', 'Andasreth, Propylon Chamber'),
             ('interior:berandas, propylon chamber', 'Berandas, Propylon Chamber'),
             ('interior:ebonheart, council', 'Ebonheart, Council'),
             ('interior:mournhold, palace', 'Mournhold, Palace')]

    def test_a_propylon_activator_travels_from_where_it_stands(self):
        dbs = self.dbs([('script', 'warp_andra', None, WARP, None)],
                       attachments=[('warp_andra', 'ACTI', 'propylon_andra')],
                       placed=[('propylon_andra', 'Andasreth Propylon', 'interior:berandas, propylon chamber')],
                       cells=self.CELLS)
        records, items, skipped = build(*dbs, 'vanilla')
        chamber = next(r for r in records if r['to'] == 'interior:andasreth, propylon chamber')
        self.assertEqual((chamber['kind'], chamber['from'], chamber['requires'], chamber['unless'], chamber['questGated']),
                         ('propylon', ['interior:berandas, propylon chamber'], ['index_andra'], ['index_master'], False))
        self.assertEqual(chamber['objectName'], 'Andasreth Propylon')

    def test_a_script_a_dialogue_starts_is_a_dialogue_transport(self):
        dbs = self.dbs([('dialogue', 'info1', 'transport', 'StartScript MHTransport', {'actor_key': 'asciene rane'}),
                        ('script', 'mhtransport', None, 'Player->PositionCell 1 2 3 0 "Mournhold, Palace"', None)],
                       placed=[('asciene rane', 'Asciene Rane', 'interior:ebonheart, council')], cells=self.CELLS)
        records, _, _ = build(*dbs, 'vanilla', {'everyday': [{'match': {'speaker': 'asciene rane'}, 'why': 's'}],
                                                'questOnly': []})
        self.assertEqual([(r['kind'], r['from'], r['to'], r['speakerName'], r['questGated']) for r in records],
                         [('dialogue', ['interior:ebonheart, council'], 'interior:mournhold, palace', 'Asciene Rane', False)])

    def test_what_is_left_out_is_counted(self):
        dbs = self.dbs([('script', 'npcmove', None, 'PositionCell 1 2 3 0 "Mournhold, Palace"', None),
                        ('script', 'orphan', None, 'Player->PositionCell 1 2 3 0 "Mournhold, Palace"', None),
                        ('script', 'onquest', None, 'Player->PositionCell 1 2 3 0 "Mournhold, Palace"', None),
                        ('script', 'band', None, 'Player->PositionCell 1 2 3 0 "Mournhold, Palace"\n'
                                                 'Player->PositionCell 1 2 3 0 "Ebonheart, Council"', None),
                        ('script', 'blocker', None, 'if ( CellChanged )\nPlayer->PositionCell 1 2 3 0 "Mournhold, Palace"\nendif', None),
                        ('script', 'todd', None, 'Player->PositionCell 1 2 3 0 "Toddtest"', None)],
                       attachments=[('npcmove', 'NPC_', 'someone'), ('onquest', 'NPC_', 'someone'),
                                    ('band', 'CLOT', 'mazed band'), ('blocker', 'ACTI', 'recall blocker'),
                                    ('todd', 'ACTI', 'todd door')], cells=self.CELLS)
        records, _, skipped = build(*dbs, 'vanilla')
        self.assertEqual(records, [])
        self.assertEqual(skipped, {'movesSomeoneElse': 1, 'scriptNothingStarts': 1, 'questScriptOnActor': 1,
                                   'itemWithSeveralDestinations': 2, 'activatorNotUsed': 1,
                                   'destinationNotInProfile': 1})

    def test_a_policy_rule_matching_nothing_fails_the_build(self):
        dbs = self.dbs([], cells=self.CELLS)
        with self.assertRaises(ExportError) as caught:
            build(*dbs, 'vanilla', {'everyday': [{'match': {'topic': 'gone'}, 'why': 'x'}], 'questOnly': []})
        self.assertIn('gone', str(caught.exception))

    def test_the_payload_names_the_items_it_needs(self):
        dbs = self.dbs([('script', 'warp_andra', None, WARP, None)],
                       attachments=[('warp_andra', 'ACTI', 'propylon_andra')],
                       placed=[('propylon_andra', 'Andasreth Propylon', 'interior:berandas, propylon chamber'),
                               ('index_andra', 'Andasreth Propylon Index', 'interior:caldera, guild of mages')],
                       cells=self.CELLS)
        payload = assemble(*dbs, 'vanilla', 'snap', {'everyday': [], 'questOnly': []})
        self.assertEqual(payload['items']['index_andra'], 'Andasreth Propylon Index')
        self.assertEqual(payload['derivation']['byKind'], {'propylon': 2})


if __name__ == '__main__':
    unittest.main()
