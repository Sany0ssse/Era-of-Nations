"""Execute current package26 decision/trigger/effect AST; not an HOI4 campaign.

The strict adapter models country scopes, scoped keys, flags/deadlines and arrays.
Native10 temporaries are shared within one execution; scoped country reads resolve
only persistent variables. Unknown commands fail. This does not simulate physical
diplomats or native AI timing.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[3]
P='eon_diplomatic_relations_'
FILES=[
 'common/scripted_triggers/'+P+'triggers.txt',
 'common/scripted_effects/'+P+'effects.txt',
 'common/decisions/'+P+'decisions.txt',
 'common/decisions/categories/'+P+'categories.txt',
 'common/on_actions/'+P+'on_actions.txt',
 'events/'+P+'events.txt',
 *[f'localisation/{lang}/{P}l_{lang}.yml' for lang in ('english','russian')],
 'common/scripted_localisation/'+P+'scripted_localisation.txt',
 'history/general/'+P+'history.txt',
]
NATIVE=Path(r'D:\SteamLibrary\steamapps\common\Hearts of Iron IV')

def parse(text):
 tokens=re.findall(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|>=|<=|!=|=|>|<|[^\s{}=<>!]+',text.lstrip('\ufeff'))
 tokens=[t for t in tokens if not t.startswith('#')]
 index=0
 def block(nested=False):
  nonlocal index
  out=[]
  while index<len(tokens):
   if tokens[index]=='}':
    assert nested, 'Unexpected closing brace'
    index+=1;return out
   key=tokens[index];index+=1
   assert index<len(tokens) and tokens[index] in ('=','>','<','>=','<=','!='),(key,tokens[index:index+3])
   operator=tokens[index];index+=1
   assert index<len(tokens),'Missing value'
   if tokens[index]=='{':index+=1;value=block(True)
   else:value=tokens[index];index+=1
   out.append((key,operator,value))
  assert not nested,'Unclosed block'
  return out
 return block()

def definitions(path):return {k:v for k,o,v in parse((ROOT/path).read_text(encoding='utf-8-sig'))}
TRIGGERS=definitions(FILES[0]);EFFECTS=definitions(FILES[1])
politics=definitions('common/scripted_triggers/00_political_triggers.txt')
for key in ('emerging_hardline_shiite_are_in_power','emerging_moderate_shiite_are_in_power'):
 TRIGGERS[key]=politics[key]
DECISIONS={k:v for k,o,v in definitions(FILES[2])[P+'category']}
HOOKS={k:v for k,o,v in definitions(FILES[4])['on_actions']}
EVENTS={dict((k,v) for k,o,v in body)['id']:body for key,op,body in parse((ROOT/FILES[5]).read_text(encoding='utf-8-sig')) if key=='country_event'}
IDS={name:index+1 for index,name in enumerate(('A','B','C','D','PER','USA','F','G','H','I','J','K'))}
# Explicit defined peer tags required by the bounded legacy compatibility branches.
for name in ('GER', 'GRE', 'HEZ', 'IRQ', 'ISR', 'KUR', 'KUW', 'NKO', 'PER', 'SAU', 'TUR', 'USA'):IDS.setdefault(name,len(IDS)+1)
checks=Counter()

def one(nodes,key):
 values=[value for name,op,value in nodes if name==key]
 assert len(values)==1,(key,len(values))
 return values[0]

def state():
 countries={name:{'exists':True,'pp':100.,'variables':{'treasury':5.},'temps':{},'flags':set(),'expires':{},
  'arrays':{'ruling_party':[5]},'wars':set(),'opinions':{},'opinion_modifiers':set()} for name in IDS}
 # Actual inherited channels are seeded, not invented generic independence markers.
 for name,c in countries.items():
  peer='C' if name!='C' else 'D'
  c['flags'].update({'trade_agreement@'+peer,'mutual_investment_treaty_@'+peer,
   'eon_aid_reserved','eon_aid_outgoing','eon_advisers_pending','eon_consultation_reserved','eon_consultation_outgoing'})
  c['variables'].update({'eon_aid_partner':peer,'eon_aid_amount':7.,'eon_advisers_partner':peer,
   'eon_aid_escrow':7.,'signed_trade_agreements':1,'eon_consultation_partner':peer,'eon_consultation_topic':2})
  c['arrays'].update({'energy_contractors':[peer],'energy_contracts_ammount':[32],
   'energy_contracts_price':[0.12],'project_array':[IDS[peer],2,1]})
  c['opinion_modifiers'].add((peer,'historic_friends'))
 result={'countries':countries,'day':0,'events':[],'global_flags':set(),'execution_temps':{}}
 execute(parse((ROOT/FILES[-1]).read_text(encoding='utf-8-sig')),result,ctx())
 return result

def ctx(actor='A',peer='B'):return {'scope':actor,'prev':[], 'root':actor,'from':peer}
def switch(context,target):return context|{'scope':target,'prev':[context['scope'],*context['prev']]}
def country_ref(result,context,token):
 if token=='THIS':return context['scope']
 if token=='PREV':return context['prev'][0] if context['prev'] else None
 if token=='FROM':return context['from']
 if token=='ROOT':return context['root']
 if token in result['countries']:return token
 if token.startswith('var:'):return value(result,context,token[4:])
 raise AssertionError(('Unknown country ref',token,context))

def key(result,context,token):
 if '@' not in token:return token
 name,target=token.split('@',1)
 return name+'@'+str(country_ref(result,context,target))

def flag_key(result,context,token):
 # Native24: three-letter literal FLAG suffixes stay literal; variables use key().
 # Single-letter synthetic fixture aliases retain their explicit country binding.
 if '@' in token:
  name,target=token.split('@',1)
  if re.fullmatch(r'[A-Z]{3}',target):return name+'@literal:'+target
 return key(result,context,token)

def value(result,context,token):
 if token in ('yes','no'):return token=='yes'
 try:return float(token)
 except ValueError:pass
 if token.startswith('var:'):token=token[4:]
 if token.startswith('"'):return token[1:-1]
 if '^' in token:
  array,index=token.split('^',1)
  values=result['countries'][context['scope']]['arrays'].get(array,[])
  ordinal=int(value(result,context,index))
  return values[ordinal] if 0<=ordinal<len(values) else 0
 if '.' in token:
  scope,field=token.split('.',1)
  peer=country_ref(result,context,scope)
  if field=='id':return IDS[peer]
  # A country prefix never resolves a shared execution temporary.
  nested=switch(context,peer)
  return result['countries'][peer]['variables'].get(key(result,nested,field),0)
 if token in ('THIS','PREV','ROOT','FROM') or token in result['countries']:return country_ref(result,context,token)
 c=result['countries'][context['scope']];name=key(result,context,token)
 return result.get('execution_temps',{}).get(name,c['variables'].get(name,0))

def compare(left,operator,right):
 return {'=':lambda:left==right,'!=':lambda:left!=right,'>':lambda:left>right,
  '<':lambda:left<right,'>=':lambda:left>=right,'<=':lambda:left<=right}[operator]()

def hasflag(result,context,name):
 c=result['countries'][context['scope']];name=flag_key(result,context,name)
 return name in c['flags'] and (name not in c['expires'] or result['day']<c['expires'][name])

def condition(nodes,result,context):
 index=0
 while index<len(nodes):
  name,op,data=nodes[index];index+=1
  c=result['countries'][context['scope']]
  if name=='if':
   branches=[(name,data)]
   while index<len(nodes) and nodes[index][0] in ('else_if','else'):
    branches.append((nodes[index][0],nodes[index][2]));index+=1
   ready=True
   for kind,body in branches:
    if kind=='else' or condition(one(body,'limit'),result,context):
     ready=condition([n for n in body if n[0]!='limit'],result,context);break
  elif name=='OR':ready=any(condition([node],result,context) for node in data)
  elif name=='AND':ready=condition(data,result,context)
  elif name=='NOT':ready=not condition(data,result,context)
  elif name=='always':ready=value(result,context,data)
  elif name=='exists':ready=c['exists']==value(result,context,data)
  elif name=='tag':ready=context['scope']==country_ref(result,context,data)
  elif name=='has_war_with':ready=country_ref(result,context,data) in c['wars']
  elif name=='has_country_flag':ready=hasflag(result,context,data)
  elif name=='has_global_flag':ready=data in result['global_flags']
  elif name=='has_opinion_modifier':
   assert isinstance(data,str),'Native opinion modifier query accepts a scalar, without a pair target'
   ready=any(modifier==data for peer,modifier in c['opinion_modifiers'])
  elif name=='check_variable':
   if len(data)==1:
    var,comparison,wanted=data[0]
    assert comparison in ('=','>','<'),('Native shorthand has no inclusive operator',data)
   else:
    fields={k:v for k,o,v in data}
    assert set(fields)=={'var','value','compare'} and all(o=='=' for k,o,v in data),('Unsupported explicit variable comparison',data)
    var,wanted=fields['var'],fields['value']
    comparison={'equals':'=','not_equals':'!=','greater_than':'>','greater_than_or_equals':'>=',
     'less_than':'<','less_than_or_equals':'<='}[fields['compare']]
   ready=compare(value(result,context,var),comparison,value(result,context,wanted))
  elif name=='has_political_power':
   assert op in ('=','>','<'),'Native direct numeric triggers have no inclusive operator'
   ready=compare(c['pp'],op,value(result,context,data))
  elif name=='is_in_array':
   if len(data)==1:array,comparison,wanted=data[0];assert comparison=='='
   else:array=one(data,'array');wanted=one(data,'value')
   ready=value(result,context,wanted) in c['arrays'].get(array,[])
  elif name=='custom_trigger_tooltip':ready=condition([n for n in data if n[0]!='tooltip'],result,context)
  elif name=='set_temp_variable':execute([(name,op,data)],result,context);ready=True
  elif name in TRIGGERS:
   ready=condition(TRIGGERS[name],result,context)
   if data=='no':ready=not ready
   else:assert data=='yes'
  elif name in ('THIS','PREV','FROM','ROOT') or name in result['countries']:
   target=country_ref(result,context,name)
   ready=target is not None and condition(data,result,switch(context,target))
  else:raise AssertionError(('Unknown trigger',name,op,data,context))
  if not ready:return False
 return True

def execute(nodes,result,context):
 index=0
 while index<len(nodes):
  name,op,data=nodes[index];index+=1
  c=result['countries'][context['scope']]
  if name=='if':
   branches=[(name,data)]
   while index<len(nodes) and nodes[index][0] in ('else_if','else'):
    branches.append((nodes[index][0],nodes[index][2]));index+=1
   for kind,body in branches:
    if kind=='else' or condition(one(body,'limit'),result,context):execute([n for n in body if n[0]!='limit'],result,context);break
  elif name in ('set_variable','set_temp_variable','add_to_variable','subtract_from_variable'):
   assert len(data)==1,('Unexpected variable command',data)
   variable,operator,wanted=data[0];assert operator=='='
   field=key(result,context,variable);amount=value(result,context,wanted)
   if name=='set_temp_variable':result.setdefault('execution_temps',{})[field]=amount
   elif name=='set_variable':c['variables'][field]=amount
   else:c['variables'][field]=round(c['variables'].get(field,0)+amount*(1 if name=='add_to_variable' else -1),6)
  elif name=='clear_variable':c['variables'].pop(key(result,context,data),None)
  elif name=='clamp_variable':
   fields={k:v for k,o,v in data};field=key(result,context,fields['var']);amount=c['variables'].get(field,0)
   if 'min' in fields:amount=max(value(result,context,fields['min']),amount)
   if 'max' in fields:amount=min(value(result,context,fields['max']),amount)
   c['variables'][field]=amount
  elif name=='set_country_flag':
   flag=one(data,'flag') if isinstance(data,list) else data;field=flag_key(result,context,flag);c['flags'].add(field)
   if isinstance(data,list):c['expires'][field]=result['day']+value(result,context,one(data,'days'));assert one(data,'value')=='1'
   else:c['expires'].pop(field,None)
  elif name=='set_global_flag':result['global_flags'].add(data)
  elif name=='clr_country_flag':field=flag_key(result,context,data);c['flags'].discard(field);c['expires'].pop(field,None)
  elif name=='add_to_array':c['arrays'].setdefault(one(data,'array'),[]).append(value(result,context,one(data,'value')))
  elif name=='remove_from_array':
   fields={k:v for k,o,v in data};array=c['arrays'].get(fields['array'],[])
   if 'index' in fields:
    ordinal=int(value(result,context,fields['index']))
    if 0<=ordinal<len(array):array.pop(ordinal)
   else:
    wanted=value(result,context,fields['value'])
    if wanted in array:array.remove(wanted)
  elif name=='add_political_power':c['pp']+=value(result,context,data)
  elif name in ('add_opinion_modifier','remove_opinion_modifier','reverse_add_opinion_modifier'):
   target=country_ref(result,context,one(data,'target'));modifier=one(data,'modifier')
   if name=='reverse_add_opinion_modifier':result['countries'][target]['opinion_modifiers'].add((context['scope'],modifier))
   elif name=='add_opinion_modifier':c['opinion_modifiers'].add((target,modifier))
   else:c['opinion_modifiers'].discard((target,modifier))
  elif name=='for_each_scope_loop':
   array=one(data,'array')
   for peer in list(c['arrays'].get(array,[])):
    assert peer in result['countries'],('Invalid partner identity',peer)
    execute([n for n in data if n[0]!='array'],result,switch(context,peer))
  elif name=='for_each_loop':
   fields={k:v for k,o,v in data};array=fields['array']
   for ordinal,item in enumerate(list(c['arrays'].get(array,[]))):
    shared=result.setdefault('execution_temps',{})
    shared[fields.get('value','v')]=item;shared[fields.get('index','i')]=ordinal
    execute([n for n in data if n[0] not in ('array','value','index','break')],result,context)
    if fields.get('break') and value(result,context,fields['break']):break
  elif name=='country_event':result['events'].append({'id':one(data,'id'),'scope':context['scope'],'root':context['root'],'from':context['from']})
  elif name=='custom_effect_tooltip':pass
  elif name=='hidden_effect':execute(data,result,context)
  elif name in EFFECTS:assert data=='yes';execute(EFFECTS[name],result,context)
  elif name in ('THIS','PREV','FROM','ROOT') or name in result['countries']:
   target=country_ref(result,context,name)
   if target is not None:execute(data,result,switch(context,target))
  else:raise AssertionError(('Unknown effect',name,op,data,context))

def decision(result,name,actor='A',peer='B',force=False):
 result['execution_temps']={}
 body=DECISIONS[P+name];context=ctx(actor,peer)
 ready=all(condition(one(body,field),result,context) for field in ('allowed','target_root_trigger','target_trigger','visible','available'))
 if ready or force:
  result['execution_temps']={}
  execute(one(body,'complete_effect'),result,context)
 return ready

def hook(result,name,actor='A',peer='B'):
 result['execution_temps']={}
 execute(one(HOOKS[name],'effect'),result,ctx(actor,peer))
def var(result,field,actor='A',peer='B'):return result['countries'][actor]['variables'].get(P+field+'@'+peer,0)
def flag(result,field,actor='A',peer='B'):return hasflag(result,ctx(actor,peer)|{'prev':[peer]},P+field+'@PREV')
def unrelated(result):
 out=deepcopy(result['countries'])
 for c in out.values():
  c.pop('temps');c.pop('pp');c.pop('expires')
  c['flags']={f for f in c['flags'] if not f.startswith(P)}
  c['variables']={k:v for k,v in c['variables'].items() if not k.startswith(P) and k!='treasury'}
  c['arrays']={k:v for k,v in c['arrays'].items() if not k.startswith(P)}
  c['opinion_modifiers']={item for item in c['opinion_modifiers'] if item[1]!='no_diplomatic_ties'}
 return out
def stable(result):
 out=deepcopy(result);out.pop('events');out['execution_temps']={}
 for c in out['countries'].values():c['temps']={}
 return out

def rehydrate(result):
 # A real JSON round trip of the adapter's durable representation, without temps.
 # This is explicitly not a native .hoi4 save/load test.
 def encode(obj):
  if isinstance(obj,set):return {'__set__':[encode(v) for v in sorted(obj,key=repr)]}
  if isinstance(obj,tuple):return {'__tuple__':[encode(v) for v in obj]}
  if isinstance(obj,list):return [encode(v) for v in obj]
  if isinstance(obj,dict):return {k:encode(v) for k,v in obj.items()}
  return obj
 def decode(obj):
  if isinstance(obj,list):return [decode(v) for v in obj]
  if isinstance(obj,dict):
   if set(obj)=={'__set__'}:return {decode(v) for v in obj['__set__']}
   if set(obj)=={'__tuple__'}:return tuple(decode(v) for v in obj['__tuple__'])
   return {k:decode(v) for k,v in obj.items()}
  return obj
 durable=deepcopy(result);durable['execution_temps']={}
 for c in durable['countries'].values():c['temps']={}
 return decode(json.loads(json.dumps(encode(durable))))
def assert_(test,group):assert test,group;checks[group]+=1
def establish(result,actor='A',peer='B'):
 assert_(decision(result,'propose',actor,peer),'establish send');assert_(decision(result,'accept_relations',peer,actor),'establish consent')
def mission(result,actor='A',peer='B',level='ambassador'):
 assert_(decision(result,'mission_'+level,actor,peer),'mission send');assert_(decision(result,'accept_'+level,peer,actor),'mission consent')
def head(result,actor='A',peer='B'):
 assert_(decision(result,'propose_head',actor,peer),'head request');assert_(decision(result,'accept_head',peer,actor),'agrement')
 assert_(var(result,'active_head',actor,peer)==0,'agrement not credentials')
 assert_(decision(result,'credentials',actor,peer),'credentials notification')

def legacy_no_ties(result,actor,peer):
 # Use the actual forward Iran history effect and its immediately following
 # metadata island to represent a late national-policy change in these fixtures.
 history=(ROOT/'history/countries/PER - Iran.txt').read_text(encoding='utf-8-sig')
 start=re.search(r'add_opinion_modifier\s*=\s*\{\s*target\s*=\s*USA\s+modifier\s*=\s*no_diplomatic_ties\s*\}\s*hidden_effect\s*=\s*\{',history)
 assert start,'Current national no-ties effect has no exact pair receipt'
 end=start.end();depth=1
 while depth:
  assert end<len(history),'Unclosed history metadata island'
  depth+=(history[end]=='{')-(history[end]=='}');end+=1
 prototype=parse(history[start.start():end])
 def remap(nodes):
  return [(peer if name=='USA' else name,op,remap(data) if isinstance(data,list) else peer if data=='USA' else data.replace('@USA','@'+peer)) for name,op,data in nodes]
 execute(remap(prototype),result,ctx(actor,peer))

def main():
 # Execute full current source paths rather than a parallel hand-written state machine.
 r=state();before=unrelated(r);establish(r);mission(r);head(r)
 assert_(flag(r,'established','A','B') and flag(r,'established','B','A'),'mutual consent state')
 assert_(var(r,'mission_level','A','B')==2 and var(r,'mission_level','B','A')==0,'directed mission independent')
 assert_(var(r,'active_head')==1 and var(r,'approved_head')==0,'credentials consume appointment')
 assert_(r['countries']['A']['variables']['treasury']==4.98 and r['countries']['A']['pp']==90,'only sending budget')
 assert_(unrelated(r)==before,'real legacy channels preserved full opening')
 for name,actor,peer in [('accept_relations','B','A'),('accept_ambassador','B','A'),('accept_head','B','A'),('credentials','A','B')]:
  previous=stable(r);decision(r,name,actor,peer,True);assert_(stable(r)==previous,'one use '+name)
 # Notice windows, including very old notices, can never authorize a later record.
 previous=stable(r)
 for event in EVENTS.values():
  options=[v for k,o,v in event if k=='option']
  for option in options:execute([n for n in option if n[0] not in ('name','ai_chance')],r,ctx('B','A'))
 assert_(stable(r)==previous,'all notice options inert')
 assert_(decision(r,'propose_head'),'replacement candidate');oldserial=var(r,'out_head')
 decision(r,'decline','B','A');assert_(var(r,'active_head')==1,'rejection retains active head')
 assert_(decision(r,'propose_head'),'reapply after decline');assert_(var(r,'out_head')>oldserial,'fresh abstract serial')
 previous=stable(r);decision(r,'accept_relations','B','A',True);assert_(stable(r)==previous,'wrong kind decision cannot accept head')
 decision(r,'accept_head','B','A');decision(r,'credentials')
 assert_(var(r,'active_head')==3 and flag(r,'departure_outstanding'),'head replacement departure duty')
 # Recall, PNG, closing and severance preserve real unrelated contracts exactly.
 for operation,actor,peer in [('recall','A','B'),('persona_non_grata','B','A'),('close','A','B'),('close_host','B','A'),('break','A','B')]:
  x=state();establish(x);mission(x);head(x);before=unrelated(x)
  assert_(decision(x,operation,actor,peer),'current '+operation)
  assert_(unrelated(x)==before,'legacy state equal after '+operation)
  assert_(flag(x,'departure_outstanding'),'departure outstanding '+operation)
  x['day']=1000;hook(x,'on_daily');assert_(flag(x,'departure_outstanding'),'no timer falsely proves departure '+operation)
  assert_(not decision(x,'report_departure'),'report needs host acknowledgement')
  assert_(decision(x,'exit_facilities','B','A'),'host facilities acknowledgement')
  assert_(flag(x,'departure_outstanding') and var(x,'departure_record')==2,'host acknowledgement not physical departure')
  assert_(decision(x,'report_departure'),'sending report');assert_(not flag(x,'departure_outstanding') and var(x,'departure_record')==3,'administrative report completion')
  if operation in ('close','close_host','break'):assert_(flag(x,'protected_closed'),'premises protection retained')
 # Bilateral rupture, both directed missions, restoration, other partners.
 x=state();establish(x);establish(x,'A','C');mission(x);head(x);mission(x,'B','A');head(x,'B','A');mission(x,'A','C','charge')
 peerC=deepcopy(x['countries']['C']);cmission=var(x,'mission_level','A','C');decision(x,'break')
 assert_(var(x,'mission_level')==0 and var(x,'mission_level','B','A')==0,'rupture closes both directions')
 assert_(stable({'countries':{'C':x['countries']['C']},'events':[]})==stable({'countries':{'C':peerC},'events':[]}) and var(x,'mission_level','A','C')==cmission,'third-country diplomacy unchanged')
 assert_(flag(x,'broken') and flag(x,'broken','B','A'),'reciprocal rupture')
 establish(x);assert_(not flag(x,'broken') and not flag(x,'broken','B','A'),'restoration consent')
 assert_(var(x,'mission_level')==0 and flag(x,'protected_closed'),'restoration does not respawn embassy')
 mission(x);head(x);assert_(var(x,'active_head')>1,'restoration new appointment')
 # Formal class changes require recipient consent. Recall is an interim downgrade.
 x=state();mission(x);head(x);assert_(decision(x,'mission_charge'),'class change proposal')
 assert_(var(x,'mission_level')==2,'old class before consent');decision(x,'accept_charge','B','A')
 assert_(var(x,'mission_level')==1 and var(x,'active_head')==0,'formal class changed on assent')
 head(x);decision(x,'persona_non_grata','B','A');assert_(decision(x,'propose_head'),'new candidate after PNG');decision(x,'withdraw')
 assert_(decision(x,'propose_head'),'new candidate after withdrawal')
 # Approved head and class must match the host's current agrément witness.
 for alteration in ('host_head','host_level','sender_level','agrement_revoked','war','legacy_break'):
  x=state();mission(x);decision(x,'propose_head');decision(x,'accept_head','B','A')
  if alteration=='host_head':x['countries']['B']['variables'][P+'host_approved_head@A']=999
  elif alteration=='host_level':x['countries']['B']['variables'][P+'host_approved_level@A']=1
  elif alteration=='sender_level':x['countries']['A']['variables'][P+'mission_level@B']=1
  elif alteration=='agrement_revoked':x['countries']['A']['flags'].discard(P+'agrement@B')
  elif alteration=='war':x['countries']['A']['wars'].add('B');x['countries']['B']['wars'].add('A')
  else:legacy_no_ties(x,'B','A')
  previous=stable(x);assert_(not decision(x,'credentials'),'credentials blocked '+alteration)
  decision(x,'credentials',force=True);assert_(stable(x)==previous,'credentials forced stale inert '+alteration)
 x=state();mission(x);decision(x,'propose_head');decision(x,'accept_head','B','A')
 decision(x,'mission_charge');decision(x,'accept_charge','B','A')
 assert_(not flag(x,'agrement') and var(x,'host_approved_head','B','A')==0 and var(x,'approved_head')==0,'class change invalidates prior agrément')
 assert_(not decision(x,'credentials'),'old-class approved head cannot activate');head(x)
 # PNG targets the concrete active person or the separately approved candidate.
 x=state();mission(x);head(x);decision(x,'propose_head');decision(x,'accept_head','B','A')
 before=unrelated(x);approved=var(x,'approved_head');level=var(x,'approved_level');witness=var(x,'host_approved_head','B','A')
 assert_(decision(x,'persona_non_grata','B','A'),'PNG active with approved replacement')
 assert_(var(x,'active_head')==0 and var(x,'approved_head')==approved and var(x,'approved_level')==level,'active PNG preserves distinct replacement')
 assert_(flag(x,'agrement') and var(x,'host_approved_head','B','A')==witness,'active PNG preserves replacement agrément witness')
 assert_(var(x,'current_departure_head')==1 and var(x,'departure_count')==1,'active PNG departure only old head')
 previous=stable(x);assert_(not decision(x,'persona_non_grata','B','A'),'active PNG no active replay');decision(x,'persona_non_grata','B','A',True)
 assert_(stable(x)==previous,'active PNG forced replay cannot discard replacement')
 assert_(decision(x,'credentials') and var(x,'active_head')==approved,'replacement remains activatable after active PNG')
 assert_(unrelated(x)==before,'active PNG replacement independent actual channels')
 x=state();mission(x);head(x);decision(x,'propose_head');decision(x,'accept_head','B','A')
 before=unrelated(x);old=var(x,'active_head');approved=var(x,'approved_head')
 assert_(decision(x,'persona_non_grata_approved','B','A'),'PNG approved with active head')
 assert_(var(x,'active_head')==old and var(x,'approved_head')==0 and not flag(x,'agrement'),'approved PNG preserves distinct active head')
 assert_(var(x,'host_approved_head','B','A')==0 and not flag(x,'departure_outstanding') and var(x,'departure_count')==0,'approved PNG clears witness without invented arrival')
 previous=stable(x);assert_(not decision(x,'persona_non_grata_approved','B','A'),'approved PNG no candidate replay')
 decision(x,'persona_non_grata_approved','B','A',True);assert_(stable(x)==previous,'approved PNG forced replay inert')
 assert_(not decision(x,'credentials'),'rejected approved appointment cannot activate')
 decision(x,'propose_head');assert_(var(x,'out_head')>approved,'new serial after approved PNG')
 assert_(unrelated(x)==before,'approved PNG independent actual channels')
 # A stale host approval cannot reject a different current candidate.
 x=state();mission(x);head(x);decision(x,'propose_head');decision(x,'accept_head','B','A')
 x['countries']['B']['variables'][P+'host_approved_head@A']=1000
 previous=stable(x);assert_(not decision(x,'persona_non_grata_approved','B','A'),'approved PNG matched current serial')
 decision(x,'persona_non_grata_approved','B','A',True);assert_(stable(x)==previous,'approved PNG mismatched serial forced inert')
 # Repeated recalls and appointments retain each unfinished departure in order.
 x=state();mission(x);head(x);decision(x,'recall');decision(x,'exit_facilities','B','A')
 original=var(x,'current_departure');head(x);newhead=var(x,'active_head');decision(x,'recall')
 assert_(var(x,'departure_count')==2 and var(x,'current_departure')==original,'repeat recall keeps first departure')
 assert_(flag(x,'exit_facilities_ack') and var(x,'exit_ack_record')==original,'second recall preserves first acknowledgement')
 assert_(var(x,'current_departure_head')==1 and newhead==2,'distinct appointment serials before old exit')
 before=unrelated(x);x=rehydrate(x);assert_(decision(x,'report_departure'),'rehydrated old departure report')
 assert_(var(x,'departure_count')==1 and var(x,'current_departure')>original and var(x,'current_departure_head')==newhead,'queue advances to correct second head')
 assert_(not flag(x,'exit_facilities_ack') and not decision(x,'report_departure'),'old acknowledgement cannot clear next departure')
 previous=stable(x);decision(x,'report_departure',force=True);assert_(stable(x)==previous,'forced report before next acknowledgement inert')
 decision(x,'exit_facilities','B','A');decision(x,'report_departure')
 assert_(var(x,'departure_count')==0 and not flag(x,'departure_outstanding'),'all two recorded departures completed')
 assert_(x['countries']['A']['arrays'][P+'reported_departures']==[original,original+1],'completion history uses departure IDs')
 assert_(unrelated(x)==before,'departure queue preserves actual independent channels')
 # Interleaved third-country duties, PNG and rupture cannot erase or misalign arrays.
 x=state();mission(x);head(x);mission(x,'A','C','charge');head(x,'A','C')
 decision(x,'recall');decision(x,'recall','A','C');head(x);decision(x,'persona_non_grata','B','A')
 rejectedhead=x['countries']['A']['variables'][P+'head_counter'];head(x)
 assert_(var(x,'active_head')>rejectedhead,'PNG appointment serial never reused')
 bcount=var(x,'departure_count');ccurrent=var(x,'current_departure','A','C');cack=flag(x,'exit_facilities_ack','A','C')
 decision(x,'break');establish(x);assert_(var(x,'departure_count')==bcount+1,'rupture appends rather than erases duties')
 decision(x,'exit_facilities','B','A');decision(x,'report_departure')
 assert_(var(x,'current_departure','A','C')==ccurrent and flag(x,'exit_facilities_ack','A','C')==cack,'report does not shift third-country duty state')
 arrays=x['countries']['A']['arrays'];lengths=[len(arrays[P+field]) for field in ('departure_partners','departure_records','departure_heads')]
 assert_(len(set(lengths))==1,'departure parallel arrays stay aligned')
 for peer in ('B','C'):
  while flag(x,'departure_outstanding','A',peer):
   assert_(decision(x,'exit_facilities',peer,'A'),'each remaining record requires current host acknowledgement')
   assert_(decision(x,'report_departure','A',peer),'each current record can be reported separately')
 assert_(all(not arrays[P+field] for field in ('departure_partners','departure_records','departure_heads')),'all interleaved records removed without orphans')
 # Current identity, changed policy, stale budget/capacity and deadline.
 for alteration in ('war','recipient_gone','sender_gone','no_ties','funds','same_class','pp','fractional_pp','deadline','mismatched_level','mismatched_head'):
  x=state();decision(x,'mission_ambassador');before=stable(x)
  if alteration=='war':x['countries']['A']['wars'].add('B');x['countries']['B']['wars'].add('A')
  elif alteration=='recipient_gone':x['countries']['B']['exists']=False
  elif alteration=='sender_gone':x['countries']['A']['exists']=False
  elif alteration=='no_ties':legacy_no_ties(x,'B','A')
  elif alteration=='funds':x['countries']['A']['variables']['treasury']=0.01
  elif alteration=='same_class':x['countries']['A']['variables'][P+'mission_level@B']=2
  elif alteration=='pp':x['countries']['A']['pp']=0
  elif alteration=='fractional_pp':x['countries']['A']['pp']=9.5
  elif alteration=='deadline':x['day']=30
  elif alteration=='mismatched_level':x['countries']['B']['variables'][P+'in_level@A']=1
  else:x['countries']['B']['variables'][P+'in_head@A']=100
  no_mutation=stable(x);assert_(not decision(x,'accept_ambassador','B','A'),'unavailable '+alteration)
  decision(x,'accept_ambassador','B','A',True);assert_(stable(x)==no_mutation,'late forced click inert '+alteration)
 # Unknown legacy state is not absence; explicit no_ties remains authoritative.
 x=state();assert_(decision(x,'mission_charge'),'unregistered legacy pair mission offer allowed');decision(x,'withdraw')
 legacy_no_ties(x,'A','B')
 assert_(not decision(x,'mission_charge'),'legacy rupture prevents mission');establish(x)
 assert_(('B','no_diplomatic_ties') not in x['countries']['A']['opinion_modifiers'],'only agreed legacy no ties removed')
 # National policy definitions are actual inherited source, not fixture hardcoded approvals.
 for party in (8,9):
  x=state();x['countries']['PER']['arrays']['ruling_party']=[party]
  assert_(not decision(x,'propose','PER','USA'),'national Iran party '+str(party))
  x=state();decision(x,'propose','PER','USA');x['countries']['PER']['arrays']['ruling_party']=[party]
  previous=stable(x);assert_(not decision(x,'accept_relations','USA','PER'),'changed national policy before assent '+str(party))
  decision(x,'accept_relations','USA','PER',True);assert_(stable(x)==previous,'current national policy forced stale inert '+str(party))
 # Pending expiry clears with reapplication; no permanent quarantine.
 x=state();decision(x,'propose');x['day']=30;hook(x,'on_daily','A','B');hook(x,'on_daily','B','A')
 assert_(decision(x,'propose'),'reapply after expiry');decision(x,'withdraw');assert_(decision(x,'propose'),'reapply after current withdrawal')
 # Simultaneous separate partners and reverse mission directions are independent.
 x=state();decision(x,'mission_charge','A','B');decision(x,'mission_ambassador','A','C');decision(x,'mission_charge','B','A')
 assert_(flag(x,'out_pending','A','B') and flag(x,'out_pending','A','C') and flag(x,'out_pending','B','A'),'concurrent directed proposals')
 decision(x,'accept_charge','B','A');decision(x,'accept_ambassador','C','A');decision(x,'accept_charge','A','B')
 assert_(var(x,'mission_level','A','B')==1 and var(x,'mission_level','A','C')==2 and var(x,'mission_level','B','A')==1,'concurrent consent records')
 assert_(x['countries']['A']['variables'][P+'mission_count']==2,'current owned capacity count')
 # Mission count is an accounting field, without an invented worldwide numerical cap.
 x=state()
 for peer in ('B','C','D','F','G','H','I','J'):mission(x,'A',peer,'charge')
 mission(x,'A','K','charge')
 assert_(x['countries']['A']['variables'][P+'mission_count']==9,'ninth mission follows budget')
 decision(x,'close','A','B');assert_(x['countries']['A']['variables'][P+'mission_count']==8,'accounting count after own close')
 # Budget charges once on accepted class, upkeep deterministic per monthly hook.
 x=state();mission(x,level='charge');hook(x,'on_monthly');assert_(x['countries']['A']['variables']['treasury']==4.989,'actual monthly charge')
 x['countries']['A']['variables']['treasury']=0.;before=unrelated(x);hook(x,'on_monthly')
 assert_(var(x,'mission_level')==0 and flag(x,'protected_closed') and flag(x,'departure_outstanding'),'funding lapse closes only mission')
 assert_(unrelated(x)==before,'funding lapse preserves all actual legacy channels')
 # A war does not turn a permanent bilateral agreement into a new rupture.
 x=state();establish(x);mission(x);before=unrelated(x);x['countries']['A']['wars'].add('B');x['countries']['B']['wars'].add('A')
 before=unrelated(x);hook(x,'on_daily');assert_(flag(x,'established') and not flag(x,'broken'),'war does not silently sever relation record')
 assert_(unrelated(x)==before,'war cleanup leaves all other contracts')
 # Annexation only follows actual tracked partner arrays, before IDs disappear.
 for callback,actor,peer in [('on_annex','C','A'),('on_subject_annexed','A','C')]:
  x=state();establish(x);mission(x);mission(x,'B','A');before=unrelated(x);hook(x,callback,actor,peer)
  assert_(var(x,'mission_level')==0 and var(x,'mission_level','B','A')==0,'annex current pair '+callback)
  assert_(unrelated(x)==before,'annex preserves independent channels '+callback)
 # Rehydrate from durable flags/vars/arrays, discard all temporary source scopes.
 x=state();mission(x);decision(x,'propose_head');durable=rehydrate(x)
 decision(durable,'accept_head','B','A');decision(durable,'credentials')
 assert_(var(durable,'active_head')==1,'save-state rehydration pending head')
 decision(durable,'close');durable['day']=10000;hook(durable,'on_daily')
 assert_(flag(durable,'departure_outstanding') and flag(durable,'protected_closed'),'save-state outstanding duty persists')
 assert_(len(durable['countries']['A']['arrays'][P+'partners'])==1,'tracked array is unique')
 print(json.dumps({'all_passed':True,'current_source_assertions':sum(checks.values()),'groups':dict(checks),
  'native_runtime':False,'native_physical_presence_proven':False,'proof_scope':'actual package26 decisions, guards and effects interpreted with strict country/flag/array/deadline adapter; no event approval paths',
  'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in FILES}},indent=2))

if __name__=='__main__':main()
