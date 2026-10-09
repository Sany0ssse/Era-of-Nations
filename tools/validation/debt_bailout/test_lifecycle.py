"""Run actual current decision/option/helper AST; supplied clock is not native proof."""
from copy import deepcopy
import hashlib
import json
import model as b
from model import m

cases = 0
def check(condition, detail):
    assert condition, detail
def near(a, wanted): check(abs(a-wanted)<1e-9,(a,wanted))
def closed(s,*peers):
    for peer in peers:
        d=s['countries'][peer]
        check('eon_debt_bailout_reserved' not in d['flags'], ('Still reserved',peer))
        for field in ('partner','kind','generation','amount','autonomy_terms'):
            check(d['vars'].get('eon_debt_bailout_'+field,0)==0,field)
def finances(s): return [(d['vars']['treasury'],d['vars']['debt']) for d in s['countries'].values()]

# Original IDs are safe even if a save still has an old queued response/news.
for ident in ('bankruptcy.1','bankruptcy.2','bankruptcy.3','bankruptcy.4','bankruptcy.5',
              'News_bankruptcy.1','News_bankruptcy.2','News_bankruptcy.3'):
    for k,o,option in b.EVENTS[ident]:
        if k!='option': continue
        s=b.state(); s['countries'][1]['vars']['debt_bailout']=37
        s['countries'][2]['vars']['debt_bailout']=91
        before=finances(s)
        b.execute(option,s,m.context(2,1))
        check(finances(s)==before,(ident,'Legacy financial mutation'))
        check(s['countries'][1]['vars']['debt_bailout']==37 and s['countries'][2]['vars']['debt_bailout']==91,(ident,'IMF field altered'))
        check('eon_debt_bailout_legacy_unresolved' in s['countries'][2]['flags'],ident)
        check(not s['events'],ident); cases+=1

fractions=(.20,.15,.10,.50)
for borrower,donor in ((1,2),(2,3),(3,1)):
    for kind in range(1,5):
        for debt in (100,.25,1):
            s=b.state(kind,debt,100,borrower,donor); b.prepare(s,kind,borrower,donor)
            amount=debt*fractions[kind-1]
            for peer in (borrower,donor): near(s['countries'][peer]['vars']['eon_debt_bailout_amount'],amount)
            check(s['events']==[{'id':f'eon_debt_bailout.{kind}','target':donor,'sender':borrower}],s['events'])
            near(s['countries'][borrower]['vars']['political_power'],450)
            check(finances(s)[borrower-1]==(0,debt),'Prepare must not charge cash')
            b.respond(s,kind,borrower,donor)
            near(s['countries'][donor]['vars']['treasury'],100-amount)
            near(s['countries'][borrower]['vars']['debt'],debt-amount)
            near(s['countries'][borrower]['vars']['treasury'],0)
            near(s['countries'][donor]['vars']['debt'],0)
            for peer in (borrower,donor): near(s['countries'][peer]['vars']['eon_debt_bailout_last_payment'],amount)
            check(s.get('autonomy_calls',[])==([(borrower,-.35)] if kind==4 else []),s.get('autonomy_calls'))
            closed(s,borrower,donor)
            before=finances(s)
            b.invoke(s,'eon_debt_bailout_accept',donor,borrower,{'eon_debt_bailout_response_kind':kind})
            check(finances(s)==before,'Repeated callback charged twice'); cases+=1

# Settlement re-reads current debt and donor liquidity; the offer ceiling is frozen.
for kind in range(1,5):
    for remaining,cash,payment in ((5,5,5),(5,4.999,0),(0,100,0),(100,100,100*fractions[kind-1]),(100,0,0),(100,-1,0)):
        s=b.state(kind); b.prepare(s,kind)
        s['countries'][1]['vars']['debt']=remaining; s['countries'][2]['vars']['treasury']=cash
        b.respond(s,kind)
        near(s['countries'][2]['vars']['treasury'],cash-payment)
        near(s['countries'][1]['vars']['debt'],remaining-payment)
        near(s['countries'][2]['vars']['eon_debt_bailout_last_payment'],payment)
        closed(s,1,2); cases+=1
    for reason in ('refuse','cancel','expire','war','role_lost'):
        s=b.state(kind); b.prepare(s,kind); before=finances(s)
        if reason=='cancel': b.invoke(s,'eon_debt_bailout_cancel',1)
        elif reason=='expire':
            s['countries'][1]['flags'].remove('eon_debt_bailout_response_window')
            b.invoke(s,'eon_debt_bailout_maintenance',1)
        elif reason=='war': s['countries'][2]['wars'].add(1)
        elif reason=='role_lost': s['countries'][1]['overlord']=3 if kind==4 else 2
        b.prepare(s,kind)
        check(len(s['events'])==1,'Cancelled modal prematurely releases locks')
        b.respond(s,kind,accept=reason!='refuse')
        check(finances(s)==before,(kind,reason,'Invalid response transferred'))
        closed(s,1,2); cases+=1

