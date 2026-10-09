"""Digest-bound historical view for exactly two treasury-bound guard additions.

Only historical byte assertions may use this projection. Behavior tests read
current game bytes with both new guards. Prior flag-scope journals stay intact.
"""
from pathlib import Path
import hashlib
import json

JOURNAL = json.loads(Path(__file__).with_name('_source_islands.json').read_text(encoding='utf-8'))

def before_aid_cash_bounds(path, raw):
    if path != JOURNAL['path']:
        return raw
    digest = hashlib.sha256(raw).hexdigest()
    if digest == JOURNAL['before']:
        return raw
    assert digest == JOURNAL['after'], 'Unreviewed cash-bound bytes; refuse historical normalization'
    for edit in JOURNAL['edits']:
        old, new = bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
        assert raw.count(new) == 1, 'Cash guard island missing or duplicated'
        raw = raw.replace(new, old, 1)
    assert hashlib.sha256(raw).hexdigest() == JOURNAL['before']
    return raw
