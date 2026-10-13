"""Portable checks for six zero-weight targeted decision filters.

Run with Python3 from an installed mod. Environment overrides exist only for
source-only author testing; they do not launch the game or rewrite the mod.
"""
from pathlib import Path
from itertools import product
import json, os, re, unittest
from audit import SOURCE, TRIGGERS, CATEGORY, IDS, PREDICATES, parse, fields, shape, decisions, pure, sha, certify

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('EON_AI_FRAMEWORK_MOD_ROOT',HERE.parents[2])).resolve()
SOURCE_PATH=Path(os.environ.get('EON_AI_FRAMEWORK_SOURCE_PATH',ROOT/SOURCE)).resolve()
BIND=json.loads((HERE/'bindings.json').read_text(encoding='utf-8'))

def normalize(data):
 digest=sha(data)
 if digest==BIND['before_sha256']:
  before=data;after=data
  for p in sorted(BIND['patches'],key=lambda p:p['before_start'],reverse=True):
   assert after[p['before_start']:p['before_end']]==bytes.fromhex(p['before_hex'])
   after=after[:p['before_start']]+bytes.fromhex(p['after_hex'])+after[p['before_end']:]
 elif digest==BIND['after_sha256']:
  after=data;before=data
  for p in sorted(BIND['patches'],key=lambda p:p['after_start'],reverse=True):
   assert before[p['after_start']:p['after_end']]==bytes.fromhex(p['after_hex'])
   before=before[:p['after_start']]+bytes.fromhex(p['before_hex'])+before[p['after_end']:]
 else:raise ValueError('unknown whole-source cohort')
 assert sha(before)==BIND['before_sha256'] and sha(after)==BIND['after_sha256']
 return before,after

def actor_root(nodes,exists,ai):
 assert all(n['op']=='=' and n['key'] in ('exists','is_ai') for n in nodes)
 return all({'exists':exists,'is_ai':ai}[n['key']]==(n['value']=='yes') for n in nodes)

class Frame:
 def __init__(self,this='A',prev=None,root='A',from_='B'):
  self.this,self.prev,self.root,self.from_=this,prev,root,from_
 def switch(self,scope):
  country={'THIS':self.this,'PREV':self.prev,'ROOT':self.root,'FROM':self.from_}[scope]
  assert country is not None
  return Frame(country,self.this,self.root,self.from_)