# A reserved donor cannot silently accept a concurrent different borrower.
s=b.state(); b.prepare(s); snapshot=deepcopy(s)
b.prepare(s); check(s['events']==snapshot['events'],'Duplicate popup')
s['countries'][3]['vars']['debt']=100; s['countries'][3]['arrays']['influence_array'][0]=2
b.invoke(s,'eon_debt_bailout_prepare',3,temps={'eon_debt_bailout_donor':2,'eon_debt_bailout_offer_kind':1})
check(s['countries'][2]['vars']==snapshot['countries'][2]['vars'],'Occupied donor overwritten')
check('eon_debt_bailout_reserved' not in s['countries'][3]['flags'],'Third borrower reserved')
b.respond(s,accept=False); b.prepare(s)
check(s['countries'][1]['vars']['eon_debt_bailout_generation']==2,'Legitimate second request blocked')
before=deepcopy([d['vars'] for d in s['countries'].values()])
for ident in ('eon_debt_bailout.10','eon_debt_bailout.11','eon_debt_bailout.12','bankruptcy.4','News_bankruptcy.1'):
    for k,o,v in b.EVENTS[ident]:
        if k=='option': b.execute(v,s,m.context(1,2))
check([d['vars'] for d in s['countries'].values()]==before,'Delayed notice erased new request'); cases+=1

for mutation in ('wrong_from','wrong_donor','wrong_kind','generation','amount','partner'):
    s=b.state(); b.prepare(s); actor=2; sender=1; kind=1
    if mutation=='wrong_from': sender=3
    elif mutation=='wrong_donor': actor=3
    elif mutation=='wrong_kind': kind=2
    else: s['countries'][2]['vars']['eon_debt_bailout_'+mutation]=77
    before=deepcopy(s)
    b.invoke(s,'eon_debt_bailout_accept',actor,sender,{'eon_debt_bailout_response_kind':kind})
    check([d for d in s['countries'].values()]==[d for d in before['countries'].values()],mutation)
    check(s['events']==before['events'],mutation); cases+=1

for dead in (1,2):
    s=b.state(); b.prepare(s); s['countries'][dead]['exists']=False
    b.invoke(s,'eon_debt_bailout_maintenance',3-dead)
    closed(s,1,2)
    check('eon_debt_bailout_retired_pair@2' in s['countries'][1]['flags'],'Borrower retirement absent')
    check('eon_debt_bailout_retired_pair@1' in s['countries'][2]['flags'],'Donor retirement absent')
    s['countries'][dead]['exists']=True; before=finances(s); queued=deepcopy(s['events'])
    b.prepare(s); check(s['events']==queued,'Revival reused retired modal pair')
    b.invoke(s,'eon_debt_bailout_accept',2,1,{'eon_debt_bailout_response_kind':1})
    check(finances(s)==before,'Dead/revived stale response paid')
    b.invoke(s,'eon_debt_bailout_prepare',1,temps={'eon_debt_bailout_donor':3,'eon_debt_bailout_offer_kind':3})
    check(s['countries'][1]['vars'].get('eon_debt_bailout_partner')==3,'Global ban replaced exact-pair retirement'); cases+=1

for debt in (0,-1):
    s=b.state(debt=debt); before=deepcopy(s['countries']); b.prepare(s)
    check(s['countries']==before and not s['events'],'Nonpositive debt charged PP'); cases+=1
for kind in (0,1.5,2.5,4.5,5):
    s=b.state(); before=deepcopy(s['countries'])
    b.invoke(s,'eon_debt_bailout_prepare',1,temps={'eon_debt_bailout_donor':2,'eon_debt_bailout_offer_kind':kind})
    check(s['countries']==before and not s['events'],('Invalid enum',kind)); cases+=1

# The real decision predicates preserve national restrictions and donor selection.
for kind in range(1,5):
    s=b.state(kind); c=m.context(1,2 if kind==3 else 1); decision=b.DECISIONS[b.ROUTES[kind-1]]
    if any(k=='visible' for k,o,v in decision): check(b.trigger(m.one(decision,'visible'),s,c),(kind,'Visible'))
    if kind==3: check(b.trigger(m.one(decision,'target_trigger'),s,c),'Neighbor target')
    check(b.trigger(m.one(decision,'available'),s,c),(kind,'Actual decision disabled'))
    s['countries'][2]['wars'].add(1)
    check(not b.trigger(m.one(decision,'available'),s,c),(kind,'War availability bypass')); cases+=1
    s=b.state(kind); b.prepare(s,kind); s['countries'][2]['vars']['eon_debt_bailout_kind']=1.5
    b.invoke(s,'eon_debt_bailout_maintenance',1)
    closed(s,1,2); check(finances(s)[0]==(0,100),'Corrupt kind paid'); cases+=1

