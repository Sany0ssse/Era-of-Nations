"""Digest-bound inverse for exactly ten consultation core source islands.

The inverse is only a preservation comparison. Runtime tests always execute
current source AST; historical restoration never supplies financial behavior.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
JOURNAL = Path(__file__).with_name('_source_islands.json')
JOURNAL_SHA256 = 'a3202e98fa14d64f21413319b57ae9d2b19eab235a05b889f93fc2ee8d749edd'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_journal():
    raw = JOURNAL.read_bytes()
    assert sha(raw) == JOURNAL_SHA256, 'Consultation island journal changed'
    receipt = json.loads(raw)
    assert receipt['schema'] == 1
    return receipt


def restore_before(relative_path, raw=None):
    """Verify complete current bytes, inverse only approved islands, verify old SHA."""
    item = load_journal()['files'][relative_path]
    current = (ROOT / relative_path).read_bytes() if raw is None else raw
    assert sha(current) == item['after_sha256'], ('Unexpected consultation bytes', relative_path)
    assert current.startswith(b'\xef\xbb\xbf') == item['bom']
    assert item['line_ending'] == 'LF' and b'\r' not in current
    for island in reversed(item['islands']):
        before, after = island['before'].encode('utf-8'), island['after'].encode('utf-8')
        assert current.count(after) == 1, ('Missing or repeated approved island', relative_path, island['name'])
        current = current.replace(after, before)
    assert sha(current) == item['before_sha256'], ('Outside-island byte change', relative_path)
    return current


def baseline_sources():
    return {path: restore_before(path) for path in load_journal()['files']}
