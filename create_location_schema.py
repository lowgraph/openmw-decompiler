"""Generate the standalone location schema without touching item datasets."""
import json
from pathlib import Path


def obj(fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}


def array(item):
    return {'type': 'array', 'items': item}


def nullable(item):
    return {'anyOf': [item, {'type': 'null'}]}


def enum(*values):
    return {'enum': list(values)}


def ref(name):
    return {'$ref': '#/$defs/' + name}


string = {'type': 'string'}
integer = {'type': 'integer'}
number = {'type': 'number'}
boolean = {'type': 'boolean'}
version = obj({'world': enum('vanilla', 'tamriel_rebuilt'), 'version': string})
vector = obj(dict.fromkeys(('x', 'y', 'z'), number))
cell = obj({'id': string, 'name': nullable(string), 'interior': boolean,
            'grid': nullable(obj({'x': integer, 'y': integer})), 'regionId': nullable(string)})
step = obj({'id': string, 'kind': enum('CONT', 'NPC_', 'CREA', 'LEVI', 'LEVC'), 'name': string,
            'sourcePlugin': string, 'entryIndex': integer, 'entryId': string, 'count': integer,
            'minimumLevel': nullable(integer), 'chanceNone': nullable(integer),
            'flags': nullable(integer), 'scriptId': nullable(string)})
access = obj({'ownerId': nullable(string), 'factionId': nullable(string), 'requiredFactionRank': nullable(integer),
              'ownershipGlobal': nullable(string), 'takingIsTheft': enum('conditional', 'not_marked_owned'),
              'lockLevel': integer, 'keyId': nullable(string), 'trapId': nullable(string),
              'saleStatus': enum('not_determined')})
location = obj({'referenceId': string, 'sourcePlugin': string, 'gameDataVersion': ref('GameDataVersion'),
                'cell': cell, 'position': nullable(vector), 'rotation': nullable(vector),
                'sourceType': enum('placed', 'container', 'npc_inventory', 'creature_inventory'),
                'rootObjectId': string, 'containerId': nullable(string), 'actorId': nullable(string),
                'count': {'type': 'integer', 'minimum': 1}, 'restocking': boolean,
                'availability': enum('leveled_chance', 'static_definition'), 'path': array(step),
                'scriptIds': array(string), 'soulId': nullable(string), 'access': access, 'label': string})
lead = obj({'kind': enum('script', 'dialogue_result'), 'id': string, 'sourcePlugin': string,
            'topic': nullable(string), 'actorId': nullable(string),
            'evidence': array(obj({'line': {'type': 'integer', 'minimum': 1}, 'text': string})),
            'interpretation': enum('unverified_text_reference')})
schema = obj({'schemaVersion': {'const': '1.0.0'},
              'coverage': obj({'mode': {'const': 'static_plugin_analysis'}, 'plugins': array(string),
                               'excludedContent': array(string), 'warnings': array(string),
                               'scriptsWithoutSource': array(string), 'limitations': array(string)}),
              'items': array(obj({'itemId': string, 'gameDataVersion': ref('GameDataVersion'),
                                  'locations': array(location), 'scriptReferences': array(lead)}))})
schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
schema['$defs'] = {'GameDataVersion': version}
if __name__ == '__main__':
    Path(__file__).with_name('location-schema.json').write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