def predicate(nodes,world,frame,registry):
 """Restricted source-query model with actual THIS/PREV/ROOT/FROM reads."""
 def country(scope):return {'THIS':frame.this,'PREV':frame.prev,'ROOT':frame.root,'FROM':frame.from_}[scope]
 def value(token):
  if token in ('THIS','PREV','ROOT','FROM'):return country(token)
  try:return float(token)
  except ValueError:pass
  if '.' in token and token.split('.',1)[0] in ('THIS','PREV','ROOT','FROM'):
   who,name=token.split('.',1);who=country(who)
  else:who,name=frame.this,token
  name=re.sub(r'@(THIS|PREV|ROOT|FROM)\b',lambda m:'@'+str(country(m[1])),name)
  return world[who]['vars'].get(name,0)
 def one(n):
  k,op,v=n['key'],n['op'],n['value'];c=world[frame.this]
  if k in registry:
   got=predicate(registry[k]['value'],world,frame,registry);return got if v=='yes' else not got
  if k in ('THIS','PREV','ROOT','FROM'):return predicate(v,world,frame.switch(k),registry)
  if k in ('AND','OR','NOT'):
   checks=[one(x) for x in v]
   return all(checks) if k=='AND' else (any(checks) if k=='OR' else not all(checks))
  if k=='exists':return c['exists']==(v=='yes')
  if k in ('tag','original_tag'):return c[k]==(country(v) if v in ('THIS','PREV','ROOT','FROM') else v)
  if k=='has_country_flag':
   name=re.sub(r'@(THIS|PREV|ROOT|FROM)\b',lambda m:'@'+str(country(m[1])),v)
   return name in c['flags']
  if k=='has_country_leader':return c['leader']==fields(v)['name']['value'].strip('"')
  if k=='has_political_power':return {'<':c['pp']<float(v),'=':c['pp']==float(v)}[op]
  if k=='check_variable':
   if len(v)==1:
    p=v[0];a,b=value(p['key']),value(p['value']);compare=p['op']
   else:
    args=fields(v);a,b=value(args['var']['value']),value(args['value']['value']);compare={'equals':'=','greater_than_or_equals':'>='}[args['compare']['value']]
   return {'=':a==b,'>':a>b,'<':a<b,'>=':a>=b,'<=':a<=b}[compare]
  if k=='always':return v=='yes'
  if k=='custom_trigger_tooltip':return predicate([x for x in v if x['key']!='tooltip'],world,frame,registry)
  if k=='if':raise ValueError('handled by ordered branch dispatcher')
  raise ValueError('unhandled primitive '+k)
 result=[];i=0
 while i<len(nodes):
  n=nodes[i];i+=1
  if n['key']=='if':
   branches=[n]
   while i<len(nodes) and nodes[i]['key'] in ('else_if','else'):branches.append(nodes[i]);i+=1
   got=True
   for b in branches:
    limit=[x for x in b['value'] if x['key']=='limit']
    if b['key']=='else' or predicate(limit[0]['value'],world,frame,registry):
     got=predicate([x for x in b['value'] if x['key']!='limit'],world,frame,registry);break
   result.append(got)
  else:result.append(one(n))
 return all(result)

