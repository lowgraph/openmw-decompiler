"""Validate schemas, empty datasets, and the twelve selected sample items."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / '.validation-deps'))
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

root = Path(__file__).resolve().parent / 'items'
registry = Registry()
for path in (root / 'schemas').glob('*.json'):
    schema = json.loads(path.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    registry = registry.with_resource(path.as_uri(), Resource.from_contents(schema))

count = 0
for schema_path in (root / 'schemas').glob('*.schema.json'):
    if schema_path.name == 'Common.schema.json':
        continue
    path = root / schema_path.name.replace('.schema.json', '.json')
    dataset = json.loads(path.read_text(encoding='utf-8'))
    validator = Draft202012Validator({'$ref': schema_path.as_uri()}, registry=registry)
    validator.validate(dataset)
    sample_path = root / 'examples' / ('Goldbrand.json' if path.stem == 'Weapons' else f'{path.stem}.sample.json')
    sample = json.loads(sample_path.read_text(encoding='utf-8'))
    validator.validate({**dataset, 'items': [sample]})
    count += 1
print(f'Validated {count} datasets, their schemas, and {count} sample items.')