# Missing receipt key never attempts a country scope at zero; its reciprocal
# survivor retires the old pair before any later popup could be interpreted.
s=b.state(); b.prepare(s); s['countries'][1]['vars']['eon_debt_bailout_partner']=0
b.invoke(s,'eon_debt_bailout_maintenance',1); closed(s,1)
b.invoke(s,'eon_debt_bailout_maintenance',2); closed(s,1,2)
check('eon_debt_bailout_retired_pair@2' in s['countries'][1]['flags'],'Missing-key retirement'); cases+=1

onactions=m.one(m.ast(m.read('common/on_actions/eon_debt_bailout_on_actions.txt')),'on_actions')
for hook,annexed,actor,sender in (('on_annex',1,4,1),('on_annex',2,4,2),
                                   ('on_subject_annexed',1,1,2),('on_subject_annexed',2,2,4)):
    s=b.state(); b.prepare(s); s['countries'][annexed]['exists']=False
    b.execute(m.one(m.one(onactions,hook),'effect'),s,m.context(actor,sender))
    closed(s,1,2)
    check('eon_debt_bailout_retired_pair@2' in s['countries'][1]['flags'] and
          'eon_debt_bailout_retired_pair@1' in s['countries'][2]['flags'],hook)
    check(finances(s)[0]==(0,100) and finances(s)[1]==(100,0),'Annex financial mutation'); cases+=1

s=b.state(); b.prepare(s); d=b.DECISIONS['eon_debt_bailout_withdraw_request']
check(b.trigger(m.one(d,'available'),s,m.context(1)),'Withdraw inaccessible')
b.execute(m.one(d,'complete_effect'),s,m.context(1))
check('eon_debt_bailout_reserved' in s['countries'][1]['flags'],'Withdraw released queued modal')
check(not b.trigger(m.one(d,'available'),s,m.context(1)),'Repeated withdraw enabled'); cases+=1

# Native40 observed available evaluation entering overlord even for an
# independent country. Do not silently treat an invalid scope as false/no-op.
# These wrappers follow actual executed branches, including guarded if/else;
# they do not traverse inactive branches or change financial predicates.
ordinary_trigger, ordinary_execute = b.trigger, b.execute

def strict_overlord_trigger(nodes, s, c):
    for group in b.groups(nodes):
        if group[0][0] == 'overlord':
            check(s['countries'][c['scope']].get('overlord') in s['countries'],
                  ('Invalid overlord trigger traversal', c['scope']))
        if not ordinary_trigger(group, s, c): return False
    return True

def strict_overlord_execute(nodes, s, c):
    for group in b.groups(nodes):
        if group[0][0] == 'overlord':
            check(s['countries'][c['scope']].get('overlord') in s['countries'],
                  ('Invalid overlord effect traversal', c['scope']))
        ordinary_execute(group, s, c)

def check_independent_overlord(decision, callback, borrower=1, donor=2, stale=3):
    s=b.state(4, borrower=borrower, donor=donor)
    s['countries'][borrower]['overlord']=None
    s['temp']={'eon_debt_bailout_donor':stale}
    before=deepcopy(s['countries'])
    c=m.context(borrower,borrower)
    if callback=='available':
        check(not b.trigger(m.one(decision,callback),s,c),'Independent route enabled')
    else:
        b.execute(m.one(decision,callback),s,c)
    check(s['temp'].get('eon_debt_bailout_donor')==0,'Stale donor was not reset')
    check(s['countries']==before and not s['events'],
          ('Independent callback changed finances, PP or receipts',callback))

overlord_scope_mutants=0
try:
    b.trigger=m.trigger=strict_overlord_trigger
    b.execute=m.execute=strict_overlord_execute
    decision=b.DECISIONS[b.ROUTES[3]]
    for borrower,donor in ((1,2),(2,3),(3,1)):
        for callback in ('available','complete_effect'):
            for stale in (donor,4):
                check_independent_overlord(decision,callback,borrower,donor,stale)
                cases+=1
        s=b.state(4,borrower=borrower,donor=donor)
        s['temp']={'eon_debt_bailout_donor':4}; c=m.context(borrower,borrower)
        check(b.trigger(m.one(decision,'available'),s,c),'Valid subject route unavailable')
        near(s['temp']['eon_debt_bailout_donor'],donor)
        b.execute(m.one(decision,'complete_effect'),s,c)
        check(s['events']==[{'id':'eon_debt_bailout.4','target':donor,'sender':borrower}],
              'Actual overlord event frame changed')
        near(s['countries'][borrower]['vars']['political_power'],450)
        near(s['countries'][borrower]['vars']['eon_debt_bailout_amount'],50)
        near(s['countries'][donor]['vars']['eon_debt_bailout_amount'],50)
        cases+=1
    # Reintroduce each old unguarded body or omit its fresh input reset.
    for callback in ('available','complete_effect'):
        for mutation in ('unguarded_scope','missing_donor_reset'):
            bad=deepcopy(decision); nodes=m.one(bad,callback)
            if mutation=='unguarded_scope':
                body=m.one(nodes,'if')
                nodes[:]=[nodes[0]]+[n for n in body if n[0]!='limit']
            else:
                check(nodes[0][0]=='set_temp_variable','Donor reset missing from current AST')
                nodes.pop(0)
            try: check_independent_overlord(bad,callback)
            except AssertionError: overlord_scope_mutants+=1
            else: raise AssertionError(('Overlord scope mutant accepted',callback,mutation))
