"""Exact historical byte view of the separately approved ammo port tally.

This restores one frozen span for old source assertions. Behavior tests still
read current game files; no gameplay bytes are changed here.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'common/scripted_effects/00_ammo_mechanics_effects.txt'
HISTORICAL_SHA256 = '198db754b38ffc21f317d4791822c2da7c5f7a33b9352b17c2fe7d89ba8b6feb'
APPROVED_SOURCE_SHA256 = '3e6dcef1879df5a4396efda47379e4d382a239332f9b9953072c990d39fbd644'
APPROVED_SPAN_SHA256 = '3582ee408494d30624c4e08a74936849937148e017b10f0e2d8ce033ae202b8f'
PROOF = ROOT / 'tools/validation/performance_policy'


def historical_ammo_mechanics_bytes(actual, *, catalog=None, original=None):
    """Undo only the exact approved port span and require the whole old file."""
    if catalog is None:
        catalog = json.loads((PROOF / 'canonical_ammo_ports.json').read_text('utf-8'))
    if original is None:
        original = (PROOF / 'fixtures/ammo_port_mechanics_baseline.txt').read_bytes()
    required = {'source', 'baseline_sha256', 'candidate_sha256', 'before_span',
                'candidate_span', 'candidate_span_sha256'}
    assert required <= catalog.keys(), 'Incomplete approved port catalog'
    assert catalog['source'] == SOURCE, 'Port catalog source path changed'
    assert catalog['baseline_sha256'] == HISTORICAL_SHA256
    assert catalog['candidate_sha256'] == APPROVED_SOURCE_SHA256
    assert hashlib.sha256(original).hexdigest() == HISTORICAL_SHA256, 'Whole historical ammo bytes changed'
    assert isinstance(catalog['before_span'], str) and isinstance(catalog['candidate_span'], str)
    before = catalog['before_span'].encode('utf-8')
    after = catalog['candidate_span'].encode('utf-8')
    assert catalog['candidate_span_sha256'] == APPROVED_SPAN_SHA256
    assert hashlib.sha256(after).hexdigest() == APPROVED_SPAN_SHA256, 'Approved port span changed'
    assert before and original.count(before) == 1, 'Historical port span must occur exactly once'
    assert original.count(after) == 0
    if actual == original:
        return original
    assert actual.count(after) == 1, 'Approved current port span missing or duplicated'
    restored = actual.replace(after, before, 1)
    assert restored == original, 'Unowned ammo mechanics bytes changed'
    assert hashlib.sha256(restored).hexdigest() == HISTORICAL_SHA256
    return restored
