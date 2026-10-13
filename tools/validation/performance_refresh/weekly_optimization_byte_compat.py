"""Exact weekly byte projections for historical guards; never execute legacy behavior."""
from pathlib import Path
import hashlib,json
CATALOG_SHA256='b504b4cdf793f6ebbc9ec1a06702286dbf597db81cd2867b8a859d06842081f4'
_raw=Path(__file__).with_name('_weekly_optimization_source_islands.json').read_bytes()
assert hashlib.sha256(_raw).hexdigest()==CATALOG_SHA256,'Exact weekly island catalog required'
CATALOG=json.loads(_raw)
assert CATALOG['version']==1
MONEY=CATALOG['money_path']; MISSILES=CATALOG['missiles_path']
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def _bytes(raw):
 assert isinstance(raw,(bytes,str)),'Bytes or UTF-8 text required'
 return raw.encode('utf-8') if isinstance(raw,str) else raw
def _return(original,changed):return changed.decode('utf-8') if isinstance(original,str) else changed
def restore_tax_membership_guard(relative,raw):
 if relative!=MONEY:return raw
 before,after,lead,tail=[bytes.fromhex(CATALOG[k]) for k in ['tax_before_hex','tax_after_hex','tax_lead_hex','tax_tail_hex']]
 data=_bytes(raw)
 assert len(before)==263 and len(after)==411
 assert data.count(b'calculate_tax_gain = {')==1,'One tax helper definition required'
 assert data.count(lead)==data.count(tail)==1,'Unique tax boundary anchors required'
 if data.count(lead+before+tail)==1:
  assert data.count(before)==1 and data.count(after)==0,'Exact one old tax branch'
  return raw
 assert data.count(lead+after+tail)==1 and data.count(after)==1 and data.count(before)==0,'Exact one reviewed empty-array guard'
 changed=data.replace(lead+after+tail,lead+before+tail,1)
 assert changed.replace(lead+before+tail,lead+after+tail,1)==data,'Tax island full-byte inverse'
 return _return(raw,changed)
def certify_weekly_money_source(raw):
 data=_bytes(raw);digest=sha(data)
 assert digest in CATALOG['money_sources'],'Foreign whole money bytes rejected'
 changed=_bytes(restore_tax_membership_guard(MONEY,data))
 assert sha(changed)==CATALOG['money_sources'][digest],'Tax inverse must reach exact registered current money'
 return {'source_sha256':digest,'restored_sha256':sha(changed),'native_behavior_proven':False}
def restore_spy_first_refresh(relative,raw):
 if relative!=MISSILES:return raw
 data=_bytes(raw);old,new,deleted=[bytes.fromhex(CATALOG[k]) for k in ['spy_before_helper_hex','spy_after_helper_hex','spy_deleted_hex']]
 assert len(deleted)==30 and old.count(deleted)==2 and new.count(deleted)==1
 assert data.count(b'update_SPY_system_stats = {')==1,'One SPY helper definition required'
 if data.count(old)==1:
  assert data.count(new)==0,'Exactly one original SPY helper'
  return raw
 assert data.count(new)==1 and data.count(old)==0,'Exact reviewed SPY helper required'
 changed=data.replace(new,old,1)
 assert changed.replace(old,new,1)==data,'SPY inverse changes only reviewed helper island'
 return _return(raw,changed)
def certify_weekly_spy_source(raw):
 data=_bytes(raw);digest=sha(data)
 assert digest in CATALOG['spy_sources'],'Foreign whole missiles bytes rejected'
 changed=_bytes(restore_spy_first_refresh(MISSILES,data))
 assert sha(changed)==CATALOG['spy_sources'][digest],'Exact SPY current source preimage required'
 return {'source_sha256':digest,'restored_sha256':sha(changed),'native_behavior_proven':False}
def restore_weekly_validator_bytes(relative,raw):
 if relative!=CATALOG['validator_path']:return raw
 data=_bytes(raw);digest=sha(data)
 if digest==CATALOG['validator_before_sha256']:return raw
 assert digest==CATALOG['validator_after_sha256'],'Unknown validator bytes rejected'
 one,two=[bytes.fromhex(CATALOG[k]) for k in ['validator_import_hex','validator_call_hex']]
 assert data.count(one)==data.count(two)==1,'One exact SPY validator hook required'
 changed=data.replace(one,b'',1).replace(two,b'',1)
 assert sha(changed)==CATALOG['validator_before_sha256'],'Whole unchanged historical validator required'
 return _return(raw,changed)
