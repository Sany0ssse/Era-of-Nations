"""Exact SHA admission for three owned source islands. Hash comparisons only.

Callers execute and parse their actual current raw source. This module never
replaces file reads or returns canonical source to an AST/execution reader.
"""
from pathlib import Path
import base64,hashlib,json
HERE=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
raw=(HERE/'source_catalog.json').read_bytes()
assert sha(raw)=='95afced9fe77fc20347dfb54bc0c08d1bd973f21d26659928fb9b5175af87eed','Frozen source catalog drift'
CATALOG=json.loads(raw)
ROWS={r['path']:r for r in CATALOG['files']}
PAIR=set(CATALOG['investment_pair_paths'])
assert len(ROWS)==3 and len(PAIR)==2 and PAIR.issubset(ROWS)
def source_for_hash(raw,relative):
 """Only a SHA caller may use this exact full inverse; all other paths unchanged."""
 if relative not in ROWS:return raw
 row=ROWS[relative];h=sha(raw)
 if h==row['before_sha256']:return raw
 assert h==row['candidate_sha256'],('Foreign owned source bytes',relative)
 original=raw
 for p in reversed(row['patches']):
  at=p['offset'];old=base64.b64decode(p['before_b64'],validate=True);new=base64.b64decode(p['after_b64'],validate=True)
  assert 0<=at<=len(original) and original[at:at+len(new)]==new
  original=original[:at]+old+original[at+len(new):]
 assert sha(original)==row['before_sha256'],('Whole inverse mismatch',relative)
 assert original==(HERE/'before'/relative).read_bytes(),'Frozen entire before mismatch'
 assert original.startswith(b'\xef\xbb\xbf')==raw.startswith(b'\xef\xbb\xbf')
 assert original.count(b'\r')==raw.count(b'\r')==0
 return original
def verify_pair(source,read=None):
 source=Path(source).resolve();read=read or (lambda p:p.read_bytes())
 roles={}
 for relative in sorted(PAIR):
  raw=read(source/relative);row=ROWS[relative]
  source_for_hash(raw,relative)
  roles[relative]='after' if sha(raw)==row['candidate_sha256'] else 'before'
 assert len(set(roles.values()))==1,'Mixed old/new investment pair rejected'
 return next(iter(roles.values()))
def verify_owned_cohort(source,read=None):
 """Exact whole-three AI cohorts for v2 AFTER14; historical BEFORE6 stays separate."""
 source=Path(source).resolve();read=read or (lambda p:p.read_bytes())
 roles={}
 for relative,row in ROWS.items():
  actual=read(source/relative);source_for_hash(actual,relative)
  roles[relative]='after' if sha(actual)==row['candidate_sha256'] else 'before'
 assert len(set(roles.values()))==1,'Mixed old/new whole-three AI cohort rejected'
 return next(iter(roles.values()))

def verify_all_current(source):
 source=Path(source).resolve();cohort=verify_pair(source)
 for relative,expected in CATALOG['model_input_sha256'].items():
  assert sha((source/relative).read_bytes())==expected,('Declared actual model input drift',relative)
 for relative,row in ROWS.items():
  assert sha((HERE/'before'/relative).read_bytes())==row['before_sha256']
  actual=(source/relative).read_bytes();source_for_hash(actual,relative)
 return cohort
