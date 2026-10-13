"""Exact reviewed traversal island; all other delivery bytes stay immutable."""
from pathlib import Path
import hashlib,json,importlib.util
ROOT=Path(__file__).resolve().parents[3]

# Exact certified adjacent damage/state boundary only; unknown effects stay closed.
_economy_spec=importlib.util.spec_from_file_location('eon_economy_refresh_compat',
    ROOT/'tools/validation/performance_refresh/byte_compat.py')
_economy_bytes=importlib.util.module_from_spec(_economy_spec)
_economy_spec.loader.exec_module(_economy_bytes)

CATALOG_PATH=Path(__file__).with_name('canonical_energy_traversal.json')
CATALOG=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))

def restore_energy_traversal(path,text):
    if path!=CATALOG['path']: return text
    text=_economy_bytes.restore_adjacent_state_refresh(path,text)
    current=CATALOG['current']; original=CATALOG['original']
    assert hashlib.sha256(current.encode()).hexdigest()==CATALOG['current_island_sha256']
    assert hashlib.sha256(original.encode()).hexdigest()==CATALOG['original_island_sha256']
    assert text.count(current)==1,'Exact unique reviewed traversal island required'
    restored=text.replace(current,original,1)
    raw=restored.encode('utf-8')
    if CATALOG['before_bom']:raw=b'\xef\xbb\xbf'+raw
    assert hashlib.sha256(raw).hexdigest()==CATALOG['before_sha256'],'Unreviewed bytes outside traversal island'
    return restored

def negative_controls(text):
    current=CATALOG['current']; assert text.count(current)==1
    mutants={
      'unreviewed phase quantity':text.replace('global.eon_energy_delivery_round < 64','global.eon_energy_delivery_round < 63',1),
      'lost former-participant cleanup':text.replace('has_country_flag = eon_energy_delivery_participant } }','always = no } }',1),
      'foreign delivery demand':text.replace('eon_energy_delivery_generation','eon_energy_delivery_generation_UNREVIEWED',1),
      'foreign whitespace':text+'\n',
    }
    rejected=[]
    for label,mutant in mutants.items():
        assert mutant!=text,label
        try: restore_energy_traversal(CATALOG['path'],mutant)
        except AssertionError:rejected.append(label)
        else:raise AssertionError('Unreviewed mutant accepted: '+label)
    return rejected
