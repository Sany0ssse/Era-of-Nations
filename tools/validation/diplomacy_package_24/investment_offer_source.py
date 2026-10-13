"""Exact legacy pending-entry view plus independent live protocol24 inner proof.

This does not emulate current v2 pending entry. The separate investment_offer_active
suite executes that actual AST. No Path methods or global file APIs are replaced.
"""
from pathlib import Path
from copy import deepcopy
import hashlib,json,base64,runpy
HERE=Path(__file__).resolve().parent
PORT=HERE.parent/'investment_offer_active'
ADMISSION=runpy.run_path(str(HERE.parent/'ai_thinking_cost/source_admission.py'))
source_for_hash=ADMISSION['source_for_hash']
sha=lambda raw:hashlib.sha256(raw).hexdigest()
CATALOG_SHA = 'c29241df2d17a533fc89a87f3307338f3453ca619a95849bd91bf2570b1b2d6f'
INVERSE_SHA = '9cf9f61253736032c0f141f3a5ba25f42c41c7ab6bf0f505dc4af1087698d854'
PUBLIC_FILES = {'_model': 'c793a2880515bc36c4be7d734965270c99a304e33a44d88e8b9d4f8fb4061e24', 'test_projects': 'ef81aee51f8276cfac3c3f3407eea4eb981950715879ee7a18ea29fdda5f4756', 'test_comparisons': '4517256af21b60d4555e09a7b2c69cca2ad06b25bbf72155b522b12d99a32976', 'test_source': '53a83211bc5b4604c1735f9dad7e78637692b13bc94c1431920d9246ce2882cb'}
UNCHANGED_LOC = {'localisation/english/eon_investment_lifecycle_l_english.yml': 'dde67777b46f12b6e43eaabf0dff9e16c69416ac48e43b2e705161344ff195c7', 'localisation/russian/eon_investment_lifecycle_l_russian.yml': 'd8ba7d3e7e15ba5a120b0dee51fefe562c47f101d2b6b3e2da194768c0af41c4', 'events/00_Econ_events.txt': 'd28ae258e56b1d0e2c279c44ec676910a8e657fcc75d7ce400800f8b60e849b5'}

def finite_data():
 raw=(PORT/'catalog.json').read_bytes();assert sha(raw)==CATALOG_SHA,'Portable catalog drift'
 raw_inverse=(PORT/'full-inverse.json').read_bytes();assert sha(raw_inverse)==INVERSE_SHA,'Exact inverse catalog drift'
 catalog=json.loads(raw);rows=json.loads(raw_inverse)
 assert len(rows)==14 and len(catalog['source_after_sha256'])==14
 assert {r['path']:r['after_sha256'] for r in rows}==catalog['source_after_sha256']
 before={r['path']:base64.b64decode(r['before_b64'],validate=True) for r in rows if r['before_b64'] is not None}
 assert len(before)==6
 for rel,expected in catalog['canonical_before_sha256'].items():
  assert sha((PORT/'before'/rel).read_bytes())==expected,('Canonical whole before bytes',rel)
 for rel,raw in before.items():assert raw==(PORT/'before'/rel).read_bytes()
 return catalog,rows,before

def verify_cohort(root,read=None):
 root=Path(root).resolve();read=read or (lambda p:p.read_bytes());catalog,rows,before=finite_data()
 observed={rel:read(root/rel) if (root/rel).is_file() else None for rel in catalog['source_after_sha256']}
 old=all(observed[rel]==raw for rel,raw in before.items()) and all(observed[rel] is None for rel in observed if rel not in before)
 # Historical BEFORE6 is exact raw and must never enter the AI2/3 whitelist.
 if not old:ADMISSION['verify_owned_cohort'](root,read=read)
 after=not old and all(raw is not None and sha(source_for_hash(raw,rel))==catalog['source_after_sha256'][rel] for rel,raw in observed.items())
 assert after or old,'Reject foreign bytes or a mixed v2 source cohort'
 if after:
  for rel,prior in before.items():
   current=observed[rel]
   assert current.startswith(b'\xef\xbb\xbf')==prior.startswith(b'\xef\xbb\xbf')
   assert (b'\r\n' in current)==(b'\r\n' in prior) and current.endswith(b'\n')==prior.endswith(b'\n')
 expected=dict(catalog['required_source_sha256'])
 if old:
  for rel in catalog['source_after_sha256']:
   if rel in before:expected[rel]=sha(before[rel])
   else:expected.pop(rel)
 for rel,h in {**expected,**UNCHANGED_LOC}.items():
  assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
  assert sha(read(root/rel) if old else source_for_hash(read(root/rel),rel))==h,('Finite protected/source dependency drift',rel)
 return 'AFTER14' if after else 'BEFORE6_WITH_NEW8_ABSENT'

def legacy_source_bytes(root,relative):
 """Six exact v2 entry files project to their canonical whole before bytes."""
 catalog,rows,before=finite_data();raw=(Path(root)/relative).read_bytes()
 if relative in before:
  assert raw==before[relative] or sha(source_for_hash(raw,relative))==catalog['source_after_sha256'][relative],('No broad source normalization',relative)
  return before[relative]
 return raw

def live_protocol24_inner(root,parse,one):
 """All lifecycle helpers and the guarded executor's inner body stay exact."""
 catalog,rows,before=finite_data();path='common/scripted_effects/eon_investment_project_effects.txt'
 raw=(Path(root)/path).read_bytes();base=parse(before[path].decode('utf-8-sig'));current=parse(raw.decode('utf-8-sig'))
 bd={k:v for k,o,v in base};ad={k:v for k,o,v in current};assert bd.keys()==ad.keys()
 changed={'eon_investment_prepare_offer','eon_investment_prepare_scripted_offer','eon_investment_execute_offer'}
 preserved=[k for k in bd if k not in changed]
 assert all(ad[k]==bd[k] for k in preserved),'Live post-entry lifecycle/ROI helper changed'
 if raw!=before[path]:
  guarded=deepcopy(ad['eon_investment_execute_offer']);assert len(guarded)==1 and guarded[0][:2]==('if','=')
  inner=guarded[0][2];gate=('has_country_flag','=','eon_investment_offer_v2_bridge_in_progress')
  assert inner[0]==('limit','=',[gate]);inner=deepcopy(inner[1:])
  assert inner[1][0]=='if' and inner[1][2][0][0]=='limit'
  assert inner[1][2][0][2][0]==gate
  del inner[1][2][0][2][0]
  assert inner==bd['eon_investment_execute_offer'],'Guarded executor financial/project body changed'
  # Current daily/annex effects preserve every original effect in its original order.
  path='common/on_actions/eon_investment_lifecycle_on_actions.txt'
  b=parse(before[path].decode('utf-8-sig'));a=parse((Path(root)/path).read_text(encoding='utf-8-sig'))
  def strip(nodes):
   return [(k,o,strip(v) if isinstance(v,list) else v) for k,o,v in nodes if not k.startswith('eon_investment_offer_v2_')]
  assert strip(a)==b,'Original daily/annex effect ordering changed'
 return {'status':'UNCHANGED_LIVE_PROTOCOL24_INNER_SOURCE_PASS','unchanged_helper_count':len(preserved),'guarded_executor_inner_exact':True,'legacy_entry_projected':True,'current_v2_entry_proven':False,'native_acceptance':False}
