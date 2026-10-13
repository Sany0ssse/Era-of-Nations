"""Exact six-selector projection only; no historical proof is broadened."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
BEFORE_SHA = 'a1b01f64430aae6d5fe92af8f0b90bcc1930a8691cf2fbb5834e34ce4c57cad2'
AFTER_SHA = '8a557c7994254e2708fd2c9a51cb9edae7b36cc986c2038fe4d09f695500b972'
CATALOG_SHA = '07acbf45fe562586ad31e1611aebad4158882556d3129e7e712e7d37af4e11d3'

def restore_reserved_selectors(raw):
    digest = hashlib.sha256(raw).hexdigest()
    # Keep the actual exact previous checkout usable before promotion.
    if digest == BEFORE_SHA: return raw
    assert digest == AFTER_SHA, 'Unreviewed source bytes outside the approved six-selector version'
    catalog_raw = (HERE / 'canonical_reserved_selectors.json').read_bytes()
    assert hashlib.sha256(catalog_raw).hexdigest() == CATALOG_SHA, 'Unreviewed selector catalog'
    catalog = json.loads(catalog_raw)
    assert catalog['before_sha256'] == BEFORE_SHA and catalog['after_sha256'] == AFTER_SHA
    assert len(catalog['fields']) == 6
    for fields in catalog['fields'].values():
        new, old = fields['after'].encode('utf-8'), fields['before'].encode('utf-8')
        assert raw.count(new) == 1, 'Missing/duplicate reviewed selector'
        raw = raw.replace(new, old, 1)
    assert hashlib.sha256(raw).hexdigest() == BEFORE_SHA, 'Unowned inverse bytes changed'
    return raw
