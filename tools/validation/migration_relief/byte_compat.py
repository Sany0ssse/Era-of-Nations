"""Restore seven native98 migration money islands for historical byte guards.

Only exact snippets are restored; the caller compares the whole foreign
prefix/suffix with the historical Git blob after its other reviewed islands.
"""
from pathlib import Path
import hashlib
import json

CATALOG_PATH = Path(__file__).with_name('_money_source_islands.json')
CATALOG = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
SOURCE_PATH = 'common/scripted_effects/00_money_system.txt'


def restore_migration_money(path, text):
    if path != SOURCE_PATH:
        return text
    for island in CATALOG['islands']:
        current, original = island['current'], island['original']
        for key, body in (('current', current), ('original', original)):
            if hashlib.sha256(body.encode('utf-8')).hexdigest() != island[key+'_sha256']:
                raise AssertionError('Migration byte catalog digest mismatch')
        if text.count(current) != 1:
            raise AssertionError('Exact unique native98 migration island required: '+island['label'])
        text = text.replace(current, original, 1)
    return text


def negative_controls(text):
    restored = restore_migration_money(SOURCE_PATH, text)
    labels = []
    for island in CATALOG['islands']:
        mutant = text.replace(island['current'], island['current']+'# foreign island mutation\n', 1)
        changed = restore_migration_money(SOURCE_PATH, mutant)
        if hashlib.sha256(changed.encode('utf-8')).digest() == hashlib.sha256(restored.encode('utf-8')).digest():
            raise AssertionError('Adjacent unrelated mutation was swallowed')
        labels.append('preserved foreign bytes beside '+island['label'])
        mutant = text.replace(island['current'], island['current'].replace('=', '!=', 1), 1)
        try:
            restore_migration_money(SOURCE_PATH, mutant)
        except AssertionError:
            labels.append('rejected changed island '+island['label'])
        else:
            raise AssertionError('Changed migration island was silently accepted')
    return labels
