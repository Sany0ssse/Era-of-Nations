"""Frozen exact energy-AI islands for historical source-byte checks.

The JSON is a reviewed before/after patch, never a runtime-generated allowlist.
Only the five GUI policy weights, weekly draft preparation, cancellation
weight, and later recipient-AI reply selector are projected. Every byte outside each island stays visible to callers.
"""
from pathlib import Path
import hashlib
import json

CATALOG = json.loads((Path(__file__).with_name('canonical_energy_ai.json')).read_text(encoding='utf-8'))
SELECTOR_CATALOG = json.loads((Path(__file__).with_name('canonical_energy_selector.json')).read_text(encoding='utf-8'))


def restore_energy_selector(path, raw):
    """Project only the frozen later selector before the original AI islands."""
    if path not in SELECTOR_CATALOG:
        return raw
    patch = SELECTOR_CATALOG[path]
    before, after = patch['before'].encode('utf-8'), patch['after'].encode('utf-8')
    assert hashlib.sha256(before).hexdigest() == patch['before_island_sha256'], 'Changed canonical selector before island'
    assert hashlib.sha256(after).hexdigest() == patch['after_island_sha256'], 'Changed canonical selector after island'
    assert raw.count(after) == 1, 'Changed, missing, or duplicated canonical energy selector: ' + path
    return raw.replace(after, before, 1)


def restore_energy_ai(path, raw):
    raw = restore_energy_selector(path, raw)
    patch = CATALOG[path]
    before, after = patch['before'].encode('utf-8'), patch['after'].encode('utf-8')
    assert hashlib.sha256(before).hexdigest() == patch['before_island_sha256'], 'Changed canonical before island'
    assert hashlib.sha256(after).hexdigest() == patch['after_island_sha256'], 'Changed canonical after island'
    assert raw.count(after) == 1, 'Changed, missing, or duplicated canonical energy-AI island: ' + path
    return raw.replace(after, before, 1)


def negative_controls(path, raw):
    patch = CATALOG[path]
    after = patch['after'].encode('utf-8')
    cases = []
    for label, mutated in (
        ('changed_owned_island', raw.replace(after, after.replace(b'\n', b'\n# changed policy\n', 1), 1)),
        ('missing_owned_island', raw.replace(after, b'', 1)),
        ('duplicated_owned_island', raw + after),
    ):
        assert mutated != raw
        try:
            restore_energy_ai(path, mutated)
        except AssertionError:
            cases.append(label)
        else:
            raise AssertionError('Accepted negative control: ' + label)
    # A correct owned island never hides unrelated changes elsewhere in a file.
    unrelated = b'# foreign mutation\n' + raw
    projected = restore_energy_ai(path, unrelated)
    assert hashlib.sha256(projected).hexdigest() != patch['before_file_sha256']
    cases.append('unrelated_byte_change')
    return cases
