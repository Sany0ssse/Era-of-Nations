"""Finite eight-file whole-byte ownership certificate for historical views.

Before and AFTER must each be a complete cohort. Foreign/mixed bytes never vanish.
New lifecycle tests consume actual AFTER AST, without this projection.
"""
from pathlib import Path
import base64
import hashlib
import json

CATALOG = json.loads((Path(__file__).resolve().parent / 'catalog.json').read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def certify_cohort(actual):
    assert isinstance(actual, dict) and set(actual) == set(CATALOG), 'Exact eight-path source cohort required'
    roles = set()
    originals = {}
    for path, record in CATALOG.items():
        raw = actual[path]
        assert isinstance(raw, bytes), ('Source bytes required', path)
        before = base64.b64decode(record['before_b64'], validate=True)
        assert sha(before) == record['before_sha256'], ('Corrupt preimage catalog', path)
        digest = sha(raw)
        if digest == record['before_sha256']:
            assert raw == before, ('Whole-byte preimage mismatch', path)
            role = 'before'
        else:
            assert digest == record['candidate_sha256'], ('Foreign source bytes', path, digest)
            role = 'after'
        roles.add(role)
        originals[path] = before
    assert len(roles) == 1, 'Mixed source cohorts rejected'
    return {'role': roles.pop(), 'originals': originals}
