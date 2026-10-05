"""Execute actual changed source branches symbolically, not the HOI4 engine.

Country variables persist; temporary variables use one shared effect environment.
GUI controls, bilateral arrays, event callbacks and money loops are read from source.
"""
from pathlib import Path
from copy import deepcopy
import re, json, hashlib

from _support import ROOT, baseline
TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
def ast(text):
    tokens=[m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff')) if not m[0].startswith('#')]; n=0
    def parse():
        nonlocal n
        result=[]
        while n<len(tokens) and tokens[n]!='}':
            key=tokens[n]; n+=1
            if n>=len(tokens) or tokens[n] not in ('=','<','>','<=','>=','!=','=='):
                result.append(('__item__','=',key)); continue
            op=tokens[n]; n+=1
            if tokens[n]=='{':
                n+=1; val=parse(); assert tokens[n]=='}'; n+=1
            else: val=tokens[n]; n+=1
            result.append((key,op,val))
        return result
    result=parse(); assert n==len(tokens),(n,len(tokens)); return result
def one(nodes,key):
    found=[v for k,o,v in nodes if k==key]; assert len(found)==1,(key,len(found)); return found[0]
def get_gui(nodes):
    return one(one(one(nodes,'scripted_gui'),'energy_scripted_gui'),'effects')
def get_event_map(text):
    nodes=ast(text)
    return {one(v,'id'):v for k,o,v in nodes if k=='country_event'}

effects={k:v for k,o,v in ast((ROOT/'common/scripted_effects/eon_energy_contract_effects.txt').read_text(encoding='utf-8-sig'))}
framework_effects_path=ROOT/'common/scripted_effects/eon_energy_framework_effects.txt'
if framework_effects_path.exists():
    effects.update({k:v for k,o,v in ast(framework_effects_path.read_text(encoding='utf-8-sig'))})
gui=get_gui(ast((ROOT/'common/scripted_guis/01_energy_gui.txt').read_text(encoding='utf-8-sig')))
confirm=one(gui,'confirm_energy_sell_click')
events=get_event_map((ROOT/'events/00_Energy_market_events.txt').read_text(encoding='utf-8-sig'))
options={one(v,'name'):v for key,ev in events.items() if key in ('energy_selling.1','energy_selling.2','energy_selling.3','energy_selling.4','energy_selling.5') for k,o,v in ev if k=='option'}

def context(root,from_=None,scope=None,previous=()): return {'root':root,'from':from_,'scope':scope or root,'previous':previous}
def switch(c,scope): return {**c,'scope':scope,'previous':(c['scope'],)+c['previous']}
def country_ref(s,c,name):
    if name.startswith('var:'): return value(s,c,name[4:])
    if name in ('ROOT','FROM','THIS','PREV'):
        return {'ROOT':c['root'],'FROM':c['from'],'THIS':c['scope'],'PREV':c['previous'][0] if c['previous'] else None}[name]
    if name.startswith('PREV.'):
        return country_ref(s,switch(c,c['previous'][0]),name[5:])
    if name in s['countries']: return name
    return value(s,c,name)
def flag_name(s,c,name):
    if '@' not in name: return name
    key,target=name.split('@',1); return key+'@'+str(country_ref(s,c,target))
def value(s,c,expr):
    try: return float(expr)
    except (TypeError,ValueError): pass
    if expr in ('ROOT','FROM','THIS','PREV') or expr.startswith('var:'): return country_ref(s,c,expr)
    if expr in s['countries']: return expr
    if expr=='id': return c['scope']
    if '.' in expr:
        head,tail=expr.split('.',1)
        if head in ('ROOT','FROM','THIS','PREV') or head in s['countries']:
            return value(s,switch(c,country_ref(s,c,head)),tail)
    if '^' in expr:
        name,index=expr.split('^',1); ar=s['countries'][c['scope']]['arrays'].get(name,[])
        if index=='num': return len(ar)
        idx=int(value(s,c,index)); return ar[idx] if 0<=idx<len(ar) else 0
    if expr in s['temp']: return s['temp'][expr]
    return s['countries'][c['scope']]['variables'].get(expr,0)
def compare(left,op,right):
    if op in ('=','=='): return abs(left-right)<1e-8 if isinstance(left,(float,int)) and isinstance(right,(float,int)) else left==right
    if op=='!=': return not compare(left,'=',right)
    return {'>':lambda:left>right,'<':lambda:left<right,'>=':lambda:left>=right,'<=':lambda:left<=right}[op]()
def trigger(nodes,s,c):
    country=s['countries'][c['scope']]
    result=[]
    for k,o,v in nodes:
        if k=='NOT': passed=not trigger(v,s,c)
        elif k=='OR': passed=any(trigger([n],s,c) for n in v)
        elif k=='AND': passed=trigger(v,s,c)
        elif k=='check_variable':
            if len(v)==1:
                var,op,comp=v[0]; passed=compare(value(s,c,var),op,value(s,c,comp))
            else:
                d={a:z for a,b,z in v}; op={'less_than_or_equals':'<=','greater_than_or_equals':'>=','less_than':'<','greater_than':'>'}[d['compare']]
                passed=compare(value(s,c,d['var']),op,value(s,c,d['value']))
        elif k=='is_in_array':
            d={a:z for a,b,z in v}; passed=value(s,c,d['value']) in country['arrays'].get(d['array'],[])
        elif k=='has_country_flag': passed=flag_name(s,c,v) in country['flags']
        elif k=='has_variable': passed=v in country['variables']
        elif k=='tag': passed=c['scope']==country_ref(s,c,v)
        elif k=='is_ai': passed=country['ai']==(v=='yes')
        elif k=='exists': passed=country['exists']==(v=='yes')
        elif k=='has_war_with': passed=country_ref(s,c,v) in country['wars']
        elif k in ('ROOT','FROM','PREV','THIS') or k.startswith('var:') or k in s['countries']:
            target=country_ref(s,c,k); passed=target in s['countries'] and trigger(v,s,switch(c,target))
        else: raise AssertionError(('Unhandled trigger',k,o,v))
        result.append(passed)
    return all(result)
def execute(nodes,s,c):
    i=0
    while i<len(nodes):
        k,o,v=nodes[i]; i+=1; country=s['countries'][c['scope']]
        if k=='if':
            branches=[v]
            while i<len(nodes) and nodes[i][0] in ('else_if','else'): branches.append(nodes[i][2]); i+=1
            for branch in branches:
                lim=[x[2] for x in branch if x[0]=='limit']
                if not lim or trigger(lim[0],s,c): execute([x for x in branch if x[0]!='limit'],s,c); break
        elif k in effects:
            if k=='eon_energy_framework_cleanup_annexed_pair':
                s.setdefault('framework_cleanup_calls',[]).append((c['scope'],value(s,c,'eon_energy_pair_partner')))
            execute(effects[k],s,c)
        elif k in ('ROOT','FROM','PREV','THIS') or k.startswith('var:') or k in s['countries']:
            target=country_ref(s,c,k)
            if target in s['countries']: execute(v,s,switch(c,target))
        elif k in ('set_variable','set_temp_variable','add_to_variable','add_to_temp_variable','multiply_variable','multiply_temp_variable','subtract_from_variable','subtract_from_temp_variable'):
            temp='temp_variable' in k; dest=s['temp'] if temp else country['variables']
            key,_,rhs=v[0]
            if isinstance(rhs,list):
                total=0
                for op,_,val in rhs:
                    operand=value(s,c,val)
                    if op=='value': total=operand
                    elif op=='multiply': total*=operand
                    elif op=='add': total+=operand
                    else: raise AssertionError(('Unhandled math',op))
                rhs=total
            else: rhs=value(s,c,rhs)
            current=dest.get(key,0)
            if k.startswith('set_'): dest[key]=rhs
            elif k.startswith('add_'): dest[key]=current+rhs
            elif k.startswith('multiply_'): dest[key]=current*rhs
            else: dest[key]=current-rhs
        elif k=='clear_variable': country['variables'].pop(v,None)
        elif k=='set_country_flag':
            name=v if isinstance(v,str) else one(v,'flag'); country['flags'].add(flag_name(s,c,name))
        elif k=='clr_country_flag': country['flags'].discard(flag_name(s,c,v))
        elif k=='add_to_array':
            d={a:z for a,b,z in v}; country['arrays'].setdefault(d['array'],[]).append(value(s,c,d['value']))
        elif k=='remove_from_array':
            d={a:z for a,b,z in v}; ar=country['arrays'].setdefault(d['array'],[])
            if 'index' in d:
                ix=int(value(s,c,d['index'])); assert 0<=ix<len(ar),('Bad removal index',c['scope'],d['array'],ix,len(ar)); ar.pop(ix)
            else:
                val=value(s,c,d['value']);
                if val in ar: ar.remove(val)
        elif k=='clear_array': country['arrays'][v]=[]
        elif k=='for_each_loop':
            d={a:z for a,b,z in v if a in ('array','value','index','break')}; ar=list(country['arrays'].get(d['array'],[]))
            for ix,element in enumerate(ar):
                s['temp'][d['value']]=element
                if 'index' in d: s['temp'][d['index']]=ix
                execute([x for x in v if x[0] not in d],s,c)
                if 'break' in d and s['temp'].get(d['break'],0): break
        elif k=='while_loop_effect':
            lim=one(v,'limit'); count=0
            while trigger(lim,s,c):
                count+=1; assert count<100,'Loop failed to terminate'
                execute([x for x in v if x[0]!='limit'],s,c)
        elif k=='every_other_country':
            for target,data in s['countries'].items():
                if target!=c['scope'] and data['exists']: execute(v,s,switch(c,target))
        elif k=='country_event': s['events'].append({'target':c['scope'],'id':v if isinstance(v,str) else one(v,'id'),'from':c['root']})
        elif k=='ingame_update_setup': s['recalculations'].append(c['scope'])
        elif k=='update_energy_dirty_variable': s['ui_updates']+=1
        elif k=='remove_opinion_modifier':
            # Membership/opinion validation belongs to the full action tests.
            s.setdefault('removed_opinions',[]).append((c['scope'],v))
        elif k in ('log','name','ai_chance','custom_effect_tooltip'): pass
        else: raise AssertionError(('Unhandled effect',k,o,v))

def state():
    return {'countries':{c:{'variables':{},'arrays':{'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]},'flags':set(),'wars':set(),'exists':True,'ai':False} for c in ('A','B','C','D')},'temp':{},'events':[],'recalculations':[],'ui_updates':0}
def framework(s,a,b):
    s['countries'][a]['flags'].add('energy_agreement@'+b); s['countries'][b]['flags'].add('energy_agreement@'+a)
def record(s,a,b,amount,price):
    ar=s['countries'][a]['arrays']; ar['energy_contractors'].append(b); ar['energy_contracts_ammount'].append(amount); ar['energy_contracts_price'].append(price)
def pair(s,a,b,amount,price): record(s,a,b,amount,price); record(s,b,a,-amount,price)
def propose(s,a,b,amount,price):
    s['countries'][a]['variables'].update(energy_selling_selected_TAG=b,temp_energy_ammount=amount,temp_energy_price=price)
    s['temp']={}; execute(confirm,s,context(a))
def response(s,recipient,sender,accept=True):
    amount=s['countries'][recipient]['variables'].get('eon_energy_offer_amount',0)
    event='energy_selling.1' if amount>0 else 'energy_selling.4'
    s['temp']={}; execute(options[event+('.a' if accept else '.b')],s,context(recipient,sender))
def snapshot_arrays(s): return {c:deepcopy(d['arrays']) for c,d in s['countries'].items()}
def locked(s,c): return 'question_about_contract' in s['countries'][c]['flags']
def assert_pair(s,a,b,amount,price):
    for country,partner,qty in ((a,b,amount),(b,a,-amount)):
        ar=s['countries'][country]['arrays']; ids=[i for i,v in enumerate(ar['energy_contractors']) if v==partner]
        assert len(ids)==1,(country,ids,ar); i=ids[0]
        assert compare(ar['energy_contracts_ammount'][i],'=',qty) and compare(ar['energy_contracts_price'][i],'=',price)
def money(s):
    # Execute the actual existing weekly payment calculation, not a copied model.
    src=(ROOT/'common/scripted_effects/00_money_system.txt').read_text(encoding='utf-8-sig')
    section=src.split('########ENERGY SELLING SYSTEM###########',1)[1].split('#Propaganda Medrese',1)[0]
    parsed=ast(section)
    for country in s['countries']:
        s['temp']={}; execute(parsed,s,context(country))
    return {c:(d['variables'].get('energy_selling_income',0),d['variables'].get('energy_buying_expenses',0)) for c,d in s['countries'].items()}

cases=[]
for signed in (-12,12):
    for old in (None,(-8,0.03),(8,0.03)):
        for accept in (False,True):
            s=state(); framework(s,'A','B'); pair(s,'A','C',-2,0.1)
            if old: pair(s,'A','B',*old)
            before=snapshot_arrays(s); propose(s,'A','B',signed,0.06)
            assert snapshot_arrays(s)==before,'Proposing/revising must not change active records'
            assert locked(s,'A') and locked(s,'B')
            assert s['countries']['A']['variables']['eon_energy_offer_weekly']==0.72
            # Mutable GUI values and selected country change while event waits.
            s['countries']['A']['variables'].update(temp_energy_ammount=999,temp_energy_price=999,energy_selling_selected_TAG='D')
            response(s,'B','A',accept)
            assert not locked(s,'A') and not locked(s,'B')
            if accept: assert_pair(s,'A','B',signed,0.06)
            else: assert snapshot_arrays(s)==before
            assert s['countries']['A']['arrays']['energy_contractors'].count('C')==1
            active=snapshot_arrays(s); response(s,'B','A',accept)
            assert snapshot_arrays(s)==active,'Replaying finalized response must have no active effects'
            cases.append(f'new/revision old={old} amount={signed} accept={accept}')

# Retry from either side, zero price, rejection and then revised re-submission.
for sender,recipient in (('A','B'),('B','A')):
    s=state(); framework(s,'A','B'); pair(s,'A','B',-5,0.04)
    propose(s,sender,recipient,7,0); response(s,recipient,sender,False)
    assert_pair(s,'A','B',-5,0.04)
    propose(s,sender,recipient,8,0.05); response(s,recipient,sender)
    assert_pair(s,sender,recipient,8,0.05)
    cases.append('reject then counterparty/initiator retry '+sender)

# Concurrent GUI sends must not overwrite either involved country's snapshots.
s=state(); framework(s,'A','B'); framework(s,'A','C'); framework(s,'C','B')
propose(s,'A','B',-6,0.07)
fixed={c:deepcopy(s['countries'][c]['variables']) for c in ('A','B')}
propose(s,'A','C',-9,0.08); propose(s,'C','B',-9,0.08)
for c in ('A','B'):
    assert {k:v for k,v in s['countries'][c]['variables'].items() if k.startswith('eon_')}=={k:v for k,v in fixed[c].items() if k.startswith('eon_')}
response(s,'B','A'); assert_pair(s,'A','B',-6,0.07)
cases.append('shared-country concurrent sends rejected before snapshots change')

# Delayed acknowledgement of an older response cannot unlock a newer negotiation.
for eid in ('energy_selling.2.a','energy_selling.3.a','energy_selling.5.a'):
    s=state(); framework(s,'A','B'); framework(s,'A','C')
    propose(s,'A','B',-6,0.07); response(s,'B','A')
    propose(s,'A','C',-2,0.03); frozen=deepcopy(s['countries'])
    execute(options[eid],s,context('A','B'))
    assert s['countries']==frozen and locked(s,'A') and locked(s,'C')
    cases.append('old acknowledgement preserves new negotiation '+eid)

# Active record/framework/liveness/war changes invalidate acceptance without restoration.
for alteration in ('receiver record removed','sender record removed','receiver price changed','sender price changed','framework cancelled','annex sender','annex recipient','direct war','pending mirror changed','misaligned arrays','duplicate record'):
    s=state(); framework(s,'A','B'); pair(s,'A','B',-8,0.03); propose(s,'A','B',-12,0.06)
    if alteration=='receiver record removed':
        for key in s['countries']['B']['arrays']: s['countries']['B']['arrays'][key]=[]
    elif alteration=='sender record removed':
        for key in s['countries']['A']['arrays']: s['countries']['A']['arrays'][key]=[]
    elif alteration=='receiver price changed': s['countries']['B']['arrays']['energy_contracts_price'][0]=0.08
    elif alteration=='sender price changed': s['countries']['A']['arrays']['energy_contracts_price'][0]=0.08
    elif alteration=='framework cancelled': s['countries']['A']['flags'].discard('energy_agreement@B')
    elif alteration=='annex sender': s['countries']['A']['exists']=False
    elif alteration=='annex recipient': s['countries']['B']['exists']=False
    elif alteration=='direct war': s['countries']['B']['wars'].add('A')
    elif alteration=='pending mirror changed': s['countries']['A']['variables']['eon_energy_offer_amount']=-14
    elif alteration=='misaligned arrays': s['countries']['B']['arrays']['energy_contracts_price'].append(0.07)
    elif alteration=='duplicate record': record(s,'B','A',8,0.03)
    before=snapshot_arrays(s); response(s,'B','A'); assert snapshot_arrays(s)==before
    assert not locked(s,'A') and not locked(s,'B')
    cases.append('acceptance invalidated: '+alteration)

# Frozen asymmetric records are replaced symmetrically only after acceptance.
for existing in ('sender only','receiver only','different amount/price'):
    s=state(); framework(s,'A','B')
    if existing!='receiver only': record(s,'A','B',-8,0.03)
    if existing!='sender only': record(s,'B','A',5,0.04)
    before=snapshot_arrays(s); propose(s,'A','B',-12,0.06); assert snapshot_arrays(s)==before
    response(s,'B','A'); assert_pair(s,'A','B',-12,0.06)
    cases.append('agreement repairs unchanged asymmetry: '+existing)

# End a contract through the actual GUI; unrelated third-party records persist.
for sender,recipient in (('A','B'),('B','A')):
    s=state(); framework(s,'A','B'); pair(s,'A','B',-6,0.06); pair(s,'A','C',-2,0.1)
    propose(s,sender,recipient,0,0.06)
    assert 'B' not in s['countries']['A']['arrays']['energy_contractors']
    assert 'A' not in s['countries']['B']['arrays']['energy_contractors']
    assert not locked(s,'A') and not locked(s,'B')
    result=money(s); assert result['A']==(0.2,0) and result['B']==(0,0)
    cases.append('terminate from '+sender+' stops both payments')

# Preserve the existing AI recall flag on sending and explicit GUI termination.
s=state(); framework(s,'A','B'); s['countries']['A']['ai']=True
propose(s,'A','B',-5,0.05); assert 'energy_recall_calldown@B' in s['countries']['A']['flags']
response(s,'B','A'); s['countries']['A']['flags'].discard('energy_recall_calldown@B')
propose(s,'A','B',0,0.05); assert 'energy_recall_calldown@B' in s['countries']['A']['flags']
cases.append('existing AI recall flag retained on new offer and explicit GUI termination')

# Invalidation of one pair leaves a pending proposal with somebody else intact.
s=state(); framework(s,'A','C'); propose(s,'A','C',-2,0.1); before=deepcopy(s['countries'])
s['temp']={'eon_energy_pair_partner':'B'}; execute(effects['eon_energy_invalidate_pair_pending'],s,context('A'))
assert s['countries']==before; cases.append('pair cancellation does not clear other-partner pending')

# Cancellation during pending changes blocks an old acceptance; retry can start afresh.
s=state(); framework(s,'A','B'); pair(s,'A','B',-6,0.06); propose(s,'A','B',-8,0.07)
s['temp']={'eon_energy_pair_partner':'B'}; execute(effects['eon_energy_end_pair'],s,context('A'))
assert locked(s,'A') and locked(s,'B') and 'eon_energy_offer_cancelled' in s['countries']['B']['flags']
before=snapshot_arrays(s); response(s,'B','A')
assert not locked(s,'A') and not locked(s,'B')
assert snapshot_arrays(s)==before; propose(s,'A','B',-5,0.02); response(s,'B','A'); assert_pair(s,'A','B',-5,0.02)
cases.append('cancel pending, old accept no effect, new proposal accepted')

# A withdrawn but unanswered event cannot be overtaken by another same-pair offer.
for attempted_recipient in ('B','C'):
    s=state(); framework(s,'A','B'); framework(s,'A','C'); pair(s,'A','B',-6,0.06)
    propose(s,'A','B',-8,0.07)
    s['temp']={'eon_energy_pair_partner':'B'}; execute(effects['eon_energy_end_pair'],s,context('A'))
    frozen={c:{k:v for k,v in d['variables'].items() if k.startswith('eon_')} for c,d in s['countries'].items()}
    propose(s,'A',attempted_recipient,-9,0.09)
    assert frozen=={c:{k:v for k,v in d['variables'].items() if k.startswith('eon_')} for c,d in s['countries'].items()}
    assert locked(s,'A') and locked(s,'B') and not locked(s,'C')
    response(s,'B','A'); assert not locked(s,'A') and not locked(s,'B')
    assert s['countries']['A']['arrays']['energy_contractors']==[]
    cases.append('withdrawn event serialized before attempted replacement to '+attempted_recipient)

# Actual on_actions energy blocks: deficient supplier clears BOTH sides and locks.
on_actions=ast((ROOT/'common/on_actions/00_costili.txt').read_text(encoding='utf-8-sig'))
monthly=next(v for k,o,v in one(on_actions,'on_actions') if k=='on_monthly' and 'eon_energy_end_pair' in str(v))
s=state(); framework(s,'A','B'); pair(s,'A','B',-6,0.06); pair(s,'A','C',-2,0.04)
propose(s,'A','B',-8,0.07); s['countries']['A']['variables']['energy_balance']=-2
s['temp']={}; execute(one(monthly,'effect'),s,context('A'))
for country in ('A','B','C'): assert s['countries'][country]['arrays']['energy_contractors']==[]
assert locked(s,'A') and locked(s,'B')
response(s,'B','A'); assert not locked(s,'A') and not locked(s,'B'); result=money(s)
assert all(income==expense==0 for income,expense in result.values())
assert {ev['target'] for ev in s['events'] if ev['id']=='energy_selling.5'}=={'B','C'}
cases.append('actual shortage on_action ends both delivery/payment records for all partners')

for name,annexed in (('on_annex','A'),('on_subject_annexed','A')):
    block=next(v for k,o,v in one(on_actions,'on_actions') if k==name and 'eon_energy_clear_pair_pending' in str(v))
    s=state(); framework(s,'A','B'); pair(s,'A','B',-6,0.06); propose(s,'A','B',-8,0.07)
    s['countries']['B']['variables']['eon_energy_framework_pending_sender']='A'
    s['countries']['B']['flags'].add('eon_energy_framework_withdrawn')
    s['countries']['A']['exists']=False
    ctx=context('D','A') if name=='on_annex' else context('A','D')
    s['temp']={}; execute(one(block,'effect'),s,ctx)
    assert not locked(s,'A') and not locked(s,'B')
    assert ('B','A') in s.get('framework_cleanup_calls',[])
    assert 'eon_energy_framework_pending_sender' not in s['countries']['B']['variables']
    assert 'eon_energy_framework_withdrawn' not in s['countries']['B']['flags']
    assert s['countries']['A']['arrays']['energy_contractors']==[] and s['countries']['B']['arrays']['energy_contractors']==[]
    before=snapshot_arrays(s); response(s,'B','A'); assert snapshot_arrays(s)==before
    cases.append('actual '+name+' releases pending and cannot resurrect annexed partner')

# Commercial clear preserves the global temporary partner supplied to framework cleanup.
s=state(); framework(s,'A','B'); propose(s,'A','B',-8,0.07)
s['countries']['B']['variables']['eon_energy_framework_pending_sender']='A'
s['countries']['B']['flags'].add('eon_energy_framework_withdrawn')
s['temp']={'eon_energy_pair_partner':'A'}
execute(effects['eon_energy_clear_pair_pending'],s,context('B','A'))
assert s['temp']['eon_energy_pair_partner']=='A'
assert s['countries']['B']['variables']['eon_energy_framework_pending_sender']=='A'
execute(effects['eon_energy_framework_cleanup_annexed_pair'],s,context('B','A'))
assert s['temp']['eon_energy_pair_partner']=='A'
assert 'eon_energy_framework_pending_sender' not in s['countries']['B']['variables']
assert 'eon_energy_framework_withdrawn' not in s['countries']['B']['flags']
cases.append('simultaneous commercial/framework pending clear preserves annexed partner temp input')

# Actual economic executor sees agreed values, no pending values and no double charge.
s=state(); framework(s,'A','B'); pair(s,'A','B',-4,0.05); propose(s,'A','B',-8,0.07)
pending_money=money(s); assert pending_money['A']==(0.2,0) and pending_money['B']==(0,0.2)
response(s,'B','A'); agreed_money=money(s)
assert compare(agreed_money['A'][0],'=',0.56) and compare(agreed_money['B'][1],'=',0.56)
response(s,'B','A'); repeated_money=money(s); assert repeated_money==agreed_money
cases.append('actual weekly money source preserves pending old value and applies accepted quantity times price once')

# The baseline GUI demonstrably removes old records before any response is delivered.
baseline_confirm=one(get_gui(ast(baseline('common/scripted_guis/01_energy_gui.txt').decode('utf-8-sig'))),'confirm_energy_sell_click')
assert 'remove_from_array' in str(baseline_confirm)
assert 'remove_from_array' not in str(confirm), 'New GUI only proposes; accepted effect owns replacement'
s=state(); framework(s,'A','B'); pair(s,'A','B',-6,0.06)
s['countries']['A']['variables'].update(energy_selling_selected_TAG='B',temp_energy_ammount=-8,temp_energy_price=0.07)
execute(baseline_confirm,s,context('A'))
assert not s['countries']['A']['arrays']['energy_contractors'] and not s['countries']['B']['arrays']['energy_contractors']
assert any(ev['id']=='energy_selling.1' for ev in s['events'])
cases.append('original pre-response loss of both active records reproduced through actual GUI source')
old_on_actions=ast(baseline('common/on_actions/00_costili.txt').decode('utf-8-sig'))
old_monthly=next(v for k,o,v in one(old_on_actions,'on_actions') if k=='on_monthly' and 'energy_balance' in str(v) and 'energy_contractors' in str(v))
s=state(); pair(s,'A','B',-6,0.06); s['countries']['A']['variables']['energy_balance']=-2
execute(one(old_monthly,'effect'),s,context('A'))
result=money(s); assert compare(result['A'][0],'=',0.36) and result['B']==(0,0)
cases.append('original shortage exporter income without importer payment reproduced from actual on_action')
assert all('clr_country_flag' not in str(options[key]) for key in ('energy_selling.2.a','energy_selling.3.a','energy_selling.5.a'))
report={'test_level':'source-driven symbolic execution; not engine/campaign/save-load proof','cases_passed':len(cases),'cases':cases,'temp_variables_unscoped':True,'actual_weekly_money_effect_executed':True,'original_regression_source_removes_before_response':True,'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'common/scripted_guis/01_energy_gui.txt',ROOT/'events/00_Energy_market_events.txt',ROOT/'common/scripted_effects/eon_energy_contract_effects.txt',ROOT/'common/on_actions/00_costili.txt')}}
print(json.dumps(report,indent=2))
