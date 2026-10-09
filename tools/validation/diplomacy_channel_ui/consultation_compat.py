"""Exact inverse of approved later repairs, for historical preservation only.

Behavior tests execute current AST. This adapter never replaces runtime effects
with historical code and rejects any change outside the approved byte islands.
"""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[3]
JOURNAL = Path(__file__).with_name('_consultation_ux_islands.json')
JOURNAL_SHA256 = 'b488572971ea8e4a91b93f659cc771e7440a9e1149065591a4c33cdb28d42e0c'
CORE = {
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def journal():
    raw = JOURNAL.read_bytes()
    assert sha(raw) == JOURNAL_SHA256, 'UX preservation journal changed'
    result = json.loads(raw)
    assert result['schema'] == 1
    assert result['baseline_commit'] == 'b174de7fcd77ec386fdf65b79caa3d9613d76d85'
    expected = {'events/eon_consultation_events.txt': 10}
    for lang in ('english', 'russian'):
        expected[f'localisation/{lang}/eon_consultation_l_{lang}.yml'] = 10
        expected[f'localisation/{lang}/eon_consultation_ui_l_{lang}.yml'] = 5
    assert {p: len(v['islands']) for p, v in result['files'].items()} == expected
    return result


def restore_before(path, raw=None):
    current = (ROOT / path).read_bytes() if raw is None else raw
    if path in CORE:
        location = ROOT / 'tools/validation/consultation_lifecycle_completion/_source_guard.py'
        spec = importlib.util.spec_from_file_location('consultation_core_preservation', location)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.restore_before(path, current)
    files = journal()['files']
    if path not in files:
        return current
    item = files[path]
    assert sha(current) == item['after_sha256'], ('Unexpected UX bytes', path)
    assert current.startswith(b'\xef\xbb\xbf') == item['bom']
    if item['line_ending'] == 'LF':
        assert b'\r' not in current
    else:
        assert item['line_ending'] == 'CRLF'
        assert b'\r' not in current.replace(b'\r\n', b'')
        assert b'\n' not in current.replace(b'\r\n', b'')
    for island in reversed(item['islands']):
        prior, after = island['before'].encode('utf-8'), island['after'].encode('utf-8')
        assert current.count(after) == 1, ('Missing or repeated approved UX island', path, island['id'])
        current = current.replace(after, prior)
    assert sha(current) == item['before_sha256'], ('Outside-island UX change', path)
    return current