class FilterChecks(unittest.TestCase):
 def test_exact_source_dependency_inverse_and_all_other_decisions(self):
  before,after=normalize(SOURCE_PATH.read_bytes())
  for p,digest in BIND['dependency_sha256'].items():self.assertEqual(sha((ROOT/p).read_bytes()),digest,p)
  proof=certify(before,after,(ROOT/TRIGGERS).read_bytes(),(ROOT/CATEGORY).read_bytes())
  self.assertEqual(len(proof['patches']),6);self.assertEqual(proof['nonzero_weight_decisions_unchanged'],14)
  for i in BIND['all_four_temp_counter_ids']:
   _,b=decisions(before);_,a=decisions(after);self.assertEqual(shape(b[i]['value']),shape(a[i]['value']))
  self.assertEqual(before.count(b'\r\n'),after.count(b'\r\n'));self.assertEqual(before.count(b'\n'),after.count(b'\n'))
  self.assertEqual(before.startswith(b'\xef\xbb\xbf'),after.startswith(b'\xef\xbb\xbf'))
  # Repository code only; ignored .local and Workshop trees are not scanned.
  pattern=re.compile((r'activate_(?:targeted_)?decision\s*=\s*(?:\{[^}]*\bdecision\s*=\s*)?(?:'+'|'.join(IDS)+r')\b').encode('ascii'),re.S)
  for area in ('common','events','history','interface'):
   for p in (ROOT/area).rglob('*'):
    if p.suffix not in ('.txt','.gui'):continue
    text=p.read_bytes()
    # Strip comments before inspecting actual literal activations.
    text=re.sub(rb'#[^\n]*',b'',text)
    self.assertIsNone(pattern.search(text),str(p))

 def test_36_actual_actor_root_cases_and_native_query_scope_model(self):
  before,after=normalize(SOURCE_PATH.read_bytes());_,b=decisions(before);_,a=decisions(after)
  contexts=((True,False,False),(True,False,True),(False,False,False),(True,True,False),(True,True,True),(False,True,False))
  for ident in IDS:
   old=fields(b[ident]['value']);new=fields(a[ident]['value'])
   for exists,ai,unlocked in contexts:
    self.assertEqual(actor_root(old['target_root_trigger']['value'],exists,ai),exists)
    self.assertEqual(actor_root(new['target_root_trigger']['value'],exists,ai),exists and not ai)
    if not ai:self.assertEqual(actor_root(old['target_root_trigger']['value'],exists,ai),actor_root(new['target_root_trigger']['value'],exists,ai))
   # 'unlocked' is intentionally absent from the actual root AST: a new proposal
   # does not impose a new human cache gate or condition beyond existing exists.
  reg=fields(parse((ROOT/TRIGGERS).read_text(encoding='utf-8-sig')))
  for kind,status,standing,pp,foreignroot in product(('trade','investment'),(0,1,2),(False,True),(74,75),(False,True)):
   world={x:{'exists':True,'tag':x,'original_tag':x,'leader':'Leader','vars':{},'flags':set(),'pp':pp} for x in ('A','B','C')}
   world['A']['vars']['eon_framework_negotiation_'+kind+'_status@B']=status
   # Deliberately different reverse and foreign-root values expose PREV mistakes.
   world['B']['vars']['eon_framework_negotiation_'+kind+'_status@A']=0
   world['C']['vars']['eon_framework_negotiation_'+kind+'_status@B']=99
   flag='trade_agreement@B' if kind=='trade' else 'mutual_investment_treaty_@B'
   if standing:world['A']['flags'].add(flag)
   f=Frame(root='C' if foreignroot else 'A')
   for action,expected in (('withdraw',status==1),('end_request',standing and status==0 and pp>=75),('status',status>0 or standing)):
    ident='eon_framework_negotiation_'+kind+'_'+action
    for field in ('visible','available'):
     observed=predicate(fields(b[ident]['value'])[field]['value'],world,f,reg)
     # Existing end-request visibility only requires a standing agreement;
     # its status/PP checks belong to availability and may grey the entry.
     field_expected=standing if action=='end_request' and field=='visible' else expected
     self.assertEqual(observed,field_expected,(ident,field,status,standing,pp,foreignroot))
     self.assertEqual(observed,predicate(fields(a[ident]['value'])[field]['value'],world,f,reg))

 def test_negative_cohorts_predicate_writes_and_foreign_scope(self):
  before,after=normalize(SOURCE_PATH.read_bytes());tr=(ROOT/TRIGGERS).read_bytes();cat=(ROOT/CATEGORY).read_bytes()
  for mutated in (before+b'\n# foreign\n',after+b'\n# foreign\n',after.replace(b'is_ai = no',b'is_ai = yes',1)):
   with self.assertRaises(ValueError):normalize(mutated)
  for token in (b'set_temp_variable = { x = 1 }',b'random = { chance = 1 always = yes }'):
   mutant=tr.replace(b'eon_framework_negotiation_trade_standing = {',b'eon_framework_negotiation_trade_standing = { '+token,1)
   with self.assertRaises(ValueError):certify(before,after,mutant,cat)
  for mutated in (after.replace(b'yes is_ai = no }',b'yes is_ai = yes }',1),after.replace(b'ai_will_do = { factor = 10 }',b'ai_will_do = { factor = 0 }',1)):
   with self.assertRaises((AssertionError,ValueError)):certify(before,mutated,tr,cat)
  reg=fields(parse(tr.decode('utf-8-sig')))
  _,b=decisions(before);block=fields(b[IDS[0]]['value'])['visible']['value']
  world={x:{'exists':True,'tag':x,'original_tag':x,'leader':'L','vars':{},'flags':set(),'pp':75} for x in ('A','B','C')}
  world['A']['vars']['eon_framework_negotiation_trade_status@B']=1
  self.assertTrue(predicate(block,world,Frame(root='C'),reg))
  mutant=parse('FROM = { ROOT = { check_variable = { eon_framework_negotiation_trade_status@PREV = 1 } } }')
  self.assertFalse(predicate(mutant,world,Frame(root='C'),reg))

if __name__=='__main__':unittest.main()
