"""Run actual current native-action, targeted-decision and lifecycle AST paths."""
from _support import *
from collections import Counter
import json

checks=Counter()
def check(ok,group):
 assert ok,group;checks[group]+=1
def c(result,actor='A'):return result['countries'][actor]
def standing(result,family,actor='A',peer='B'):
 prefix='trade_agreement' if family=='trade' else 'mutual_investment_treaty_'
 return prefix+'@'+peer in c(result,actor)['flags']
def approved(family,days=90,actor='A',peer='B'):
 result=state();check(action(result,family,actor,peer),'native dispatch')
 check(decision(result,family,'review',peer,actor),'actual recipient review')
 if days==180:
  check(decision(result,family,'counter_180',peer,actor),'actual counteroffer')
  check(decision(result,family,'review',actor,peer),'actual counterparty review')
  check(decision(result,family,'accept_180',actor,peer),'accept exact counterterms')
 else:check(decision(result,family,'accept_90',peer,actor),'accept exact initial terms')
 return result
def daily(result,day):
 result['day']=day
 for actor in IDS:hook(result,'on_daily',actor)

def ai_weight(result,family,name,actor='A',peer='B'):
 body=one(DECISIONS[P+family+'_'+name],'ai_will_do');factor=float(one(body,'factor'));context=ctx(actor,peer)
 for key,operator,data in body:
  if key=='modifier' and condition([node for node in data if node[0]!='factor'],result,context):factor*=float(one(data,'factor'))
 return factor

def status_label(result,family,field,actor='A',peer='B'):
 name=P+family+'_'+field+'_label'
 body=next(body for kind,operator,body in parse((ROOT/FILES[12]).read_text(encoding='utf-8-sig')) if one(body,'name')==name)
 for kind,operator,branch in body:
  if kind!='text':continue
  gates=[body for key,operator,body in branch if key=='trigger']
  if not gates or condition(gates[0],result,ctx(actor,peer)):return one(branch,'localization_key')
 raise AssertionError(('No status branch',name))

def others_snapshot(result):
 out=deepcopy(result['countries'])
 for country in out.values():
  country.pop('temps');country.pop('pp');country.pop('expires')
  country['flags']={flag for flag in country['flags'] if not flag.startswith(P)}
  country['variables']={key:val for key,val in country['variables'].items() if not key.startswith(P) and key!='signed_trade_agreements'}
  country['arrays']={key:val for key,val in country['arrays'].items() if not key.startswith(P) and key!='permanent_investment_targets'}
  country['opinion_modifiers']={row for row in country['opinion_modifiers'] if row[1]=='historic_friends'}
 return out

def seed_obligations(result):
 for actor,country in result['countries'].items():
  peer='C' if actor!='C' else 'D'
  country['variables'].update({'treasury':9.,'int_investments':12.5,'eon_aid_escrow':7.,'eon_energy_invoice_unpaid':3.,'eon_project_primary_investor':IDS[peer]})
  country['arrays'].update({'energy_contractors':[peer],'energy_contracts_ammount':[32.], 'energy_contracts_price':[.05],
   'project_array':[IDS[peer],2,1],'goods_deliveries':[IDS[peer],5,11], 'eon_energy_original_invoices':[17,19]})
  country['flags'].update({'trade_agreement@'+peer,'mutual_investment_treaty_@'+peer,'eon_aid_reserved'})
  country['opinion_modifiers'].add((peer,'historic_friends'))

