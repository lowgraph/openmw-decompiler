"""Read one sample per inventory record type, seeking past other payloads."""
import json
import struct
from pathlib import Path

source = Path(r'A:\SteamLibrary\steamapps\common\Morrowind\Data Files\Morrowind.esm')
wanted = {'WEAP', 'ARMO', 'CLOT', 'BOOK', 'ALCH', 'INGR', 'APPA', 'LOCK', 'PROB', 'REPA', 'LIGH', 'MISC', 'ENCH'}
samples = {}
with source.open('rb') as stream:
    while header := stream.read(16):
        tag, size, unknown, flags = struct.unpack('<4sIII', header)
        tag = tag.decode('ascii')
        if tag not in wanted or tag in samples:
            stream.seek(size, 1)
            continue
        data = stream.read(size)
        fields = []
        pos = 0
        while pos < len(data):
            key, length = struct.unpack_from('<4sI', data, pos)
            pos += 8
            value = data[pos:pos + length]
            fields.append((key.decode('ascii'), value))
            pos += length
        values = dict(fields)
        ident = values.get('NAME', b'').rstrip(b'\0').decode('cp1252')
        if tag == 'WEAP' and ident != 'katana_goldbrand_unique':
            continue
        if tag == 'ENCH' and ident != 'goldbrand':
            continue
        if tag == 'LIGH' and not (struct.unpack_from('<I', values['LHDT'], 20)[0] & 2):
            continue
        samples[tag] = {'id': ident, 'recordFlags': flags, 'fields': [
            {'tag': key, 'hex': value.hex(), **({'text': value.rstrip(b'\0').decode('cp1252')} if key in ('NAME', 'FNAM', 'MODL', 'ITEX', 'SCRI', 'ENAM', 'TEXT') and not (key == 'ENAM' and tag in ('ALCH', 'ENCH')) else {})}
            for key, value in fields
        ]}
        if len(samples) == len(wanted):
            break
out = Path(__file__).resolve().parent / 'items' / 'examples'
out.mkdir(parents=True, exist_ok=True)
(out / 'sample-records.raw.json').write_text(json.dumps(samples, indent=2) + '\n', encoding='utf-8')
for tag, sample in samples.items():
    print(tag, sample['id'])
    for field in sample['fields']:
        print(' ', field['tag'], field.get('text', field['hex'])[:400])
