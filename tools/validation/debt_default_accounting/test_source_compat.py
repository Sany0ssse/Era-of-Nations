"""Reject byte drift before a historical source-only inverse is attempted."""
from pathlib import Path
import hashlib
import json
from byte_compat import JOURNAL, restore_before_default_repair

ROOT = Path(__file__).resolve().parents[3]
rejected = 0
for path, entry in JOURNAL.items():
    current = (ROOT / path).read_bytes()
    assert hashlib.sha256(current).hexdigest() == entry['after']
    restored = restore_before_default_repair(current, path)
    assert hashlib.sha256(restored).hexdigest() == entry['before']
    assert restore_before_default_repair(restored, path) == restored
    probes = [current + b'\n']
    shift = 0
    for edit in sorted(entry['edits'], key=lambda item: item['start']):
        old, new = bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
        at = edit['start'] + shift
        assert current[at:at + len(new)] == new
        probes.append(current[:at] + b' ' + current[at:])
        shift += len(new) - len(old)
    for probe in probes:
        try:
            restore_before_default_repair(probe, path)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError(('Unreviewed bytes normalized', path))
reviewed_body_islands = sum(len(entry['edits']) for entry in JOURNAL.values())
assert reviewed_body_islands == 10
print(json.dumps({'files_verified': len(JOURNAL), 'reviewed_body_islands': reviewed_body_islands,
                  'byte_mutants_rejected': rejected,
                  'behavioral_tests_use_current_source': True}))
