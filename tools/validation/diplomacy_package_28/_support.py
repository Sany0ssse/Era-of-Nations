"""Strict current-source adapter, extending package26 scope/flag/array semantics.

Native10 confirms shared execution temporaries; scoped reads never read a temp.
Unknown commands fail. External influence/Singapore recalculation are witnessed,
not simulated; neither this model nor its durable round trip is a native campaign.
"""
from pathlib import Path
import importlib.util
from copy import deepcopy
import hashlib

ROOT=Path(__file__).resolve().parents[3]
P='eon_framework_negotiation_'
FILES=[
 'common/scripted_triggers/'+P+'triggers.txt',
 'common/scripted_effects/'+P+'effects.txt',
 'common/scripted_diplomatic_actions/'+P+'actions.txt',
 'common/decisions/'+P+'decisions.txt',
 'common/decisions/categories/'+P+'categories.txt',
 'common/on_actions/'+P+'on_actions.txt',
 'events/'+P+'events.txt',
 *[f'localisation/{lang}/{P}l_{lang}.yml' for lang in ('english','russian')],
 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
 'common/scripted_effects/eon_trade_treaty_effects.txt',
 'common/scripted_effects/eon_investment_treaty_effects.txt',
 'common/scripted_localisation/'+P+'scripted_localisation.txt',
]
spec=importlib.util.spec_from_file_location('framework_scope_adapter',ROOT/'tools/validation/diplomacy_package_26/test_relations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
parse=m.parse;one=m.one;compare=m.compare;ctx=m.ctx;switch=m.switch;value=m.value;key=m.key
m.TRIGGERS=m.definitions(FILES[0]);m.EFFECTS=m.definitions(FILES[1])
for name in FILES[10:12]:m.EFFECTS.update(m.definitions(name))
TRIGGERS=m.TRIGGERS;EFFECTS=m.EFFECTS
DECISIONS={k:v for k,o,v in m.definitions(FILES[3])[P+'category']}
HOOKS={k:v for k,o,v in m.definitions(FILES[5])['on_actions']}
ACTIONS={k:v for k,o,v in m.definitions(FILES[2])['scripted_diplomatic_actions']}
OLD={k:v for k,o,v in m.definitions(FILES[9])['scripted_diplomatic_actions']}
IDS=m.IDS
for name in ('SWI','ERI','SIN','SOV','CHI'):
 IDS.setdefault(name,len(IDS)+1)

original_country=m.country_ref
def country_ref(result,context,token):
 if token.startswith('var:'):
  number=value(result,context,token[4:])
  if number in result['countries']:return number
  return next((country for country,index in IDS.items() if index==number),None)
 return original_country(result,context,token)
m.country_ref=country_ref
original_condition=m.condition;original_execute=m.execute

def chunks(nodes):
 index=0
 while index<len(nodes):
  node=nodes[index];index+=1;group=[node]
  if node[0]=='if':
   while index<len(nodes) and nodes[index][0] in ('else_if','else'):
    group.append(nodes[index]);index+=1
  yield group

def condition(nodes,result,context):
 for group in chunks(nodes):
  name,op,data=group[0]
  c=result['countries'][context['scope']]
  if name=='if':
   ready=True
   for kind,operator,body in group:
    if kind=='else' or condition(one(body,'limit'),result,context):
     ready=condition([n for n in body if n[0]!='limit'],result,context);break
  elif name in ('set_temp_variable','add_to_temp_variable','multiply_temp_variable'):
   execute([(name,op,data)],result,context);ready=True
  elif name=='original_tag':ready=c['original_tag']==data
  elif name=='has_country_leader':ready=c['leader']==one(data,'name').strip('"')
  elif name=='has_idea':ready=data in c['ideas']
  elif name=='has_government':ready=c['government']==data
  elif name=='has_opinion':
   peer=country_ref(result,context,one(data,'target'));n=next(node for node in data if node[0]=='value')
   ready=compare(c['opinions'].get(peer,0),n[1],value(result,context,n[2]))
  elif name=='is_in_faction':ready=bool(c['allies'])==(data=='yes')
  elif name=='any_allied_country':ready=any(condition(data,result,switch(context,peer)) for peer in c['allies'])
  elif name=='is_in_faction_with':ready=country_ref(result,context,data) in c['allies']
  elif name=='is_subject_of':ready=c['overlord']==country_ref(result,context,data)
  else:ready=original_condition([(name,op,data)],result,context)
  if not ready:return False
 return True

original_value=m.value
def updated_value(result,context,token):
 if token.startswith('var:'):token=token[4:]
 if token.startswith('opinion@'):
  peer=country_ref(result,context,token.split('@',1)[1])
  return result['countries'][context['scope']]['opinions'].get(peer,0)
 if '.' in token and not token.startswith('"'):
  try:return float(token)
  except ValueError:pass
  scope,field=token.split('.',1)
  peer=country_ref(result,context,scope)
  if field=='id':return IDS[peer]
  # Explicit country lookup resolves only that country's persistent variables.
  nested=switch(context,peer)
  return result['countries'][peer]['variables'].get(key(result,nested,field),0)
 if token not in ('THIS','PREV','ROOT','FROM') and token not in result['countries']:
  field=key(result,context,token)
  if field in result.get('execution_temps',{}):return result['execution_temps'][field]
 # The inherited fallback cannot see country-local temp fixtures either.
 country=result['countries'][context['scope']];saved=country['temps'];country['temps']={}
 try:return original_value(result,context,token)
 finally:country['temps']=saved
m.value=updated_value;value=updated_value

def execute(nodes,result,context):
 for group in chunks(nodes):
  name,op,data=group[0]
  c=result['countries'][context['scope']]
  if name=='if':
   for kind,operator,body in group:
    if kind=='else' or condition(one(body,'limit'),result,context):
     execute([n for n in body if n[0]!='limit'],result,context);break
  elif name in ('set_temp_variable','add_to_temp_variable','multiply_temp_variable'):
   field,operator,wanted=data[0];assert operator=='=' and len(data)==1
   amount=value(result,context,wanted);field=key(result,context,field)
   shared=result.setdefault('execution_temps',{});previous=shared.get(field,0)
   shared[field]=amount if name=='set_temp_variable' else (previous+amount if name=='add_to_temp_variable' else previous*amount)
  elif name=='for_each_loop':
   fields={k:v for k,o,v in data};array=fields['array']
   for ordinal,item in enumerate(list(c['arrays'].get(array,[]))):
    shared=result.setdefault('execution_temps',{})
    shared[fields.get('value','v')]=item;shared[fields.get('index','i')]=ordinal
    execute([n for n in data if n[0] not in ('array','value','index','break')],result,context)
    if fields.get('break') and value(result,context,fields['break']):break
  elif name=='while_loop_effect':
   iterations=0
   while condition(one(data,'limit'),result,context):
    execute([n for n in data if n[0] not in ('limit','break')],result,context)
    iterations+=1;assert iterations<1000,'Nonterminating actual-source loop'
  elif name=='clamp_variable':
   field=key(result,context,one(data,'var'))
   assert field in c['variables'],('Native clamp on an uninitialized variable',field,context)
   original_execute([(name,op,data)],result,context)
  elif name in ('change_influence_percentage','SIN_calculate_singaporean_trade_agreements'):
   assert data=='yes'
   fields=('percent_change','tag_index','influence_target') if name=='change_influence_percentage' else ()
   result['external'].append((context['scope'],name,{field:value(result,context,field) for field in fields}))
  else:original_execute([(name,op,data)],result,context)
m.condition=condition;m.execute=execute

def state():
 countries={name:{'exists':True,'pp':600.,'variables':{'treasury':5.,'signed_trade_agreements':0},'temps':{},'flags':set(),'expires':{},
  'arrays':{'permanent_investment_targets':[], 'influence_array':[]},'wars':set(),'opinions':{peer:60 for peer in IDS},
  'opinion_modifiers':set(),'ideas':set(),'government':'democratic','original_tag':name,'leader':'Generic leader','allies':set(),'overlord':None} for name in IDS}
 return {'countries':countries,'day':0,'events':[],'global_flags':set(),'external':[],'execution_temps':{}}

def decision(result,family,name,actor='A',peer='B',force=False):
 result['execution_temps']={}
 body=DECISIONS[P+family+'_'+name];context=ctx(actor,peer)
 ready=all(condition(one(body,field),result,context) for field in ('allowed','target_root_trigger','target_trigger','visible','available'))
 if ready or force:
  result['execution_temps']={}
  execute(one(body,'complete_effect'),result,context)
 return ready

def action(result,family,actor='A',peer='B',force=False):
 result['execution_temps']={}
 body=ACTIONS['eon_propose_'+family+'_framework'];context=ctx(actor,peer)|{'scope':peer}
 ready=all(condition(one(body,field),result,context) for field in ('allowed','visible','selectable','can_be_sent'))
 if ready or force:
  result['execution_temps']={}
  execute(one(body,'complete_effect'),result,context)
 return ready

def old_callback(result,name,callback,actor='A',peer='B'):
 result['execution_temps']={}
 execute(one(OLD[name],callback),result,ctx(actor,peer)|{'scope':peer})

def hook(result,name,actor='A',peer='B'):
 result['execution_temps']={}
 execute(one(HOOKS[name],'effect'),result,ctx(actor,peer))

def var(result,family,field,actor='A',peer='B'):
 return result['countries'][actor]['variables'].get(P+family+'_'+field+'@'+peer,0)

def flag(result,family,field,actor='A',peer='B'):
 return m.hasflag(result,ctx(actor,peer),P+family+'_'+field+'@'+peer)

def stable(result):
 out=deepcopy(result);out.pop('events');out.pop('external');out['execution_temps']={}
 for c in out['countries'].values():c['temps']={}
 return out

def rehydrate(result):
 durable=deepcopy(result);durable['execution_temps']={}
 return m.rehydrate(durable)
def hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