finally:
    b.trigger=m.trigger=ordinary_trigger
    b.execute=m.execute=ordinary_execute

# Mutate actual AST in memory only: each guard prevents a concrete bad transfer.
def remove_once(nodes,predicate):
    for index,node in enumerate(nodes):
        k,o,v=node
        if predicate(node): nodes.pop(index); return True
        if isinstance(v,list) and remove_once(v,predicate): return True
    return False
mutants=0
for mutation in ('debt_bound','cash_check','sovereignty','donor_war','response_generation','response_amount','response_kind'):
    s=b.state(); b.prepare(s); table=m.triggers
    name='eon_debt_bailout_pair_current' if mutation in ('response_generation','response_amount') else 'eon_debt_bailout_response_current' if mutation=='response_kind' else 'eon_debt_bailout_payment_ready'
    old=table[name]; bad=deepcopy(old)
    if mutation=='debt_bound':
        predicate=lambda n:n[0]=='clamp_temp_variable'
        s['countries'][1]['vars']['debt']=5
    elif mutation=='cash_check':
        predicate=lambda n:n[0]=='check_variable' and any(q[0]=='var' and q[2]=='treasury' for q in n[2])
        s['countries'][2]['vars']['treasury']=19
    elif mutation=='sovereignty':
        predicate=lambda n:n[0]=='is_subject'
        s['countries'][1]['overlord']=2
    elif mutation=='donor_war':
        predicate=lambda n:n[0]=='NOT' and any(q[0]=='has_war_with' and q[2]=='var:eon_debt_bailout_partner' for q in n[2])
        s['countries'][2]['wars'].add(1)
    else:
        field={'response_generation':'generation','response_amount':'amount','response_kind':'kind'}[mutation]
        predicate=lambda n:n[0]=='check_variable' and any(q[0]=='eon_debt_bailout_'+field and q[2]==('eon_debt_bailout_response_kind' if field=='kind' else 'PREV.eon_debt_bailout_'+field) for q in n[2])
        if field!='kind': s['countries'][2]['vars']['eon_debt_bailout_'+field] = 2 if field=='generation' else 99
    # The source itself rejects or bounds the scenario before the mutant is used.
    before=finances(s); source_case=deepcopy(s)
    expected_kind=2 if mutation=='response_kind' else 1
    b.invoke(source_case,'eon_debt_bailout_accept',2,1,{'eon_debt_bailout_response_kind':expected_kind})
    if mutation=='debt_bound': near(source_case['countries'][1]['vars']['debt'],0)
    else: check(finances(source_case)==before,('Current guard failed',mutation))
    check(remove_once(bad,predicate),('Mutant predicate absent',mutation))
    try:
        table[name]=bad
        b.invoke(s,'eon_debt_bailout_accept',2,1,{'eon_debt_bailout_response_kind':expected_kind})
        if mutation=='debt_bound': check(s['countries'][1]['vars']['debt']<0,'Over-relief mutant undetected')
        else: check(finances(s)!=before,('Mutation did not expose failure',mutation))
        mutants+=1
    finally: table[name]=old

paths=('common/decisions/bankruptcy_decisions.txt','events/00_Econ_events.txt',
       'common/scripted_effects/eon_debt_bailout_effects.txt','common/scripted_triggers/eon_debt_bailout_triggers.txt',
       'events/eon_debt_bailout_events.txt','common/on_actions/eon_debt_bailout_on_actions.txt')
print(json.dumps({'passed':cases,'actual_AST_financial_mutants_rejected':mutants,
                  'actual_AST_overlord_scope_mutants_rejected':overlord_scope_mutants,
                  'source_hashes':{p:hashlib.sha256((b.ROOT/p).read_bytes()).hexdigest() for p in paths},
                  'native_popup_consumption_verified':False,'native_autonomy_verified':False,
                  'economy_refresh_emulated':False},ensure_ascii=False,indent=2))
