"""Invert only digest-bound aid selector islands for historical source checks."""
from pathlib import Path
import hashlib
import json

JOURNAL=json.loads(Path(__file__).with_name('_source_islands.json').read_text(encoding='utf-8-sig'))

def before_aid_flag_repair(path,raw):
    if path not in JOURNAL:
        return raw
    entry=JOURNAL[path]
    digest=hashlib.sha256(raw).hexdigest()
    if digest==entry['before']:
        return raw
    assert digest==entry['after'], 'Unreviewed aid bytes; refuse historical normalization'
    positions=[]; shift=0
    for edit in sorted(entry['edits'],key=lambda item:item['start']):
        old,new=bytes.fromhex(edit['before']),bytes.fromhex(edit['after'])
        at=edit['start']+shift
        assert raw[at:at+len(new)]==new
        positions.append((at,old,new)); shift+=len(new)-len(old)
    for at,old,new in reversed(positions):
        raw=raw[:at]+old+raw[at+len(new):]
    assert hashlib.sha256(raw).hexdigest()==entry['before']
    return raw
