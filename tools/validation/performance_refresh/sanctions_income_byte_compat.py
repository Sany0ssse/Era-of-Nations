"""Exact inverse of one reviewed sanctions-income loop deletion.

Only historical byte guards may use the projection. Actual source behavior is
never replaced with the legacy algorithm. Strict certification accepts exactly
the registered whole before/candidate files; inverse mutations retain foreign
bytes so an older whole-file guard can reject them.
"""
from pathlib import Path
import hashlib, json

SOURCE_PATH = 'common/scripted_effects/00_money_system.txt'
BEFORE_SHA256 = '38788567d06d4fa2f31afe0bb0d633081e964cd78dd53a5febff1cfd11d07c1f'
CANDIDATE_SHA256 = '65e429a2e8fd3cab9cfbadd1551e89a8e431fc89a6acace2e8aa6f9d444aa47c'
DELETED_SHA256 = 'fdf963724993650d8c7b5db3a8d43318473deb85d793cc6bf33d888142f36929'
CATALOG_SHA256 = '41c4c031eff89ffba973430e7d15912e9babe7dd1222be746f4e0ece1228a84c'
CATALOG_PATH = Path(__file__).with_name('_sanctions_income_source_island.json')
_raw_catalog = CATALOG_PATH.read_bytes()
assert hashlib.sha256(_raw_catalog).hexdigest() == CATALOG_SHA256, 'Exact sanctions catalog required'
CATALOG = json.loads(_raw_catalog)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def spans():
    assert CATALOG['version'] == 1 and CATALOG['path'] == SOURCE_PATH
    assert CATALOG['before_sha256'] == BEFORE_SHA256
    assert CATALOG['candidate_sha256'] == CANDIDATE_SHA256
    assert CATALOG['deleted_byte_span'] == [20387,21232] and CATALOG['deleted_bytes'] == 845
    assert CATALOG['deleted_sha256'] == DELETED_SHA256
    deleted = CATALOG['deleted_utf8'].encode('utf-8')
    assert len(deleted) == 845 and sha(deleted) == DELETED_SHA256, 'Exact deleted bytes required'
    lead, tail = CATALOG['lead_utf8'].encode(), CATALOG['tail_utf8'].encode()
    assert lead == b'\tclear_variable = sanctions_evasion_income\n'
    assert tail == b'\tadd_to_variable = { additional_income_rate = sanctions_evasion_income }\n'
    return lead, deleted, tail

def restore_sanctions_income_loop(relative, raw):
    if relative != SOURCE_PATH: return raw
    if isinstance(raw, str):
        return restore_sanctions_income_loop(relative, raw.encode('utf-8')).decode('utf-8')
    assert isinstance(raw, bytes), 'Sanctions byte inverse needs bytes or str'
    lead, deleted, tail = spans()
    fixed, legacy = lead+tail, lead+deleted+tail
    assert raw.count(lead) == raw.count(tail) == 1, 'Unique clear/add anchors required'
    if raw.count(legacy) == 1:
        assert raw.count(fixed) == 0 and raw.count(deleted) == 1, 'One exact baseline span required'
        return raw  # Registered before shape; keep every foreign byte visible.
    assert raw.count(fixed) == 1 and raw.count(legacy) == raw.count(deleted) == 0, 'One exact fixed span required'
    return raw.replace(fixed, legacy, 1)

def certify_sanctions_money_source(raw):
    if isinstance(raw, str): raw = raw.encode('utf-8')
    assert isinstance(raw, bytes)
    digest = sha(raw)
    assert digest in {BEFORE_SHA256,CANDIDATE_SHA256}, 'Unreviewed whole money source'
    restored = restore_sanctions_income_loop(SOURCE_PATH,raw)
    assert sha(restored) == BEFORE_SHA256, 'Exact 845-byte inverse must reach current-before source'
    lead, deleted, tail = spans()
    if digest == CANDIDATE_SHA256:
        assert restored.replace(lead+deleted+tail,lead+tail,1) == raw, 'Exact forward transform'
    else: assert restored == raw, 'Before source must pass through unchanged'
    return {'source_sha256': digest, 'restored_sha256': BEFORE_SHA256, 'deleted_bytes':845,
            'native_behavior_proven':False}