def main():
 # Native10 reproduced these primitives in the installed engine. This prevents
 # a country-local adapter from falsely validating unreadable PREV.temp input.
 r=state();owner=ctx('A','B');peer=switch(owner,'B')
 execute(parse('set_temp_variable = { eon_private_temp_primitive = 11 }'),r,owner)
 check(value(r,peer,'eon_private_temp_primitive')==11,'native shared cross-country temp read')
 check(value(r,peer,'PREV.eon_private_temp_primitive')==0,'scoped lookup cannot read a temporary')
 execute(parse('set_temp_variable = { eon_private_temp_primitive = 22 }'),r,peer)
 check(value(r,owner,'eon_private_temp_primitive')==22,'native cross-country temp write is shared')
 check(not c(r,'A')['temps'] and not c(r,'B')['temps'],'no country-local temporary storage')
 execute(parse('set_variable = { eon_private_temp_primitive = 3 }'),r,owner)
 check(value(r,peer,'PREV.eon_private_temp_primitive')==3,'explicit lookup preserves persistent country variables')
 check(value(r,peer,'eon_private_temp_primitive')==22,'unscoped shared temp is independent of a persistent variable')
 restored=rehydrate(r)
 check(value(restored,owner,'eon_private_temp_primitive')==3,'durable round trip discards execution temporaries')
 check(not restored['execution_temps'],'no shared temporary survives durable round trip')
 r['countries']['B']['temps']['eon_private_country_fixture']=99
 check(value(r,peer,'eon_private_country_fixture')==0,'obsolete country-local fixture cannot produce a native value')
 check(value(r,owner,'B.eon_private_country_fixture')==0,'scoped lookup cannot read obsolete country-local fixture')
 # Native13 exposed clamp on absent first-agreement counters.
 # Exercise real bilateral consent with absent, corrupt-negative and positive totals.
 for initial,expected in ((None,1),(-2,1),(4,5)):
  r=state()
  for owner in ('A','B'):
   if initial is None:c(r,owner)['variables'].pop('signed_trade_agreements')
   else:c(r,owner)['variables']['signed_trade_agreements']=initial
  check(action(r,'trade'),'counter regression actual proposal')
  check(decision(r,'trade','review','B','A'),'counter regression actual review')
  check(decision(r,'trade','accept_90','B','A'),'counter regression actual consent')
  check(all(c(r,owner)['variables']['signed_trade_agreements']==expected for owner in ('A','B')),'initialize first counter without resetting other agreements')
  before=stable(r);decision(r,'trade','accept_90','B','A',True)
  check(stable(r)==before,'counter regression repeated consent is inert')
 for family in ('trade','investment'):
  F=P+family+'_'
  for actor,peer in [('A','B'),('B','A'),('A','SWI'),('SWI','A'),('ERI','A'),('A','SIN')]:
   r=state();initial={a:c(r,a)['pp'] for a in (actor,peer)}
   check(action(r,family,actor,peer),'native sender/receiver frame')
   check(c(r,actor)['pp']==initial[actor]-75 and c(r,peer)['pp']==initial[peer],'one submission payment, correct owner')
   check(var(r,family,'status',actor,peer)==1 and var(r,family,'status',peer,actor)==2,'paired directional status')
   before=stable(r)
   check(not decision(r,family,'accept_90',peer,actor),'accept blocked until actual review')
   decision(r,family,'accept_90',peer,actor,True)
   check(stable(r)==before,'forced unreviewed effect cannot accept')
   check(decision(r,family,'review',peer,actor),'review accessible to actual recipient')
   check(not decision(r,family,'accept_180',peer,actor),'wrong clause cannot accept')
   check(decision(r,family,'accept_90',peer,actor),'reviewed acceptance')
   check(standing(r,family,actor,peer) and standing(r,family,peer,actor),'bilateral standing rights')
   check(var(r,family,'notice_days',actor,peer)==90 and var(r,family,'notice_days',peer,actor)==90,'both accepted exact clause')
   check(var(r,family,'contract_epoch',actor,peer)==1 and var(r,family,'contract_epoch',peer,actor)==1,'both frozen agreement identity')
   check(len([row for row in r['external'] if row[1]=='change_influence_percentage'])==2,'two genuine influence calls witnessed')
   for owner,other in ((actor,peer),(peer,actor)):
    calls=[row for row in r['external'] if row[0]==owner and row[1]=='change_influence_percentage']
    check(calls[0][2]=={'percent_change':1.,'tag_index':IDS[other],'influence_target':IDS[owner]},'influence actual scoped arguments')
    if family=='trade':check(c(r,owner)['variables']['signed_trade_agreements']==1,'one standing trade count')
    else:check(c(r,owner)['arrays']['permanent_investment_targets']==[IDS[other]],'one standing investment target')
   before=stable(r);decision(r,family,'accept_90',peer,actor,True);decision(r,family,'review',peer,actor,True)
   check(stable(r)==before,'repeated acceptance has no result or charge')

  # Independent partner/type lanes and exact counterpart targeting.
  r=state();seed_obligations(r);baseline=others_snapshot(r)
  check(action(r,family,'A','B') and action(r,family,'A','D'),'multiple partner requests')
  other='investment' if family=='trade' else 'trade'
  check(action(r,other,'A','B'),'two independent framework types')
  check(not action(r,family,'B','A'),'cross proposal cannot overwrite pair')
  check(not decision(r,family,'review','C','A'),'third country cannot review')
  check(decision(r,family,'review','B','A') and decision(r,family,'decline','B','A'),'reviewed refusal')
  check(var(r,family,'status','A','B')==0 and var(r,family,'status','A','D')==1 and var(r,other,'status','A','B')==1,'refusal clears only its pair/type')
  check(others_snapshot(r)==baseline,'refusal preserves projects, paid advances, energy and goods')
  check(action(r,family,'A','B'),'new round after refusal')
  check(var(r,family,'epoch','A','B')==2,'new epoch after refusal')
  check(not decision(r,family,'decline','B','A'),'new refusal requires new review')
  check(decision(r,family,'withdraw','A','B'),'actual outgoing withdrawal')
  check(var(r,family,'status','A','B')==0 and var(r,family,'status','B','A')==0,'withdrawal closes matched mirror')

  # Expiry, durable round trip and stale reviewed epoch.
  r=state();check(action(r,family),'expiry dispatch');daily(r,29)
  check(var(r,family,'status')==1,'request active before 30 days')
  daily(r,30);check(var(r,family,'status')==0 and var(r,family,'status','B','A')==0,'silence expires without consent')
  check(not standing(r,family),'expiry cannot sign')
  check(action(r,family),'new request after expiry')
  c(r,'B')['variables'][F+'reviewed_epoch@A']=1
  before=stable(r);decision(r,family,'accept_90','B','A',True)
  check(stable(r)==before,'old review cannot approve later epoch')
  r=rehydrate(r);check(decision(r,family,'review','B','A'),'durable adapter state after round trip')
  check(decision(r,family,'accept_90','B','A'),'durable adapter acceptance after round trip')

  # A missing review is numerically zero; corrupt zero epochs must never turn
  # that default into approval. Execute the same real UI/effect paths.
  for mutation in ('both_zero','both_missing','both_negative','sender_missing','receiver_missing','unequal'):
   r=state();action(r,family);action(r,family,'A','D')
   other='investment' if family=='trade' else 'trade';action(r,other)
   if mutation in ('both_zero','both_negative'):
    number=0 if mutation=='both_zero' else -1
    c(r)['variables'][F+'epoch@B']=number;c(r,'B')['variables'][F+'epoch@A']=number
   if mutation in ('both_missing','sender_missing'):c(r)['variables'].pop(F+'epoch@B')
   if mutation in ('both_missing','receiver_missing'):c(r,'B')['variables'].pop(F+'epoch@A')
   if mutation=='unequal':c(r,'B')['variables'][F+'epoch@A']=2
   check(not decision(r,family,'review','B','A'),'invalid positive epoch cannot be reviewed '+mutation)
   before=stable(r);decision(r,family,'review','B','A',True);decision(r,family,'accept_90','B','A',True)
   check(stable(r)==before and not standing(r,family),'default zero review cannot sign '+mutation)
   # Even an injected explicit reviewed=0 receipt cannot replace a real review.
   c(r,'B')['variables'][F+'reviewed_epoch@A']=0;before=stable(r)
   decision(r,family,'accept_90','B','A',True);check(stable(r)==before,'explicit zero reviewed receipt cannot sign '+mutation)
   daily(r,1)
   check(var(r,family,'status','A','D')==1 and var(r,other,'status')==1,'invalid epoch cleanup preserves other pairs/types '+mutation)
  for field,number in [('round',0),('round',4),('round',-1),('kind',0),('kind',3),('terms',0),('terms',91)]:
   r=state();action(r,family)
   for owner,peer in [('A','B'),('B','A')]:c(r,owner)['variables'][F+field+'@'+peer]=number
   check(not decision(r,family,'review','B','A'),'invalid immutable request shape cannot be reviewed')
   before=stable(r);decision(r,family,'review','B','A',True);decision(r,family,'accept_90','B','A',True)
   check(stable(r)==before and not standing(r,family),'invalid immutable shape cannot force agreement')

  # Counter round changes one actual contractual term, direction and all receipts.
  r=state();action(r,family);decision(r,family,'review','B','A')
  check(decision(r,family,'counter_180','B','A'),'first counter')
  check(var(r,family,'terms','B','A')==180 and var(r,family,'round','B','A')==2 and var(r,family,'epoch','B','A')==2,'counter terms/round/epoch are frozen')
  check(var(r,family,'status','A','B')==2 and var(r,family,'status','B','A')==1,'counter reverses actual sender')
  check(not decision(r,family,'accept_180','A','B'),'counter needs new target review')
  decision(r,family,'review','A','B');check(decision(r,family,'counter_90','A','B'),'second counter')
  decision(r,family,'review','B','A');check(not decision(r,family,'counter_180','B','A'),'three round upper bound')
  check(decision(r,family,'accept_90','B','A'),'third round remains acceptable')
  check(var(r,family,'contract_epoch')==3 and c(r,'A')['pp']==450 and c(r,'B')['pp']==525,'one actual fee per sending round')

  # Status content follows actual fields and decision partner, never a universal
  # legacy prohibition on newly negotiated clauses.
  r=state();action(r,family)
  check(status_label(r,family,'clause')==P+'clause_unrecorded' and status_label(r,family,'pending')==F+'pending_90','actual new pending status branch')
  decision(r,family,'review','B','A');decision(r,family,'counter_180','B','A')
  check(status_label(r,family,'pending')==F+'pending_180' and status_label(r,family,'pending','B','A')==F+'pending_180','counter status is exact in both directions')
  decision(r,family,'review');decision(r,family,'accept_180')
  check(status_label(r,family,'clause')==P+'clause_180' and status_label(r,family,'pending')==P+'pending_none','accepted exact clause status branch')
  decision(r,family,'end_request');check(status_label(r,family,'pending')==P+'pending_end','mutual end has separate actual status')
  c(r)['variables'][F+'epoch@B']=0;c(r,'B')['variables'][F+'epoch@A']=0
  check(status_label(r,family,'pending')==P+'pending_obsolete','corrupt or expired request status is explicit')
  check(status_label(r,family,'clause','A','D')==P+'clause_unrecorded','status reads only actual selected partner')

  # The shared epoch advances beyond either surviving country record.
  r=state();c(r,'B')['variables'][F+'epoch@A']=100
  check(action(r,family),'asymmetric surviving serial send')
  check(var(r,family,'epoch')==101 and var(r,family,'epoch','B','A')==101,'new serial exceeds both sides')
  c(r,'B')['variables'][F+'reviewed_epoch@A']=100;before=stable(r)
  decision(r,family,'accept_90','B','A',True);check(stable(r)==before,'surviving old review cannot consent')

  # Fresh actual review provides the receiver's score, independent of the decision ROOT.
  r=state();c(r)['ideas'].add('EU_member');c(r,'B')['ideas'].add('EU_member');action(r,family)
  decision(r,family,'review','B','A');check(var(r,family,'reviewed_score','B','A')==-2,'receiver policy and sender relation produce actual review score')
  check(ai_weight(r,family,'accept_90','B','A')==0 and ai_weight(r,family,'counter_180','B','A')==5,'actual AI decision weight offers meaningful counterterms')
  decision(r,family,'counter_180','B','A');decision(r,family,'review','A','B')
  check(var(r,family,'reviewed_score','A','B')==3 and ai_weight(r,family,'accept_180','A','B')==8,'fresh reversed review scores exact longer clause')
  r=state();c(r)['flags'].add('italy_china_trade_deal');c(r,'B')['flags'].add('italy_china_trade_deal');c(r,'B')['government']='nationalist'
  action(r,family);decision(r,family,'review','B','A')
  expected=-22+(50 if family=='trade' else 40)-50
  check(var(r,family,'reviewed_score','B','A')==expected,'nationalist penalty applies to receiver, not ROOT sender')

  # Native retired queues can never reach the new namespace, even after re-review.
  r=approved(family);check(decision(r,family,'end_request'),'new end proposal')
  decision(r,family,'review','B','A');before=stable(r)
  oldnames=('propose_improved_trade_agreement','cancel_trade_agreement') if family=='trade' else ('propose_mutual_investment_treaty','cancel_mutual_investment_treaty')
  for name in oldnames:
   check(not condition(one(OLD[name],'visible'),r,ctx('A','B')|{'scope':'B'}),'retired identity hidden')
   check(not condition(one(OLD[name],'can_be_sent'),r,ctx('A','B')|{'scope':'B'}),'retired identity cannot send')
   old_callback(r,name,'complete_effect')
   if name.startswith('propose'):old_callback(r,name,'reject_effect')
  check(stable(r)==before,'old native accept/reject/cancel cannot touch new accepted/requested epochs')

  # Final acceptance rechecks current sender policy, recipient opinion and war.
  for mutation in ('war','opinion','sender_vanished','receiver_vanished','mirror_epoch','mirror_terms','ERI_policy'):
   actor='ERI' if mutation=='ERI_policy' else 'A';r=state();check(action(r,family,actor,'B'),'recheck dispatch');decision(r,family,'review','B',actor)
   if mutation=='war':c(r,actor)['wars'].add('B');c(r,'B')['wars'].add(actor)
   if mutation=='opinion':c(r,'B')['opinions'][actor]=0
   if mutation=='sender_vanished':c(r,actor)['exists']=False
   if mutation=='receiver_vanished':c(r,'B')['exists']=False
   if mutation=='mirror_epoch':c(r,actor)['variables'][F+'epoch@B']=90
   if mutation=='mirror_terms':c(r,actor)['variables'][F+'terms@B']=180
   if mutation=='ERI_policy':c(r,actor)['flags'].add('ETH_transitional_government_FLAG');c(r,actor)['leader']='Eritrean Transitional Government'
   before=stable(r);decision(r,family,'accept_90','B',actor,True)
   check(stable(r)==before,'final actual-source eligibility '+mutation)

  # Inherited thresholds including the Swiss/EU exception and allied existential rule.
  for threshold in ([10,50] if family=='trade' else [25]):
   for delta in (0,1):
    r=state();peer='SWI' if family=='trade' and threshold==50 else 'B';c(r,peer)['opinions']['A']=threshold+delta
    check(action(r,family,'A',peer)==bool(delta),'strict inherited opinion boundary')
  if family=='trade':
   r=state();c(r,'SWI')['opinions']['A']=11;c(r,'A')['ideas'].add('EU_member');check(action(r,family,'A','SWI'),'Swiss EU exception preserved')
  r=state();c(r,'B')['allies'].add('C');c(r,'C')['wars'].add('A')
  check(not action(r,family),'allied existential rejects when every ally is at war')
  c(r,'B')['allies'].add('D');check(action(r,family),'inherited existential permits another peaceful ally')
  for pp in (74,75):
   r=state();c(r,'A')['pp']=pp;check(action(r,family)==(pp==75),'actual fee affordability boundary')
  r=state();action(r,family);decision(r,family,'review','B','A');c(r,'B')['pp']=74
  before=stable(r);decision(r,family,'counter_180','B','A',True);check(stable(r)==before,'unaffordable forced counter preserves current request')

  # All four guarded charges require the FULL75, including fractional PP.
  # Execute actual native/targeted callbacks even when their UI is unavailable.
  for effort in (74,74.01,74.99,75,75.01,100):
   for operation in ('send','counter_180','end_request','notice'):
    r=state();actor,peer='A','B'
    if operation=='counter_180':
     assert action(r,family) and decision(r,family,'review','B','A')
     actor,peer='B','A'
    elif operation!='send':
     assert action(r,family) and decision(r,family,'review','B','A') and decision(r,family,'accept_90','B','A')
    c(r,actor)['pp']=effort;before=stable(r)
    ready=action(r,family,actor,peer,True) if operation=='send' else decision(r,family,operation,actor,peer,True)
    check(ready==(effort>=75),'full75 affordability for fractional '+operation)
    if effort<75:check(stable(r)==before,'forced fractional shortfall inert for '+operation)
    else:check(abs(c(r,actor)['pp']-(effort-75))<1e-6,'exact75 fee after fractional '+operation)

  # New contractual notice remains effective, legacy has no invented unilateral right.
  for days in (90,180):
   r=approved(family,days);seed_obligations(r);baseline=others_snapshot(r)
   prefix='trade_agreement' if family=='trade' else 'mutual_investment_treaty_'
   baseline['A']['flags'].discard(prefix+'@B');baseline['B']['flags'].discard(prefix+'@A')
   check(decision(r,family,'notice'),'actual contractual notice')
   check(standing(r,family) and flag(r,family,'notice'),'notice is not immediate termination')
   before_pp=c(r)['pp'];check(not decision(r,family,'notice'),'repeated notice blocked');check(c(r)['pp']==before_pp,'repeated notice no fee')
   daily(r,days-1);check(standing(r,family),'framework remains throughout notice')
   # Severed relations do not erase an accepted framework.
   c(r)['flags'].add('eon_diplomatic_relations_broken@B');c(r,'B')['flags'].add('eon_diplomatic_relations_broken@A')
   before=stable(r);hook(r,'on_daily');check(standing(r,family),'relations rupture does not terminate')
   c(r)['flags'].discard('eon_diplomatic_relations_broken@B');c(r,'B')['flags'].discard('eon_diplomatic_relations_broken@A')
   daily(r,days);check(not standing(r,family) and not standing(r,family,'B','A'),'exact agreed notice maturity')
   check(others_snapshot(r)==baseline,'lawful ending preserves all actual project/cash/delivery obligations')
   before=stable(r);daily(r,days+1)
   # A tick only changes day; monetary and standing records are untouched.
   previous=before|{'day':days+1};check(stable(r)==previous,'repeat maturity does not end or debit again')
  r=state();prefix='trade_agreement' if family=='trade' else 'mutual_investment_treaty_';c(r)['flags'].add(prefix+'@B');c(r,'B')['flags'].add(prefix+'@A')
  check(not decision(r,family,'notice'),'legacy has no invented 90-day right')
  check(decision(r,family,'end_request'),'legacy consensual termination request')
  check(not decision(r,family,'end_accept','B','A'),'legacy termination needs review')
  check(decision(r,family,'review','B','A') and decision(r,family,'end_accept','B','A'),'legacy actual mutual agreement')
  check(not standing(r,family) and not standing(r,family,'B','A'),'legacy bilateral ending')
  r=approved(family);c(r,'B')['variables'][F+'notice_days@A']=180
  before=stable(r);decision(r,family,'notice',force=True)
  check(stable(r)==before,'asymmetric clause cannot issue notice or take fee')
  r=approved(family);decision(r,family,'notice')
  c(r)['variables'][F+'contract_epoch@B']=99;c(r,'B')['variables'][F+'contract_epoch@A']=99
  daily(r,90)
  check(standing(r,family) and standing(r,family,'B','A'),'obsolete notice cannot end another agreement')
  check(not flag(r,family,'notice') and not flag(r,family,'notice','B','A'),'obsolete notice does not block later contractual notice')
  check(decision(r,family,'notice'),'later agreement notice remains reachable')

  # A story-signed pair makes the old offer obsolete without a rejection penalty.
  r=state();action(r,family);decision(r,family,'review','B','A')
  prefix='trade_agreement' if family=='trade' else 'mutual_investment_treaty_'
  c(r)['flags'].add(prefix+'@B');c(r,'B')['flags'].add(prefix+'@A')
  baseline=deepcopy((c(r)['opinion_modifiers'],c(r,'B')['opinion_modifiers']))
  check(decision(r,family,'decline','B','A'),'obsolete standing offer can be retired')
  check((c(r)['opinion_modifiers'],c(r,'B')['opinion_modifiers'])==baseline,'obsolete offer has no false rejection penalty')

  # New contract identity guards prevent an old reviewed termination ending a later one.
  r=approved(family);decision(r,family,'end_request');decision(r,family,'review','B','A')
  c(r)['variables'][F+'contract_epoch@B']=99;c(r,'B')['variables'][F+'contract_epoch@A']=99
  before=stable(r);decision(r,family,'end_accept','B','A',True);check(stable(r)==before,'stale early-end identity cannot end another agreement')
  r=approved(family);decision(r,family,'end_request');decision(r,family,'review','B','A')
  check(decision(r,family,'end_accept','B','A'),'consensual early end of new framework')
  check(not standing(r,family),'mutual consent can end before notice')
  check(action(r,family),'fresh contract negotiation after lawful end');decision(r,family,'review','B','A');decision(r,family,'accept_90','B','A')
  check(var(r,family,'contract_epoch')==3,'new contract gets later durable identity')

  # Legacy queue migration consumes no fees or accepted state.
  r=approved(family);seed_obligations(r)
  c(r)['variables'].update({'pending_trade_offer_country':IDS['D'],'eon_trade_treaty_pending_sender':IDS['C'],
   'pending_mutual_investment_treaty_offer':IDS['D'],'eon_investment_treaty_pending_sender':IDS['C'],'eon_investment_treaty_pending_terms':1})
  baseline=others_snapshot(r);baseline['A']['variables']={k:v for k,v in baseline['A']['variables'].items() if k not in ('pending_trade_offer_country','eon_trade_treaty_pending_sender','pending_mutual_investment_treaty_offer','eon_investment_treaty_pending_sender','eon_investment_treaty_pending_terms')}
  pp=c(r)['pp'];daily(r,1)
  check(others_snapshot(r)==baseline and c(r)['pp']==pp,'one-time migration retains accepted rights, invoices and no invented refunds')
  c(r)['variables']['pending_trade_offer_country']=IDS['C'];hook(r,'on_daily')
  check(c(r)['variables']['pending_trade_offer_country']==IDS['C'],'legacy migration runs once')

  # Annex callbacks use vanished-country scope, not the annexer.
  for callback in ('on_annex','on_subject_annexed'):
   r=approved(family);check(action(r,family,'A','D'),'third partner negotiation');decision(r,family,'review','D','A');decision(r,family,'accept_90','D','A')
   c(r,'B')['exists']=False
   if callback=='on_annex':hook(r,callback,'C','B')
   else:hook(r,callback,'B','C')
   check(not standing(r,family,'A','B') and standing(r,family,'A','D'),'annex scope preserves surviving third-party framework')

 print(json.dumps({'package':28,'scenario_assertions':sum(checks.values()),'groups':dict(checks),'all_passed':True,
  'source_sha256':hashes(),'native_campaign_proven':False,'native_save_load_proven':False,'multiplayer_proven':False,
  'external_macros':'influence and Singapore recalculation are witnessed with actual call scopes and parameters, not simulated'}))

if __name__=='__main__':main()
