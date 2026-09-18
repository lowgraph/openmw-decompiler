"""Format only the previously selected sample records, not the full masters."""
import json
import struct
from pathlib import Path

root = Path(__file__).resolve().parent / 'items'
samples = json.loads((root / 'examples/sample-records.raw.json').read_text())
attributes = ['strength', 'intelligence', 'willpower', 'agility', 'speed', 'endurance', 'personality', 'luck']
effect_names = {14: 'Fire Damage', 17: 'Drain Attribute', 74: 'Restore Attribute', 79: 'Fortify Attribute'}

def unpack(fmt, data):
    return struct.unpack('<' + fmt, data)

def text(data):
    return data.rstrip(b'\0').decode('cp1252') if data else None

def effect(data):
    ident, skill, attribute, target, area, duration, low, high = unpack('Hbb5i', data)
    return {'effectId': ident, 'name': effect_names[ident],
            'range': ['self', 'touch', 'target'][target],
            'magnitude': {'min': low, 'max': high}, 'durationSeconds': duration,
            'areaFeet': area, 'skill': None if skill == -1 else str(skill),
            'attribute': None if attribute == -1 else attributes[attribute]}

names = {'ARMO': 'Armor', 'CLOT': 'Clothing', 'BOOK': 'Books', 'ALCH': 'Potions',
         'INGR': 'Ingredients', 'APPA': 'Apparatus', 'LOCK': 'Lockpicks',
         'PROB': 'Probes', 'REPA': 'RepairTools', 'LIGH': 'Lights', 'MISC': 'Miscellaneous'}
for tag, name in names.items():
    sample = samples[tag]
    fields = [(f['tag'], bytes.fromhex(f['hex'])) for f in sample['fields']]
    data = dict(fields)
    item = {'id': sample['id'], 'name': text(data['FNAM']),
            'gameDataVersion': {'world': 'vanilla', 'version': 'OpenMW 0.51.0'},
            'sourcePlugin': 'Morrowind.esm', 'model': text(data.get('MODL')),
            'icon': text(data.get('ITEX', data.get('TEXT') if tag == 'ALCH' else None)),
            'script': text(data.get('SCRI'))}
    if tag in ('ARMO', 'CLOT'):
        if tag == 'ARMO':
            kind, weight, value, health, enchantp, armor = unpack('if4i', data['AODT'])
            item.update(health=health, armorRating=armor)
            kinds = ['helmet', 'cuirass', 'left_pauldron', 'right_pauldron', 'greaves', 'boots', 'left_gauntlet', 'right_gauntlet', 'shield', 'left_bracer', 'right_bracer']
        else:
            kind, weight, value, enchantp = unpack('ifHH', data['CTDT'])
            kinds = ['pants', 'shoes', 'shirt', 'belt', 'robe', 'right_glove', 'left_glove', 'skirt', 'ring', 'amulet']
        parts = []
        for key, value_bytes in fields:
            if key == 'INDX':
                parts.append({'slot': value_bytes[0], 'male': None, 'female': None})
            elif key in ('BNAM', 'CNAM'):
                parts[-1]['male' if key == 'BNAM' else 'female'] = text(value_bytes)
        item.update(type=kinds[kind], enchantp=enchantp, enchantment=None, bodyParts=parts)
    elif tag == 'BOOK':
        weight, value, scroll, skill, enchantp = unpack('f4i', data['BKDT'])
        assert skill == 9
        item.update(isScroll=bool(scroll), skill='enchant', enchantp=enchantp, enchantment=None, text=text(data['TEXT']))
    elif tag == 'ALCH':
        weight, value, flags = unpack('fii', data['ALDT'])
        item.update(autoCalculate=bool(flags & 1), effects=[effect(v) for k, v in fields if k == 'ENAM'])
    elif tag == 'INGR':
        weight, value, *values = unpack('f13i', data['IRDT'])
        item['effects'] = [{'slot': i, 'effectId': values[i], 'name': effect_names[values[i]],
                            'skill': None, 'attribute': attributes[values[i + 8]] if values[i] in (17, 74, 79) else None}
                           for i in range(4) if values[i] != -1]
    elif tag == 'APPA':
        kind, quality, weight, value = unpack('iffi', data['AADT'])
        item.update(type=['mortar_and_pestle', 'alembic', 'calcinator', 'retort'][kind], quality=quality)
    elif tag in ('LOCK', 'PROB'):
        weight, value, quality, uses = unpack('fifi', data['LKDT' if tag == 'LOCK' else 'PBDT'])
        item.update(quality=quality, uses=uses)
    elif tag == 'REPA':
        weight, value, uses, quality = unpack('fiif', data['RIDT'])
        item.update(quality=quality, uses=uses)
    elif tag == 'LIGH':
        weight, value, duration, radius, color, flags = unpack('fiiiIi', data['LHDT'])
        item.update(durationSeconds=duration, radius=radius,
                    color={key: (color >> (i * 8)) & 255 for i, key in enumerate(('r', 'g', 'b'))},
                    sound=text(data.get('SNAM')),
                    flags=[label for i, label in enumerate(['dynamic', 'carry', 'negative', 'flicker', 'fire', 'off_default', 'flicker_slow', 'pulse', 'pulse_slow']) if flags & (1 << i)])
    elif tag == 'MISC':
        weight, value, is_key = unpack('fii', data['MCDT'])
        item.update(isKey=bool(is_key))
    item.update(weight=weight, value=value)
    (root / 'examples' / f'{name}.sample.json').write_text(json.dumps(item, indent=2) + '\n', encoding='utf-8')
print('Formatted 11 additional samples; Goldbrand is the weapon sample.')
