"""Execute candidate Clausewitz AST. Engine/event/TTL/UI boundaries stay explicit."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
import _model as m

OUT = Path(__file__).resolve().parent
CANDIDATE = SOURCE_ROOT
source_for_hash = SOURCE_FOR_HASH  # Hash comparisons only; AST readers keep actual bytes.
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
catalog=json.loads((OUT/'catalog.json').read_bytes())
def selected_paths(prefix):
 return [CANDIDATE/r for r in catalog['source_after_sha256'] if r.startswith(prefix)]
def before_path(relative):
 return OUT/'before'/relative
P = 'eon_investment_offer_v2_'
checks = 0
cases = []

def check(passed, message):
 global checks
 checks += 1
 assert passed, message

def load(path): return m.ast((CANDIDATE/path).read_text(encoding='utf-8-sig'))

for path in selected_paths('common/scripted_effects/'):
 m.effects.update({k:v for k,o,v in m.ast(path.read_text(encoding='utf-8-sig'))})
for path in selected_paths('common/scripted_triggers/'):
 m.triggers.update({k:v for k,o,v in m.ast(path.read_text(encoding='utf-8-sig'))})
for path in selected_paths('events/'):
 m.events.update({m.one(v,'id'):v for k,o,v in m.ast(path.read_text(encoding='utf-8-sig')) if k=='country_event'})
actions = {k:v for k,o,v in m.one(load('common/scripted_diplomatic_actions/'+P+'actions.txt'),'scripted_diplomatic_actions')}
decisions = {k:v for k,o,v in m.one(load('common/decisions/eon_investment_offer_v2_decisions.txt'),P+'category')}

def run(s, action, actor=2, partner=1, epoch=None):
 s['temp'] = {}
 if epoch is not None: s['temp'][P+'expected_epoch'] = epoch
 m.execute(m.effects[P+action], s, m.context(actor, partner, previous=(partner,)))

def menu_action(s, name, actor=2, partner=1, force=False, third=11):
 s['temp']={}
 c=m.context(actor,third,scope=partner)
 body=actions[P+'ui_'+name]
 ready=all(m.condition(m.one(body,field),s,c) for field in ['allowed','visible','selectable','can_be_sent'])
 s['temp']={}
 if ready or force:m.execute(m.one(body,'complete_effect'),s,c)
 return ready

def decision(s, name, actor=2, partner=1):
 return menu_action(s,name,actor,partner)

def var(s, field, actor=1, partner=2):
 return s['entities'][actor]['variables'].get(P+field+'@'+str(partner),0)

def count(s, actor=1): return s['entities'][actor]['variables'].get(P+'outgoing_count',0)

def state():
 s=m.state()
 for actor in range(1,12):
  if actor not in s['entities']: s['entities'][actor]=deepcopy(s['entities'][4])
  s['entities'][actor]['ai']=False
  m.execute(m.effects['init_investment_system'],s,m.context(actor))
 return s

def send(s, donor=1, recipient=2, cost=30, state_id=None, kind=1, amount=2, duration=100):
 target=state_id or -100-recipient
 if target not in s['entities']: s['entities'][target]=deepcopy(s['entities'][-101])
 s['entities'][target].update(owner=recipient,controller=recipient)
 m.stage(s,donor,recipient,target,kind,amount,cost,duration)
 s['temp']={}
 m.execute(m.one(m.events['AC_event.3'],'immediate'),s,m.context(donor))
 return var(s,'epoch',donor,recipient)

def accept(s, donor=1, recipient=2, epoch=None):
 run(s,'review',recipient,donor)
 run(s,'accept',recipient,donor,epoch or var(s,'epoch',recipient,donor))

def money(s): return tuple(s['entities'][i]['variables']['treasury'] for i in range(1,12))

def unchanged(s,before,label): check(m.persistent(s)==before,label)

def receipt(s,result,donor=1,recipient=2,epoch=None):
 for actor,partner in [(donor,recipient),(recipient,donor)]:
  check(var(s,'status',actor,partner)==result,'terminal status')
  check(var(s,'result',actor,partner)==result,'result receipt')
  if epoch is not None: check(var(s,'result_epoch',actor,partner)==epoch,'receipt binds epoch')
  check(P+'window@'+str(partner) not in s['entities'][actor]['flags'],'window released')
 check(count(s,donor)==0,'outgoing reservation released')

def record_case(name): cases.append(name)

# Stage executes actual donor/recipient snapshot writes and charges nothing.
s=state(); before=money(s); e=send(s)
check(money(s)==before,'staging charges no money')
check(var(s,'status')==1 and var(s,'status',2,1)==2,'roles mirror')
check(var(s,'donor')==1 and var(s,'recipient')==2,'explicit native country roles')
check(count(s)==1,'one reservation')
for field in ['donor','recipient','state','type','amount','cost','cofunding','duration','total_duration','epoch']:
 check(var(s,field)==var(s,field,2,1),'immutable terms mirror '+field)
accept(s); receipt(s,5,epoch=e)
check(money(s)[0]==970 and money(s)[1]==997,'actual principal/cofunding debit')
check(s['entities'][1]['variables']['active_projects']==1,'one actual project')
check(s['entities'][1]['variables']['eon_project_protocol^0']==24,'existing construction protocol')
check(s['entities'][1]['arrays']['project_array'][0]==-102,'frozen state projects')
check(s['entities'][1]['variables']['project_build_amount^0']==2,'frozen amount')
check(s['entities'][1]['variables']['project_monetary_cost^0']==30,'principal held under construction')
check(s['entities'][1]['variables']['int_investments']==0,'no early ROI portfolio transfer')
check('eon_investment_offer_partner' not in s['entities'][1]['variables'],'bridge cleared')
check(P+'bridge_in_progress' not in s['entities'][1]['flags'],'bridge flag cleared')
snapshot=m.persistent(s)
run(s,'accept',2,1,e); run(s,'decline',2,1,e); run(s,'withdraw',1,2,e)
unchanged(s,snapshot,'duplicate terminal actions inert')
record_case('actual staging/atomic acceptance/protocol24/duplicate actions')

# Legacy-compatible donor cap1; independently owned donors share a receiver.
s=state();e=send(s);send(s,recipient=3)
check(count(s)==1 and var(s,'epoch',1,3)==0,'one outgoing cap before staging')
run(s,'withdraw',1,2,e);send(s,recipient=3)
check(count(s)==1 and var(s,'status',1,3)==1,'released cap immediately reusable')
record_case('one outgoing cap/reuse')

# Actor binding and opposite direction lock.
s=state(); e=send(s); before=m.persistent(s)
for actor,partner,action in [(1,2,'accept'),(1,2,'decline'),(2,1,'withdraw'),(3,1,'accept'),(2,3,'accept')]:
 run(s,action,actor,partner,e); unchanged(s,before,'wrong actor '+action)
send(s,2,1,cost=50); check(var(s,'donor')==1 and count(s,2)==0,'opposite direction pending blocked')
send(s,1,2,cost=70); check(var(s,'cost')==30 and count(s)==1,'duplicate same-pair stage blocked')
record_case('actor roles/opposite direction/duplicate stage')

# Acknowledgement is inert; replacement resets review; stale explicit epochs inert.
for terminal in ['withdraw','decline']:
 s=state(); e1=send(s); run(s,'review')
 run(s,terminal,1 if terminal=='withdraw' else 2,2 if terminal=='withdraw' else 1,e1)
 e2=send(s,cost=65,kind=2,amount=1,duration=120)
 check(e2==e1+1,'durable epoch increments')
 check(var(s,'reviewed_epoch',2,1)==0,'replacement resets review')
 baseline=m.persistent(s)
 for ident in ['AC_event.10',P+'notice.1']:
  for k,o,v in m.events[ident]:
   if k=='option': m.execute(v,s,m.context(2,1))
 unchanged(s,baseline,'old informational report inert')
 run(s,'accept',2,1,e2); unchanged(s,baseline,'current consent without new review blocked')
 run(s,'review'); baseline=m.persistent(s)
 for action,actor,partner in [('accept',2,1),('decline',2,1),('withdraw',1,2)]:
  run(s,action,actor,partner,e1); unchanged(s,baseline,'old expected epoch inert '+action)
 decision(s,'accept'); check(s['entities'][1]['variables']['treasury']==935,'current final decision starts current frozen terms')
 check(s['entities'][1]['variables']['project_building_type^0']==2,'replacement building exact')
record_case('old report/replacement review/stale epoch/current decision')

# Acceptance requires BOTH authoritative native flags before the daily cleanup.
for expired in ['donor_flag','recipient_flag','both_flags']:
 s=state(); e=send(s); run(s,'review')
 if 'flag' in expired:
  if expired!='recipient_flag': s['entities'][1]['flags'].discard(P+'window@2')
  if expired!='donor_flag': s['entities'][2]['flags'].discard(P+'window@1')
 else: s['entities'][1 if expired=='donor_days' else 2]['variables'][P+'days@'+('2' if expired=='donor_days' else '1')]=0
 original_money=money(s); run(s,'accept',2,1,e)
 check(money(s)==original_money and s['entities'][1]['variables']['active_projects']==0,'late consent blocked '+expired)
 run(s,'daily_pair',2,1); receipt(s,8,epoch=e)
 baseline=m.persistent(s); run(s,'daily_pair',1,2); unchanged(s,baseline,'repeat expiry inert')
record_case('deadline gates before daily/repeated expiry')

# Display counters reaching zero never expire a still-live native flag.
for order in [(1,2),(2,1)]:
 s=state();e=send(s)
 for day in range(1,96):
  for actor in order:run(s,'daily_update',actor,3-actor)
  check(var(s,'days')==max(0,90-day),'display counter clamped')
  check(var(s,'status')==1 and count(s)==1,'no synthetic early native expiry')
 s['entities'][1]['flags'].discard(P+'window@2')
 for actor in order:run(s,'daily_update',actor,3-actor)
 receipt(s,8,epoch=e)
 check(money(s)[:2]==(1000,1000),'flag expiry charges nothing')
record_case('native flag authority/counter-only90ticks/both daily orders')

# Final state/budget/policy/slot checks execute original building predicates.
mutations={
 'donor_money':lambda s:s['entities'][1]['variables'].update(treasury=29),
 'recipient_money':lambda s:s['entities'][2]['variables'].update(treasury=2),
 'owner':lambda s:s['entities'][-102].update(owner=3),
 'controller':lambda s:s['entities'][-102].update(controller=3),
 'war_from_donor':lambda s:s['entities'][1]['wars'].add(2),
 'war_from_recipient':lambda s:s['entities'][2]['wars'].add(1),
 'justification':lambda s:s['entities'][1]['justifying'].add(2),
 'donor_policy':lambda s:s['entities'][1]['flags'].add('disabled_foreign_investment'),
 'recipient_policy':lambda s:s['entities'][2]['flags'].add('int_auto_reject_investment_flag'),
 'slots':lambda s:s['entities'][-102]['slots'].update(industrial_complex=1),
 'project_cap':lambda s:s['entities'][1]['variables'].update(active_projects=15),
 'project_index':lambda s:s['entities'][1]['arrays'].update(project_array=[-102]*15),
 'state_arrays':lambda s:s['entities'][-102]['arrays'].update(projects_in_state=[3],project_type_in_state=[]),
 'existing_state_project':lambda s:s['entities'][-102]['arrays'].update(projects_in_state=[1],project_type_in_state=[1]),
 'donor_annexed':lambda s:s['entities'][1].update(exists=False),
 'recipient_annexed':lambda s:s['entities'][2].update(exists=False),
}
for name,mutate in mutations.items():
 s=state(); e=send(s); run(s,'review'); mutate(s)
 before=money(s); run(s,'accept',2,1,e)
 check(money(s)==before,'no debit after changed '+name)
 check(P+'bridge_in_progress' not in s['entities'][1]['flags'],'no bridge after '+name)
 check(s['entities'][1]['variables'].get('eon_project_protocol^0',0)==0,'no new project after '+name)
record_case('16 post-review budget/ownership/policy/war/slots/index invalidations')

s=state(); s['entities'][2]['variables']['treasury']=4
e1=send(s,1,2); e3=send(s,3,2); run(s,'review',2,1); run(s,'review',2,3)
run(s,'accept',2,1,e1); before=money(s); run(s,'accept',2,3,e3)
check(money(s)==before,'shared recipient cofunding cannot overcommit')
check(var(s,'status',3,2)==1 and count(s,3)==1,'other donor request retains ownership')
record_case('independent donors to one recipient/shared recipient cofunding')

# Peer corruption/future epoch cleanup never touches unrelated live peer.
for field,bad in [('epoch',99),('donor',3),('recipient',3)]:
 s=state(); e=send(s); s['entities'][2]['variables'][P+field+'@1']=bad
 peer=deepcopy(s['entities'][2]); run(s,'daily_pair',1,2)
 check(s['entities'][2]==peer,'corrupted/future peer untouched '+field)
 check(var(s,'status')==9 and count(s)==0,'owned slot safely retired '+field)
record_case('future epoch/wrong identity cleanup isolation')

# Legacy snapshots retire without cash; direct old effect cannot start a project.
s=state(); m.stage(s); s['entities'][1]['variables'].update(eon_investment_offer_partner=2,eon_investment_offer_cost=30)
s['entities'][1]['flags'].update({'AC_ai_investment_pending','this_investment_offer_pending@2'})
before=money(s); run(s,'daily_update',1,2)
check(money(s)==before,'legacy drain does not invent payment/refund')
check('eon_investment_offer_partner' not in s['entities'][1]['variables'],'legacy slot drained')
check('AC_ai_investment_pending' not in s['entities'][1]['flags'],'global pending blocker retired')
send(s); before=money(s)
m.execute(m.effects['eon_investment_execute_offer'],s,m.context(1,previous=(2,)))
check(money(s)==before and count(s)==1,'unbridged legacy start has no authority')
record_case('legacy drain/guarded construction start')

# AI weights use explicit fixture outcomes; all acceptance/refusal transitions actual.
for selection,expected in [('accept',5),('decline',6)]:
 s=state(); s['entities'][2]['ai']=True; s['ai_selection']=selection; before=money(s)
 e=send(s); receipt(s,expected,epoch=e)
 check(s.get('unverified_ai_selection_fixture_calls')==[selection],'declared AI choice fixture')
 check(money(s)[0]==(970 if expected==5 else before[0]),'AI transition actual debit')
for policy,expected in [('int_auto_accept_investment_flag',5),('int_auto_reject_investment_flag',9)]:
 s=state(); s['entities'][2]['flags'].add(policy); e=send(s)
 receipt(s,expected,epoch=e)
 check(not s.get('unverified_ai_selection_fixture_calls'),'human policy does not roll AI choice')
s=state(); send(s); s['entities'][2]['ai']=True; s['ai_selection']='decline'; run(s,'daily_update',2,1)
receipt(s,6); record_case('AI choice fixtures/human auto policy/AI-control transition')
s=state(); s['entities'][1]['ideas'].add('EU_member'); s['entities'][2]['ideas'].add('EU_member')
check(m.condition(m.triggers[P+'ai_same_organization'],s,m.context(2,3,previous=(1,))),'organization sees actual pair donor despite unrelated FROM')
s['entities'][1]['ideas'].discard('EU_member'); s['entities'][3]['ideas'].add('EU_member')
check(not m.condition(m.triggers[P+'ai_same_organization'],s,m.context(2,3,previous=(1,))),'organization ignores unrelated FROM')

# Poison persisted names do not substitute into shared bare captures or actor roles.
s=state(); e=send(s)
for ent in s['entities'].values():
 ent['variables'].update({P+'read_epoch':999,P+'expected_epoch':999,P+'check_recipient':999,P+'check_amount':999})
accept(s,epoch=e); receipt(s,5,epoch=e)
record_case('same-named persistent variable poison')

# Malicious mirrored terms cannot redirect acceptance without the actor identity guards.
for field,mutator in [('donor',3),('recipient',3),('state',-103),('cost',31),('amount',3)]:
 s=state(); e=send(s); run(s,'review'); s['entities'][2]['variables'][P+field+'@1']=mutator
 before=money(s); run(s,'accept',2,1,e); check(money(s)==before,'tampered mirror rejected '+field)
record_case('mirrored actor/payload tamper controls')
for kind in range(1,16):
 s=state(); e=send(s,kind=kind,amount=1); check(var(s,'status')==1,'original building eligibility '+str(kind))
 accept(s); receipt(s,5,epoch=e)
 check(s['entities'][1]['variables']['project_building_type^0']==kind,'frozen building bridge '+str(kind))
record_case('all fifteen inherited building eligibility/bridge paths')

# Bridge allocation failure is injected at the native allocation boundary and sealed terminal.
original_allocator=m.effects['get_available_project']
m.effects['get_available_project']=[]
s=state(); e=send(s); before=money(s); accept(s); receipt(s,10,epoch=e)
check(money(s)==before,'failed allocation charges no money')
check('eon_investment_offer_partner' not in s['entities'][1]['variables'],'failed bridge clears fields')
m.effects['get_available_project']=original_allocator
record_case('declared allocation-failure fixture/terminal idempotent cleanup')

# Daily processing removes ALL adjacent expired entries from immutable snapshots.
for terminal in ['decline','withdraw','expiry','annex','accept','lapse']:
 s=state()
 for donor in range(1,11):
  if donor==2:continue
  send(s,donor,2,cost=1,amount=1)
 check(len(s['entities'][2]['arrays'][P+'partners'])==9,'receiver multiple active donors')
 for donor in range(1,11):
  if donor==2:continue
  e=var(s,'epoch',donor,2)
  if terminal=='decline':run(s,'review',2,donor);run(s,'decline',2,donor,e)
  elif terminal=='withdraw':run(s,'withdraw',donor,2,e)
  elif terminal=='accept':accept(s,donor,2,e)
  elif terminal=='expiry':s['entities'][donor]['flags'].discard(P+'window@2')
  elif terminal=='lapse':s['entities'][donor]['wars'].add(2);s['entities'][2]['wars'].add(donor)
 if terminal=='annex':run(s,'annex_cleanup',2,11)
 elif terminal in ['expiry','lapse']:run(s,'daily_update',2,11)
 for ident in range(1,11):
  check(s['entities'][ident]['arrays'].get(P+'partners',[])==[],'all active indexes empty '+terminal)
  check(count(s,ident)==0,'all cap reservations released '+terminal)
 run(s,'daily_update',2,11);baseline=m.persistent(s);run(s,'daily_update',2,11);unchanged(s,baseline,'repeat clean daily inert')
record_case('nine adjacent partners every terminal outcome/snapshot removal')

# Repeated history grows only durable pair epochs, never daily work indexes.
s=state()
for cycle in range(100):
 partner=2+cycle%9;e=send(s,1,partner)
 run(s,'withdraw',1,partner,e)
 for ent in s['entities'].values():check(ent['arrays'].get(P+'partners',[])==[],'no history after cycle')
check(var(s,'epoch',1,2)==12,'epochs retained through repeated partner reuse')
run(s,'daily_update',1,11)
check(not s.get('temp_arrays'),'temporary snapshot released')
record_case('100cycles/multiplepartners/active-only bounded index')

# New five country actions use native ROOT actor / THIS selected target; FROM is
# deliberately unrelated. No amount/type/state comes from an earlier hover.
for actor in range(1,11):
 partner=actor%10+1
 s=state();e=send(s,actor,partner)
 check(menu_action(s,'review',partner,actor),'review direct country transport')
 check(var(s,'reviewed_epoch',partner,actor)==e,'review actor identity')
 check(menu_action(s,'accept',partner,actor),'accept direct country transport')
 receipt(s,5,actor,partner,e)
 check(menu_action(s,'status',actor,partner),'terminal status independent active index')
 check(s['entities'][actor]['variables']['treasury']==970,'allcountry donor debit')
 check(s['entities'][partner]['variables']['treasury']==997,'allcountry recipient debit')
for name in ['review','accept','decline','withdraw','status']:
 s=state();e=send(s);run(s,'review')
 actor,partner=(1,2) if name=='withdraw' else (2,1)
 s['entities'][actor]['ai']=True;before=m.persistent(s)
 check(not menu_action(s,name,actor,partner,force=True),'AI transport excluded '+name)
 unchanged(s,before,'AI forced final transport inert '+name)
 check(s['temp']=={},'AI excluded before pair TEMP '+name)
 check(m.one(decisions[P+name],'allowed')==[('always','=','no')],'legacy alias disabled')
record_case('allcountry direct transport/independentFROM/AI earlyTEMP exclusion')

# Simulate both actual annex hook source frames without legacy project side effects.
hooks=m.one(load('common/on_actions/eon_investment_lifecycle_on_actions.txt'),'on_actions')
saved=m.effects['eon_investment_lifecycle_cancel_annexed_donor']
m.effects['eon_investment_lifecycle_cancel_annexed_donor']=[]
for hook in ['on_annex','on_subject_annexed']:
 s=state();e=send(s)
 c=m.context(1,2) if hook=='on_annex' else m.context(2,1)
 m.execute(m.one(m.one(hooks,hook),'effect'),s,c)
 receipt(s,9,epoch=e)
m.effects['eon_investment_lifecycle_cancel_annexed_donor']=saved
record_case('both native-defined annex callback frames/samepair cleanup')

# Both legacy option IDs remain inert, including after replacement and migration.
options=[v for k,o,v in m.events['AC_event.10'] if k=='option']
check([m.one(v,'name') for v in options]==['AC_event.1.o1','AC_event.1.o2',P+'notice.ok'],'legacy option identities preserved/visible acknowledgement')
for option in options[:2]:check(m.one(option,'trigger')==[('always','=','no')],'misleading legacy response labels hidden')
s=state();s['entities'][1]['variables'].update(eon_investment_offer_partner=2,eon_investment_offer_cost=30)
s['entities'][1]['flags'].update({'AC_ai_investment_pending','this_investment_offer_pending@2'})
before=money(s);run(s,'daily_update',1,2)
check(money(s)==before,'migration no payment/refund/penalty')
check(any(event[0]==P+'notice.2' for event in s['events']),'human migration passive notice')
baseline=m.persistent(s);run(s,'daily_update',1,2);unchanged(s,baseline,'migration once')
send(s);baseline=m.persistent(s)
for option in options:m.execute(option,s,m.context(2,1))
unchanged(s,baseline,'old option payloads inert in current AST')
for ent in s['entities'].values():ent['variables']['break']=1
s['entities'][1]['flags'].discard(P+'window@2');run(s,'daily_update',1,2)
receipt(s,8)
check(s['entities'][1]['arrays'][P+'partners']==[],'default break poison cannot skip active cleanup')
record_case('legacy optionIDs/passive migration once/defaultloopbreak poison')

# Complete parsing/grammar/byte-preservation checks bind evidence to exact candidate files.
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
for entry in manifest['files']:
 raw=(CANDIDATE/entry['path']).read_bytes()
 check(hashlib.sha256(source_for_hash(raw,entry['path'])).hexdigest()==entry['candidate_sha256'],'manifest '+entry['path'])
 if entry['path'].endswith('.yml'): check(raw.startswith(b'\xef\xbb\xbf'),'new localisation native UTF8 BOM')
 if entry['before_sha256']:
  original=(OUT/'before'/entry['path']).read_bytes()
  check(original.startswith(b'\xef\xbb\xbf')==raw.startswith(b'\xef\xbb\xbf'),'BOM preserved '+entry['path'])
  check((b'\r\n' in original)==(b'\r\n' in raw),'EOL family preserved '+entry['path'])
 if entry['path'].endswith('.txt'): m.ast(raw.decode('utf-8-sig'))

def nodes(tree):
 for node in tree:
  yield node
  if isinstance(node[2],list): yield from nodes(node[2])
for path in [CANDIDATE/r for r in catalog['source_after_sha256'] if r.endswith('.txt')]:
 for key,op,value in nodes(m.ast(path.read_text(encoding='utf-8-sig'))):
  if key=='check_variable': m.variable_comparison(value)
  if key=='set_temp_variable':
   check(not any('.' in k for k,o,v in value),'no qualified temporary writes in offer candidate') if P in str(value) else None
  if key=='set_country_flag' and isinstance(value,list) and any(k=='days' for k,o,v in value):
   check(m.one(value,'value')=='1','explicit native timed flag value')

# Existing construction body is identical apart from its new bridge authorization gate.
old=(OUT/'before/common/scripted_effects/eon_investment_project_effects.txt').read_text(encoding='utf-8-sig')
new=(CANDIDATE/'common/scripted_effects/eon_investment_project_effects.txt').read_text(encoding='utf-8-sig')
def effect_body(text,name): return m.one(m.ast(text),name)
before=effect_body(old,'eon_investment_execute_offer'); after=deepcopy(effect_body(new,'eon_investment_execute_offer'))
outer=m.one(after,'if'); check(m.one(outer,'limit')==[('has_country_flag','=',P+'bridge_in_progress')],'whole unbridged executor inert'); after=[n for n in outer if n[0]!='limit']; first=next(v for k,o,v in after if k=='if'); limits=m.one(first,'limit'); check(limits.pop(0)==('has_country_flag','=',P+'bridge_in_progress'),'only bridge guard added to construction')
check(before==after,'entire existing construction execute AST preserved')
original_event=next(v for k,o,v in m.ast((OUT/'before/events/00_AC_events.txt').read_text(encoding='utf-8-sig')) if k=='country_event' and m.one(v,'id')=='AC_event.10')
old_choices=[m.one(v,'ai_chance') for k,o,v in original_event if k=='option']
compiled=m.effects[P+'ai_compute_weights'];cursor=1
for index,original in enumerate(old_choices):
 field=P+('ai_accept_weight' if index==0 else 'ai_decline_weight')
 check(compiled[cursor]==('set_temp_variable','=',[(field,'=',m.one(original,'base'))]),'AI base weight preserved');cursor+=1
 def adapt(node):
  key,operator,value=node
  if isinstance(value,list):value=[adapt(child) for child in value]
  else:value=value.replace('FROM.eon_investment_offer_type',P+'ai_type').replace('FROM','PREV').replace('ai_has_same_organization',P+'ai_same_organization')
  key=key.replace('FROM.eon_investment_offer_type',P+'ai_type').replace('FROM','PREV').replace('ai_has_same_organization',P+'ai_same_organization')
  return key,operator,value
 expected=[]
 for key,operator,modifier in original:
  if key!='modifier':continue
  modifier=[adapt(node) for node in modifier];op=next(n for n in modifier if n[0] in ('add','factor'));condition=[n for n in modifier if n[0] not in ('add','factor')]
  action=('add_to_temp_variable' if op[0]=='add' else 'multiply_temp_variable','=',[(field,'=',op[2])])
  expected.append(('if','=',[('limit','=',condition),action]) if condition else action)
 check(compiled[cursor:cursor+len(expected)]==expected,'all inherited25 AI predicates/operations in exact order');cursor+=len(expected)+1
record_case('manifest/source grammar/BOM/EOL/construction preservation')
for relative,expected in catalog['canonical_before_sha256'].items():
 check(hashlib.sha256(before_path(relative).read_bytes()).hexdigest()==expected,'canonical original fixture unchanged '+relative)

for relative, expected in manifest['inputs'].items():
 check(hashlib.sha256(source_for_hash((CANDIDATE/relative).read_bytes(),relative)).hexdigest()==catalog['source_after_sha256'].get(relative,expected),'current candidate/unchanged dependency binding '+relative)
for relative, expected in manifest['protected'].items():
 check(hashlib.sha256((CANDIDATE/relative).read_bytes()).hexdigest()==expected,'protected existing optimizations '+relative)
import base64
inverse=json.loads((OUT/'full-inverse.json').read_text())
check([e['path'] for e in inverse]==[e['path'] for e in manifest['files']],'inverse exact target set')
for entry in inverse:
 raw=(CANDIDATE/entry['path']).read_bytes()
 check(hashlib.sha256(source_for_hash(raw,entry['path'])).hexdigest()==entry['after_sha256'],'inverse candidate binding')
 current=before_path(entry['path'])
 check(base64.b64decode(entry['before_b64'])==current.read_bytes() if entry['before_b64'] is not None else not current.exists(),'exact complete original inverse')
for lang in ['english','russian']:
 text=(CANDIDATE/f'localisation/{lang}/{P}l_{lang}.yml').read_text(encoding='utf-8-sig')
 ui_terms=re.search(r'(?m)^ '+P+r'ui_terms_tt:0 "(.*)"$',text).group(1)
 check('@FROM' not in ui_terms and '[?ROOT.' in ui_terms and '@THIS' in ui_terms,'selectedcountry ROOT/THIS terms scopes')
record_case('exact14 fullinverse/current11dependencies/protectedAI9framework6raid/UIterms')

report={
 'source_model_only':True,'result':'PASS','checks':checks,'cases':cases,
 'candidate_AST_execution_in_model':True,'candidate_manifest_sha256':hashlib.sha256((OUT/'manifest.json').read_bytes()).hexdigest(),
 'native_acceptance':False,'production_edited':False,
 'explicit_fixture_boundaries':[
  'Country/state tokens use existing package24 entity model; actual full token conversion still requires native calibration.',
  'Native timed flag TTL is not emulated. Flag-loss scenarios manually remove flags; display ticks are not an expiry mechanism.',
  'AI choice uses the explicitly selected accept/refuse random_list fixture; natural scheduling/random selection remains unverified.',
  'Allocation failure is an injected get_available_project boundary fixture.',
  'Country-event delivery, UI rendering/click identity, save/load and MP are not modelled.',
  'Construction state-result writers remain outside this proposal lifecycle scope.'
 ]
}
check(checks==3358 and len(cases)==22,'current meaningful3358 checks/22 groups retained')

# Separate current explicit25 weight AST/arithmetic proof; native RNG is not emulated.
lifecycle_report=report
"""Execute actual explicit-weight AST. Native draw/quantization remain separate."""
from copy import deepcopy
from pathlib import Path
import base64,hashlib,json
import _model as m
HERE=Path(__file__).resolve().parent;P='eon_investment_offer_v2_';REL='common/scripted_effects/eon_investment_offer_v2_effects.txt'
checks=0
def check(ok,label):
    global checks
    checks+=1;assert ok,label
sha=lambda b:hashlib.sha256(b).hexdigest()
for folder,registry in [('common/scripted_effects',m.effects),('common/scripted_triggers',m.triggers)]:
    for file in selected_paths(folder+'/'):registry.update({k:v for k,o,v in m.ast(file.read_text('utf-8-sig'))})
for file in selected_paths('events/'):
    m.events.update({m.one(v,'id'):v for k,o,v in m.ast(file.read_text('utf-8-sig')) if k=='country_event'})
_parent_journal=catalog['ordered_ai_parent_derivation'];_current=(CANDIDATE/REL).read_bytes();_i=_parent_journal['offset'];_before=base64.b64decode(_parent_journal['before_b64']);_after=base64.b64decode(_parent_journal['after_b64']);assert _current[_i:_i+len(_after)]==_after
_parent_raw=_current[:_i]+_before+_current[_i+len(_after):];assert sha(_parent_raw)==_parent_journal['before_sha256']
parent_body=m.one(m.ast(_parent_raw.decode('utf-8-sig')),P+'ai_choose')
draw=m.one(m.one(parent_body,'else'),'random_list')
mods=[[v for k,o,v in branch if k=='modifier'] for base,o,branch in draw]
compiled=m.effects[P+'ai_compute_weights'];choose=m.effects[P+'ai_choose']
def assert_compilation(candidate):
    """Finite validator derived from the historical draw, not a candidate self-comparison."""
    expected=[('set_temp_variable','=',[(P+'ai_type','=',P+'type@PREV')])]
    for branch,(base,operator,body) in enumerate(draw):
        field=P+('ai_accept_weight' if branch==0 else 'ai_decline_weight')
        expected.append(('set_temp_variable','=',[(field,'=',base)]))
        for old in mods[branch]:
            operations=[node for node in old if node[0] in ('add','factor')]
            assert len(operations)==1 and operations[0][1]=='='
            op=operations[0];predicate=[node for node in old if node[0] not in ('add','factor')]
            action=('add_to_temp_variable' if op[0]=='add' else 'multiply_temp_variable','=',[(field,'=',op[2])])
            expected.append(('if','=',[('limit','=',predicate),action]) if predicate else action)
        expected.append(('clamp_temp_variable','=',[('var','=',field),('min','=','0')]))
    expected.extend([('set_temp_variable','=',[(P+'ai_total_weight','=',P+'ai_accept_weight')]),('add_to_temp_variable','=',[(P+'ai_total_weight','=',P+'ai_decline_weight')])])
    assert candidate==expected,'Historical modifier compilation changed'
assert_compilation(compiled);check(True,'Full historical compiler AST exact including initial type')
check(list(map(len,mods))==[11,14],'Original eleven/fourteen modifier census')
cursor=1;predicates=[]
for branch,(base,operator,body) in enumerate(draw):
    field=P+('ai_accept_weight' if branch==0 else 'ai_decline_weight')
    check(compiled[cursor]==('set_temp_variable','=',[(field,'=',base)]),'Exact original base');cursor+=1
    for old in mods[branch]:
        operation=[n for n in old if n[0] in ('add','factor')];check(len(operation)==1,'Exactly one original operation')
        op=operation[0];predicate=[n for n in old if n[0] not in ('add','factor')]
        action=('add_to_temp_variable' if op[0]=='add' else 'multiply_temp_variable','=',[(field,'=',op[2])])
        expected=('if','=',[('limit','=',predicate),action]) if predicate else action
        check(compiled[cursor]==expected,'Exact predicate TEMP order and arithmetic operation')
        if predicate:predicates.append(m.one(compiled[cursor][2],'limit'))
        cursor+=1
    check(compiled[cursor]==('clamp_temp_variable','=',[('var','=',field),('min','=','0')]),'Only final nonnegative clamp');cursor+=1
check(compiled[cursor:]==[('set_temp_variable','=',[(P+'ai_total_weight','=',P+'ai_accept_weight')]),('add_to_temp_variable','=',[(P+'ai_total_weight','=',P+'ai_decline_weight')])],'Exact final total')
check(m.one(m.one(choose,'if'),'limit')==[n for n in mods[0][-1] if n[0]!='factor'],'Same original terminal policy predicate')
check(m.effects[P+'ai_probe_decline_sign']==m.one(m.ast(_parent_raw.decode('utf-8-sig')),P+'ai_probe_decline_sign'),'Old helper ID definition unchanged')
check(not any(n[0]==P+'ai_probe_decline_sign' for n in choose),'No doubled sign-probe work')
branch=m.one(choose,'else');selection=m.one(m.one(branch,'if'),'random_list')
check([n[0] for n in selection]==[P+'ai_accept_weight',P+'ai_decline_weight'],'Documented variable-weight transport')
check(all(not any(k=='modifier' for k,o,v in b) for name,o,b in selection),'No native additive ai_chance modifiers in random_list')

def state():
    s=m.state()
    for ident in (1,2,3,4):
        s['entities'][ident]['ai']=False;s['entities'][ident]['original_tag']='USA' if ident==1 else 'URG'
        m.execute(m.effects['init_investment_system'],s,m.context(ident))
    return s
def original_weight(modifiers,base,s,c):
    value=float(base)
    for modifier in modifiers:
        if m.condition([n for n in modifier if n[0] not in ('add','factor')],s,c):
            for key,op,operand in modifier:
                if key=='add':value+=m.value(s,c,operand)
                if key=='factor':value*=m.value(s,c,operand)
    return max(0,value)
opinions=[-1000,-600.001,-600,-599.999,-201,-200,-199.999,-50,-40,-1,0,1,15,20,30,40,50,100,599.999,600,600.001,1000]
cases=0;max_accept=0;max_decline=0
for opinion in opinions:
 for government in ['democratic','neutrality','nationalist']:
  for same in [False,True]:
   for top in [False,True]:
    for tag in ['URG','NKO','PER','CHI']:
        s=state();c=m.context(3,2,previous=(1,));ent=s['entities'][3]
        ent.update(government=government,original_tag=tag);s['entities'][1]['government']=government if same else 'fascism'
        ent['variables'].update({'opinion@1':opinion,'interest_rate':0,'domestic_influence_amount':100,'gdp_per_capita':100,P+'type@1':1})
        ent['arrays']['influence_array']=[1,1,1,1] if top else [0,0,0,0]
        reference=deepcopy(s);reference['temp'][P+'ai_type']=1
        a=original_weight(mods[0],10,reference,c);d=original_weight(mods[1],0,reference,c)
        m.execute(compiled,s,c)
        check(abs(m.value(s,c,P+'ai_accept_weight')-a)<1e-7,'Actual compiled accept arithmetic matches legacy source')
        check(abs(m.value(s,c,P+'ai_decline_weight')-d)<1e-7,'Actual compiled decline arithmetic matches legacy source')
        check(abs(m.value(s,c,P+'ai_total_weight')-(a+d))<1e-7,'Actual source total matches both weights')
        max_accept=max(max_accept,a);max_decline=max(max_decline,d);cases+=1
# Additional source threshold/operator coverage, including all domestic/type factors.
for kind in range(1,16):
 for domestic in [100,60,59.999,50,49.999,35,34.999,20,19.999,10,9.999,0]:
    s=state();c=m.context(3,2,previous=(1,));ent=s['entities'][3]
    ent.update(government='nationalist',original_tag='CHI',num_of_factories=29,num_of_available_civilian_factories=29)
    ent['variables'].update({'opinion@1':-300,'interest_rate':0,'domestic_influence_amount':domestic,'gdp_per_capita':14.999,P+'type@1':kind,'treasury_rate':1,'gdp_total':100,'unfulfilled_energy_demand_var':0})
    reference=deepcopy(s);reference['temp'][P+'ai_type']=kind
    a=original_weight(mods[0],10,reference,c);d=original_weight(mods[1],0,reference,c)
    m.execute(compiled,s,c);check(abs(m.value(s,c,P+'ai_accept_weight')-a)<1e-7,'All type/accept-factor thresholds exact');check(abs(m.value(s,c,P+'ai_decline_weight')-d)<1e-7,'All domestic/decline-factor thresholds exact')
    max_accept=max(max_accept,a);max_decline=max(max_decline,d);cases+=1
# Count the actual modifier-predicate AST identities once, including nested conditions.
hits={id(n):0 for n in predicates};condition=m.condition
def counted(nodes,s,c):
    if id(nodes) in hits:hits[id(nodes)]+=1
    return condition(nodes,s,c)
m.condition=counted;s=state();m.execute(compiled,s,m.context(3,2,previous=(1,)));m.condition=condition
check(all(n==1 for n in hits.values()),'Each original modifier predicate evaluated once in ordinary compiler')

def send(s):
    m.stage(s,1,3,-101,1,1,30,100);s['entities'][-101].update(owner=3,controller=3)
    s['temp']={};m.execute(m.one(m.events['AC_event.3'],'immediate'),s,m.context(1))
def statuses(s):return [s['entities'][a]['variables'].get(P+'status@'+str(t),0) for a,t in [(1,3),(3,1)]]
# Both zero and positive decline policies terminate without draw/debit/retry.
for opinion in [-50,100]:
    s=state();s['entities'][3]['ai']=True;s['entities'][3]['variables'].update({'interest_rate':10,'opinion@1':opinion});cash=[s['entities'][n]['variables']['treasury'] for n in [1,3]];send(s)
    check(statuses(s)==[6,6],'Original terminal policy always declines')
    check(not s.get('unverified_ai_selection_fixture_calls'),'Terminal policy consumes no fixture/native draw')
    check([s['entities'][n]['variables']['treasury'] for n in [1,3]]==cash,'Policy decline no cash debit')
    check(all(s['entities'][n]['arrays'].get(P+'partners',[])==[] for n in [1,3]),'Terminal active indexes released')
    m.execute(m.effects[P+'daily_update'],s,m.context(3,2));before=m.persistent(s)
    for _ in range(3):m.execute(m.effects[P+'daily_update'],s,m.context(3,2))
    check(before==m.persistent(s),'Terminal policy no recurring daily retry')
for selection,terminal in [('accept',5),('decline',6)]:
    s=state();s['entities'][3]['ai']=True;s['ai_selection']=selection;send(s)
    check(statuses(s)==[terminal,terminal],'Ordinary weighted declared choice executes real terminal '+selection)
    check(s['unverified_ai_selection_fixture_calls']==[selection],'Ordinary declared choice once')
# Math/compiler source negative controls; no mutable cached score or policy effects.
for mutation in ['wrong_order','wrong_operand','missing_modifier']:
    bad=deepcopy(compiled)
    if mutation=='wrong_order':bad[2],bad[3]=bad[3],bad[2]
    elif mutation=='wrong_operand':bad[2][2][1][2][0]=(P+'ai_accept_weight','=','999')
    else:bad.pop(2)
    try:assert_compilation(bad)
    except AssertionError:check(True,'Historical AST validator rejects mutation '+mutation)
    else:raise AssertionError('Historical AST validator accepted mutation '+mutation)
j=json.loads(json.dumps(catalog['ordered_ai_parent_derivation']).encode());raw=(CANDIDATE/REL).read_bytes();old,new=base64.b64decode(j['before_b64']),base64.b64decode(j['after_b64']);i=j['offset']
check(raw[i:i+len(new)]==new and raw[:i]+old+raw[i+len(new):]==_parent_raw,'Exact R4 whole inverse of sole game mutation')
for row in catalog['ordered_ai_parent_manifest']['files']:
    if row['path']!=REL:check(sha(source_for_hash((CANDIDATE/row['path']).read_bytes(),row['path']))==row['candidate_sha256'],'Other thirteen game files unchanged')
report={'status':'SOURCE_AST_EXPLICIT_25_AI_WEIGHTS_PASS_NATIVE_PENDING','checks':checks,'opinion_policy_boundary_cases':1056,'arithmetic_cases':cases,'original_modifiers':25,'ordinary_modifier_predicate_visits':len(hits),'ordinary_modifier_evaluation_passes':1,'negative_ast_mutations_rejected':3,'historical_compiler_AST_full_match':True,'source_case_context':'THIS recipient3,ROOT independent2,PREV donor1','terminal_policy_no_cash_no_rng_no_retry':True,'weight_scale':1,'maximum_reference_accept_seen':max_accept,'maximum_reference_decline_seen':max_decline,'RNG_stream_identity_proven':False,'engine_rng_or_modifier_rounding_emulated':False,'native_accepted':False,'public_source_modified':False}
check(checks==3622 and cases==1236,'Actual meaningful3622 ordered AST/arithmetic checks retained')
ai_ordered_report=report
report=lifecycle_report
report['ai_ordered_weights']=ai_ordered_report
