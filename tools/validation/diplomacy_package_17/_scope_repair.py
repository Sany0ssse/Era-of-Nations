"""Exact, test-only inverse views for accepted support scope/registry repairs.

Only byte-preservation checks use this view. Behavioral adapters execute current
AST; no source file, global Path reader or behavioral condition is replaced.
The journal contains complete before/after hashes and exact byte islands, so an
unowned suffix, condition change or second occurrence is rejected.
"""
from pathlib import Path
import hashlib
import json

JOURNAL = json.loads(Path(__file__).with_name('_scope_repair.json').read_text(encoding='utf-8'))


def inverse(group, path, actual):
    entry = JOURNAL[group].get(path)
    if entry is None: return actual
    digest = hashlib.sha256(actual).hexdigest()
    if digest == entry['before_sha256']: return actual
    assert digest == entry['after_sha256'], ('Unowned repair byte mutation', group, path, digest)
    restored = actual
    for start, end, before, after in reversed(entry['islands']):
        before, after = bytes.fromhex(before), bytes.fromhex(after)
        assert restored[start:end] == after, ('Repair island drift', group, path, start)
        restored = restored[:start] + before + restored[end:]
    assert hashlib.sha256(restored).hexdigest() == entry['before_sha256'], ('Incomplete repair inverse', group, path)
    return restored


def game_before(path, actual):
    # Independently accepted, disjoint repairs; never execute this byte view.
    return inverse('registry', path, inverse('equipment_field', path, inverse('support_reads', path, actual)))


def test_before(path, actual):
    return inverse('test_adapters', path, actual)
