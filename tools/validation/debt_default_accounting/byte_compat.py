"""Digest-bound inverse for historical bailout byte checks, never behavior tests."""
from pathlib import Path
import hashlib
import json

JOURNAL = json.loads(Path(__file__).with_name('_source_islands.json').read_text(encoding='utf-8-sig'))
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def restore_before_default_repair(raw, path='common/decisions/bankruptcy_decisions.txt'):
    entry = JOURNAL[path]
    digest = sha(raw)
    if digest == entry['before']:
        return raw
    assert digest == entry['after'], 'Unreviewed source bytes; refuse historical normalization'
    rebuilt = raw
    shift = 0
    edits = sorted(entry['edits'], key=lambda edit: edit['start'])
    positions = []
    for edit in edits:
        old, new = bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
        at = edit['start'] + shift
        assert rebuilt[at:at + len(new)] == new, 'Default source island mismatch'
        positions.append((at, old, new))
        shift += len(new) - len(old)
    for at, old, new in reversed(positions):
        rebuilt = rebuilt[:at] + old + rebuilt[at + len(new):]
    assert sha(rebuilt) == entry['before'], 'Unowned byte difference after inverse'
    return rebuilt
