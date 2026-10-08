"""Source/reference boundaries for the new protocol and retired native IDs."""
from _support import *
from collections import Counter
import json,re,subprocess

BASE='f2832b6bfd980066163d0a69a6306169c992c5d7'
checks=Counter()
def check(ok,label):assert ok,label;checks[label]+=1
def old(path):return subprocess.run(['git','show',BASE+':'+path],cwd=ROOT,check=True,capture_output=True).stdout
def block(blob,name):
 match=re.search(rb'(?m)^\t'+name.encode()+rb' = \{',blob);assert match,name
 start=match.start();index=blob.index(b'{',start)+1;depth=1
 while depth:
  if blob[index:index+1]==b'{':depth+=1
  elif blob[index:index+1]==b'}':depth-=1
  index+=1
 return start,index,blob[start:index]
def scrub(blob):
 for name in ('propose_improved_trade_agreement','cancel_trade_agreement','propose_mutual_investment_treaty','cancel_mutual_investment_treaty'):
  start,end,body=block(blob,name);blob=blob[:start]+b'\t'+name.encode()+b' = { RETIRED_ISLAND }'+blob[end:]
 return blob

def main():
 core='\n'.join((ROOT/path).read_text(encoding='utf-8-sig') for path in FILES[:2])
 temp_names=set(re.findall(r'\bset_temp_variable\s*=\s*\{\s*(\w+)\s*=',core))
 for scope,name in re.findall(r'\b(PREV|ROOT|FROM|THIS)\.(eon_framework_negotiation_\w+)\b',core):
  check(name not in temp_names,'explicit country prefixes never read execution temporaries')
 check(bool(temp_names),'native temporary guard inspected actual source definitions')
 check(not re.search(r'\b(?:PREV|ROOT|FROM|THIS)\.(?:'+ '|'.join(map(re.escape,sorted(temp_names))) +r')\b',core),'all native10 unreadable scoped temporary references removed')
 path=FILES[9];current=(ROOT/path).read_bytes();baseline=old(path)
 check(scrub(current)==scrub(baseline),'exact bytes outside four legacy islands')
 check(current.startswith(b'\xef\xbb\xbf')==baseline.startswith(b'\xef\xbb\xbf'),'legacy BOM retained')
 check(current.count(b'\r\n')==0 and baseline.count(b'\r\n')==0,'legacy LF retained')
 for path in FILES[10:12]:check((ROOT/path).read_bytes()==old(path),'existing pair helpers unchanged')
 for family,name in [('trade','propose_improved_trade_agreement'),('investment','propose_mutual_investment_treaty')]:
  body=OLD[name];helper='eon_trade_treaty_finish_response' if family=='trade' else 'eon_investment_treaty_finish_response'
  for field in ('allowed','visible','selectable','can_be_sent','can_be_accepted'):check(one(body,field)==[('always','=','no')],'retired proposal cannot send or accept')
  for callback in ('complete_effect','reject_effect'):check(one(body,callback)==[(helper,'=','yes')],'legacy callbacks drain only their old type')
  check(one(body,'on_sent_effect')==[],'retired send callback cannot create a new request')
  action=ACTIONS['eon_propose_'+family+'_framework'];check(one(action,'requires_acceptance')=='no','new identities have no native acceptance queue')
  check(one(action,'cost')=='0','native action cannot charge twice')
  old_action=next(v for k,o,v in one(parse(baseline.decode('utf-8-sig')),'scripted_diplomatic_actions') if k==name)
  check(one(action,'ai_desire')==one(old_action,'ai_desire'),'native sender desire retained with original ROOT frame')
 for family,name in [('trade','cancel_trade_agreement'),('investment','cancel_mutual_investment_treaty')]:
  body=OLD[name];helper='eon_trade_treaty_finish_response' if family=='trade' else 'eon_investment_treaty_finish_response'
  for field in ('allowed','visible','selectable','can_be_sent'):check(one(body,field)==[('always','=','no')],'retired cancellation hidden')
  check(one(body,'complete_effect')==[(helper,'=','yes')],'retired cancellation cannot erase a new agreement')
 ids=[]
 for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
  definitions=parse(path.read_text(encoding='utf-8-sig'))
  for key,operator,body in definitions:
   if key=='scripted_diplomatic_actions':ids.extend(k for k,o,v in body)
 check(len(ids)==len(set(ids)),'all native action IDs unique')
 for name in ('eon_propose_trade_framework','eon_propose_investment_framework','propose_improved_trade_agreement','propose_mutual_investment_treaty','cancel_trade_agreement','cancel_mutual_investment_treaty'):
  check(ids.count(name)==1,'new and retired identities remain disjoint and singular')

 locales=[]
 for lang in ('english','russian'):
  path=ROOT/f'localisation/{lang}/{P}l_{lang}.yml';blob=path.read_bytes();text=blob.decode('utf-8-sig')
  check(blob.startswith(b'\xef\xbb\xbf'),'locale BOM')
  keys=re.findall(r'^ ([\w.]+):0 "[^"\r\n]*"\r?$',text,re.M)
  check(len(keys)==len(set(keys)),'locale keys unique')
  check(text.splitlines()[0]=='l_'+lang+':','locale language header')
  locales.append(set(keys))
 check(locales[0]==locales[1],'EN/RU keys identical')
 required={P+'category',P+'notice_ack'}
 for name in DECISIONS:required|={name,name+'_desc'}
 for family in ('trade','investment'):required|={'eon_propose_'+family+'_framework','eon_propose_'+family+'_framework_desc',P+family+'_propose_desc',P+family+'_review_info_tt',P+family+'_status_info_tt'}
 for ordinal in (1,2,3):required|={P+f'notice.{ordinal}.t',P+f'notice.{ordinal}.d'}
 check(required<=locales[0],'all actual decisions, actions, events and tooltip references localised')
 for path in [*FILES[:9],FILES[12]]:
  blob=(ROOT/path).read_bytes();check(blob.count(b'\n')==blob.count(b'\r\n'),'new game CRLF complete')
  if not path.endswith('.yml'):check(not blob.startswith(b'\xef\xbb\xbf'),'new text format consistent')
  check(not blob.endswith(b'\r\n\r\n'),'no surplus EOF whitespace')
  if not path.endswith('.yml'):parse(blob.decode('utf-8-sig'));checks['every new source parses']+=1
 for path in [*FILES[:9],FILES[12]]:
  if path.endswith('.yml'):continue
  text=(ROOT/path).read_text(encoding='utf-8-sig')
  check(not re.search(r'\bROOT\s*=\s*\{',text) or path==FILES[2] or path==FILES[5],'pair core is independent of ROOT')
  for reference in re.findall(r'\b('+P+r'\w+)\s*=\s*yes\b',text):
   check(reference in TRIGGERS or reference in EFFECTS,'custom game helper resolves')
 for family in ('trade','investment'):
  F=P+family+'_'
  check(one(EFFECTS[F+'send'],'if')[0][0]=='limit','submission final guard exists')
  text=str(EFFECTS[F+'clear_local']);check(F+'epoch@PREV' not in text,'request clearing never resets serial')
  text=str(EFFECTS[F+'remove_side']);
  for forbidden in ('treasury','int_investments','energy_contracts','project_array','goods_deliveries'):
   check(forbidden not in text,'ending standing access does not cancel concrete obligations')
 # Notices are informational; all commitments remain guarded targeted decisions.
 for name,operator,body in parse((ROOT/FILES[6]).read_text(encoding='utf-8-sig')):
  if name=='country_event':
   option=one(body,'option');check({k for k,o,v in option}=={'name','ai_chance'},'notice options have no contractual effects')
 for name,body in DECISIONS.items():
  complete=one(body,'complete_effect');check(complete[0][0]=='FROM' and complete[0][2][0][0]=='PREV','actual decision re-enters owner with partner PREV')
  owner=complete[0][2][0][2];check(owner[0][0]=='if','forced decision completion has its own final guard')
 for name,operator,body in parse((ROOT/FILES[12]).read_text(encoding='utf-8-sig')):
  check(name=='defined_text','only documented dynamic localisation definitions')
  for name,operator,branch in body:
   if name=='text':check(one(branch,'localization_key') in locales[0],'every dynamic status branch localised')

 print(json.dumps({'package':28,'source_assertions':sum(checks.values()),'groups':dict(checks),'all_passed':True,
  'source_sha256':hashes(),'native_action_ids':len(ids),'native_campaign_proven':False,'multiplayer_proven':False}))

if __name__=='__main__':main()
