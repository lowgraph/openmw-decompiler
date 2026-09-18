"""Generate empty item datasets and JSON schemas; never reads game data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'items'
SCHEMAS = ROOT / 'schemas'
SCHEMAS.mkdir(parents=True, exist_ok=True)

def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def obj(properties, required=None):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': False}

def enum(*values):
    return {'type': 'string', 'enum': list(values)}

def ref(name):
    return {'$ref': f'Common.schema.json#/$defs/{name}'}

string = {'type': 'string'}
number = {'type': 'number', 'minimum': 0}
integer = {'type': 'integer', 'minimum': 0}
boolean = {'type': 'boolean'}
nullable_string = {'type': ['string', 'null']}
damage = obj({'min': number, 'max': number})
effect = obj({
    'effectId': {'type': 'integer'}, 'name': string,
    'range': enum('self', 'touch', 'target'),
    'magnitude': damage, 'durationSeconds': number, 'areaFeet': number,
    'skill': nullable_string, 'attribute': nullable_string,
}, ['effectId', 'name', 'range', 'magnitude'])
enchantment = obj({
    'id': string,
    'castType': enum('cast_once', 'when_strikes', 'when_used', 'constant_effect'),
    'cost': number, 'charges': number, 'autoCalculate': boolean,
    'effects': {'type': 'array', 'items': ref('Effect')},
}, ['id', 'castType', 'cost', 'charges', 'effects'])
common = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    '$defs': {
        'GameDataVersion': obj({'world': enum('vanilla', 'tamriel_rebuilt'),
                                'version': {'type': 'string', 'minLength': 1}}),
        'Damage': damage, 'Effect': effect, 'Enchantment': enchantment,
        'BodyPart': obj({'slot': {'type': 'integer', 'minimum': 0, 'maximum': 26}, 'male': nullable_string, 'female': nullable_string}),
    },
}
write(SCHEMAS / 'Common.schema.json', common)

ench = {'anyOf': [ref('Enchantment'), {'type': 'null'}]}
effects = {'type': 'array', 'items': ref('Effect')}
body = {'type': 'array', 'items': ref('BodyPart')}
categories = {
    'Weapons': ('WEAP', {
        'enchantp': number, 'health': integer,
        'type': enum('SB1H', 'LB1H', 'LB2H', 'BL1H', 'BL2C', 'BL2W', 'SP2H', 'AX1H', 'AX2H', 'BOW', 'CROSSBOW', 'THROWN', 'ARROW', 'BOLT'),
        'speed': number, 'reach': number, 'chop': ref('Damage'),
        'slash': ref('Damage'), 'thrust': ref('Damage'),
        'magical': boolean, 'silver': boolean, 'enchantment': ench,
    }),
    'Armor': ('ARMO', {'type': enum('helmet', 'cuirass', 'left_pauldron', 'right_pauldron', 'greaves', 'boots', 'left_gauntlet', 'right_gauntlet', 'shield', 'left_bracer', 'right_bracer'), 'health': integer, 'armorRating': integer,
                       'enchantp': number, 'enchantment': ench, 'bodyParts': body}),
    'Clothing': ('CLOT', {'type': enum('pants', 'shoes', 'shirt', 'belt', 'robe', 'right_glove', 'left_glove', 'skirt', 'ring', 'amulet'), 'enchantp': number, 'enchantment': ench, 'bodyParts': body}),
    'Books': ('BOOK', {'isScroll': boolean, 'text': string, 'skill': nullable_string,
                       'enchantp': number, 'enchantment': ench}),
    'Potions': ('ALCH', {'autoCalculate': boolean, 'effects': effects}),
    'Ingredients': ('INGR', {'effects': {'type': 'array', 'maxItems': 4, 'items': obj({
        'slot': {'type': 'integer', 'minimum': 0, 'maximum': 3},
        'effectId': {'type': 'integer'}, 'name': string,
        'skill': nullable_string, 'attribute': nullable_string,
    })}}),
    'Apparatus': ('APPA', {'type': enum('mortar_and_pestle', 'alembic', 'calcinator', 'retort'), 'quality': number}),
    'Lockpicks': ('LOCK', {'quality': number, 'uses': integer}),
    'Probes': ('PROB', {'quality': number, 'uses': integer}),
    'RepairTools': ('REPA', {'quality': number, 'uses': integer}),
    'Lights': ('LIGH', {'durationSeconds': {'type': 'integer', 'minimum': -1},
        'radius': integer, 'color': obj({key: {'type': 'integer', 'minimum': 0, 'maximum': 255} for key in ('r', 'g', 'b')}),
        'sound': nullable_string, 'flags': {'type': 'array', 'uniqueItems': True, 'contains': {'const': 'carry'}, 'items': enum('dynamic', 'carry', 'negative', 'flicker', 'fire', 'off_default', 'flicker_slow', 'pulse', 'pulse_slow')}}),
    'Miscellaneous': ('MISC', {'isKey': boolean}),
}

for name, (record, properties) in categories.items():
    base = {
        'id': {'type': 'string', 'minLength': 1}, 'name': string,
        'gameDataVersion': ref('GameDataVersion'),
        'sourcePlugin': string, 'weight': number, 'value': integer,
        'model': nullable_string, 'icon': nullable_string, 'script': nullable_string,
    }
    item = obj(base | properties, ['id', 'name', 'gameDataVersion', 'weight', 'value'] + list(properties))
    schema = obj({
        '$schema': string, 'schemaVersion': {'const': '1.0.0'},
        'recordType': {'const': record}, 'items': {'type': 'array', 'items': item},
    })
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    schema['title'] = name
    write(SCHEMAS / f'{name}.schema.json', schema)
    if not (ROOT / f'{name}.json').exists():
        write(ROOT / f'{name}.json', {
            '$schema': f'./schemas/{name}.schema.json',
            'schemaVersion': '1.0.0', 'recordType': record, 'items': [],
        })

(ROOT / 'examples').mkdir(exist_ok=True)
write(ROOT / 'examples' / 'Goldbrand.json', {
    'id': 'katana_goldbrand_unique', 'name': 'Goldbrand',
    'gameDataVersion': {'world': 'vanilla', 'version': 'OpenMW 0.51.0'},
    'sourcePlugin': 'Morrowind.esm',
    'weight': 40, 'value': 150000, 'enchantp': 700, 'health': 4500,
    'type': 'LB1H', 'speed': 1.5, 'reach': 1,
    'chop': {'min': 10, 'max': 50}, 'slash': {'min': 10, 'max': 45},
    'thrust': {'min': 10, 'max': 25}, 'magical': True, 'silver': False,
    'enchantment': {'id': 'goldbrand', 'castType': 'when_strikes', 'cost': 5, 'autoCalculate': True,
                    'charges': 50, 'effects': [
                        {'effectId': 14, 'name': 'Fire Damage', 'range': 'touch',
                         'magnitude': {'min': 10, 'max': 30}, 'durationSeconds': 1,
                         'areaFeet': 0, 'skill': None, 'attribute': None},
                    ]},
})
print(f'Created {len(categories)} empty item datasets, schemas, and Goldbrand example in {ROOT}')
