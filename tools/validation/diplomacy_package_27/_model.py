"""Package27 CURRENT source interpreter adapted from package25; native state aggregation is a fixture boundary.

No independent copied dispatch algorithm. Arrays, scopes, signed quantities,
rounds, prices, daily latch, balance and budget deltas are read from game files.
This is source execution evidence, never native HOI4/campaign acceptance.
"""
from pathlib import Path
from decimal import Decimal, ROUND_DOWN
from copy import deepcopy
from itertools import permutations
from collections import Counter
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[3]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
def read(path): return (ROOT/path).read_text(encoding='utf-8-sig')
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
            if tokens[n]=='{': n+=1; val=parse(); assert tokens[n]=='}'; n+=1
            else: val=tokens[n]; n+=1
            result.append((key,op,val))
        return result
    result=parse(); assert n==len(tokens); return result
def one(nodes,key):
    found=[v for k,o,v in nodes if k==key]; assert len(found)==1,(key,len(found)); return found[0]
FILES=['common/scripted_effects/eon_energy_delivery_effects.txt',
       'common/scripted_effects/!_energy_effects.txt',
       'common/scripted_effects/eon_energy_contract_effects.txt',
       'common/scripted_effects/eon_energy_framework_effects.txt',
       'common/scripted_effects/eon_energy_negotiation_effects.txt',
       'common/scripted_effects/eon_energy_ai_effects.txt',
       'common/scripted_effects/eon_energy_settlement_effects.txt',
       'common/scripted_effects/eon_investment_income_effects.txt']
effects={k:v for path in FILES for k,o,v in ast(read(path))}
TRIGGER_FILES=['common/scripted_triggers/eon_energy_delivery_triggers.txt',
               'common/scripted_triggers/eon_energy_capacity_triggers.txt',
               'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
               'common/scripted_triggers/eon_energy_settlement_triggers.txt']
triggers={k:v for path in TRIGGER_FILES for k,o,v in ast(read(path))}
money_ast=ast(read('common/scripted_effects/00_money_system.txt'))
effects['automated_debt_taker']=one(money_ast,'automated_debt_taker')
constants={k:float(v) for k,v in effects.items() if k.startswith('@')}
groups=Counter(); native=Counter()
def context(root,from_=None,scope=None,prev=()): return dict(root=root,from_=from_,scope=scope if scope is not None else root,prev=prev)
def switch(c,scope): return {**c,'scope':scope,'prev':(c['scope'],)+c['prev']}
def resolve(s,c,key):
    if key=='global': return 'global'
    if key=='ROOT': return c['root']
    if key=='FROM': return c['from_']
    if key=='THIS': return c['scope']
    if key=='PREV': return c['prev'][0]
    if key.startswith('var:'): return value(s,c,key[4:])
    return value(s,c,key)
def target(s,c,key):
    if '.' in key:
        scope,tail=key.split('.',1)
        if scope in ('global','ROOT','FROM','THIS','PREV'): return target(s,switch(c,resolve(s,c,scope)),tail)
    return c['scope'],key
def value(s,c,key):
    if isinstance(key,(float,int)): return key
    try: return float(key)
    except (ValueError,TypeError): pass
    if key in constants:return constants[key]
    if key in ('ROOT','FROM','THIS','PREV'):return resolve(s,c,key)
    explicit_scope='.' in key and key.split('.',1)[0] in ('global','ROOT','FROM','THIS','PREV')
    scope,key=target(s,c,key); owner=s['global'] if scope=='global' else s['countries'].get(scope,{})
    sc=switch(c,scope) if scope!=c['scope'] else c
    if key=='id':return scope
    if '^' in key:
        array,index=key.split('^',1); rows=owner.get('arrays',{}).get(array,[])
        if index=='num':return len(rows)
        ix=int(value(s,sc,index));return rows[ix] if 0<=ix<len(rows) else 0
    # Native10: execution temporaries are shared; an explicit scope reads persistent state.
    if not explicit_scope and key in s['temp']:return s['temp'][key]
    return owner.get('vars',{}).get(key,0)
def write(s,c,key,val,temp=False):
    if temp:assert '.' not in key,('Unmodeled scoped temporary write',key)
    if 'precision' in s:
        unit=Decimal(1).scaleb(-s['precision']);val=float(Decimal(str(val)).quantize(unit,rounding=ROUND_DOWN))
    scope,key=target(s,c,key); owner=s['global'] if scope=='global' else s['countries'][scope]
    sc=switch(c,scope) if scope!=c['scope'] else c
    if '^' in key:
        assert not temp;array,index=key.split('^',1);ix=int(value(s,sc,index));rows=owner['arrays'][array]
        assert 0<=ix<len(rows),(scope,key,ix,len(rows));rows[ix]=val
    elif temp:s['temp'][key]=val
    else:owner['vars'][key]=val
def flag(s,c,key):
    # Native29: only actual country scopes address keyed flags; arbitrary names
    # remain literal even when a temporary or persistent alias has a country ID.
    if '@' in key:
        name,who=key.split('@',1)
        if who in ('ROOT','FROM','PREV','THIS'):
            return name+'@'+str(int(resolve(s,c,who)))
    return key
def compare(a,op,b):
    return {'=':lambda:abs(a-b)<1e-8,'==':lambda:abs(a-b)<1e-8,'!=':lambda:abs(a-b)>=1e-8,
            '<':lambda:a<b,'>':lambda:a>b,'<=':lambda:a<=b,'>=':lambda:a>=b}[op]()
COMPARE_OPERATORS={'equals':'=','not_equals':'!=','less_than':'<','greater_than':'>',
                   'less_than_or_equals':'<=','greater_than_or_equals':'>='}
def variable_comparison(nodes):
    """Read native full var/value/compare form and documented shorthand alike."""
    if any(k=='var' for k,o,v in nodes):
        key=one(nodes,'var');wanted=one(nodes,'value')
        comparisons=[v for k,o,v in nodes if k=='compare']
        assert len(comparisons)<=1,nodes
        operation=COMPARE_OPERATORS[comparisons[0] if comparisons else 'equals']
        assert all(k in ('var','value','compare','tooltip') and o=='=' for k,o,v in nodes),nodes
        return key,operation,wanted
    assert len(nodes)==1,nodes
    return nodes[0]
def trigger(nodes,s,c):
    i=0
    while i<len(nodes):
        k,op,v=nodes[i];i+=1;owner=s['countries'].get(c['scope'],{})
        if k in triggers: passed=trigger(triggers[k],s,c)==(v=='yes')
        elif k=='NOT': passed=not trigger(v,s,c)
        elif k=='OR': passed=any(trigger([node],s,c) for node in v)
        elif k=='AND':passed=trigger(v,s,c)
        elif k=='always':passed=v=='yes'
        elif k=='check_variable':
            key,operation,wanted=variable_comparison(v);passed=compare(value(s,c,key),operation,value(s,c,wanted))
        elif k in ('set_temp_variable','add_to_temp_variable','multiply_temp_variable','subtract_from_temp_variable'):
            execute([(k,op,v)],s,c);passed=True
        elif k=='all_of':
            d={a:b for a,o,b in v if a in ('array','value','index')};passed=True
            for idx,entry in enumerate(list(owner.get('arrays',{}).get(d['array'],[]))):
                write(s,c,d.get('value','v'),entry,True);write(s,c,d.get('index','i'),idx,True)
                if not trigger([node for node in v if node[0] not in d],s,c):passed=False;break
        elif k=='any_other_country':
            passed=any(data['exists'] and scope!=c['scope'] and trigger(v,s,switch(c,scope))
                       for scope,data in s['countries'].items())
        elif k=='if':
            branches=[v]
            while i<len(nodes) and nodes[i][0] in ('else_if','else'):branches.append(nodes[i][2]);i+=1
            passed=True
            for branch in branches:
                limits=[body for name,o,body in branch if name=='limit']
                if not limits or trigger(limits[0],s,c):passed=trigger([node for node in branch if node[0]!='limit'],s,c);break
        elif k=='exists':passed=owner.get('exists',False)==(v=='yes')
        elif k=='is_ai':passed=owner.get('ai',False)==(v=='yes')
        elif k=='is_debug':passed=s.get('debug',False)==(v=='yes')
        elif k=='has_war_with':passed=resolve(s,c,v) in owner.get('wars',set())
        elif k=='tag':passed=c['scope']==resolve(s,c,v)
        elif k=='has_variable':passed=v in owner['vars']
        elif k=='has_country_flag':passed=flag(s,c,v) in owner['flags']
        elif k=='has_global_flag':passed=v in s['global']['flags']
        elif k=='has_idea':passed=v in owner.get('ideas',set())
        elif k=='has_dynamic_modifier':passed=one(v,'modifier') in owner.get('modifiers',set())
        elif k=='is_in_array':passed=value(s,c,one(v,'value')) in owner['arrays'].get(one(v,'array'),[])
        elif k.startswith('var:') or k in ('ROOT','FROM','THIS','PREV'):
            scope=resolve(s,c,k);passed=scope in s['countries'] and trigger(v,s,switch(c,scope))
        else:raise AssertionError(('Unknown trigger',k,op,v))
        if not passed:return False
    return True
def execute(nodes,s,c):
    i=0
    while i<len(nodes):
        k,op,v=nodes[i];i+=1;owner=s['countries'].get(c['scope'])
        if k=='if':
            branches=[v]
            while i<len(nodes) and nodes[i][0] in ('else_if','else'):branches.append(nodes[i][2]);i+=1
            for branch in branches:
                limits=[body for name,o,body in branch if name=='limit']
                if not limits or trigger(limits[0],s,c):execute([node for node in branch if node[0]!='limit'],s,c);break
        elif k in ('calculate_damaged_buildings_count','update_state_variables','ingame_update_setup'):
            native[k]+=1
            # Explicit native aggregation boundary. Dynamic generation/demand
            # fixtures feed the REAL calculate_energy_use source below.
            if k!='calculate_damaged_buildings_count':
                owner['vars'].update(owner.get('state_aggregates',{}))
                execute(effects['calculate_energy_use'],s,c)
        elif k=='update_display':
            native[k]+=1
            # Read actual final budget arithmetic from installed source; opaque
            # tax/welfare state already supplied as zero fixtures in this suite.
            body=one(money_ast,'update_display');chosen=[]
            for node in body:
                if node[0] in ('set_variable','add_to_variable','subtract_from_variable') and node[2][0][0] in ('display_income','display_expense','treasury_rate','eon_cash_income_rate','eon_cash_expense_rate','eon_treasury_cash_rate'):
                    chosen.append(node)
                elif node[0]=='clamp_variable' and one(node[2],'var') in ('display_income','display_expense','eon_cash_income_rate','eon_cash_expense_rate'):
                    chosen.append(node)
            execute(chosen,s,c)
        elif k in effects:execute(effects[k],s,c)
        elif k.startswith('var:') or k in ('ROOT','FROM','THIS','PREV'):
            scope=resolve(s,c,k)
            if scope in s['countries']:execute(v,s,switch(c,scope))
        elif k in ('set_variable','add_to_variable','subtract_from_variable','multiply_variable','divide_variable',
                   'set_temp_variable','add_to_temp_variable','subtract_from_temp_variable','multiply_temp_variable','divide_temp_variable'):
            d={a:b for a,o,b in v};key=d.get('var',next(iter(d)));rhs=d.get('value',d[key]);temp='temp_variable' in k
            if isinstance(rhs,list):
                total=0
                for operation,o,operand in rhs:
                    wanted=value(s,c,operand)
                    if operation=='value':total=wanted
                    elif operation=='multiply':total*=wanted
                    elif operation=='add':total+=wanted
                    else:raise AssertionError(operation)
                rhs=total
            else:rhs=value(s,c,rhs)
            old=value(s,c,key)
            if k.startswith('divide_'):assert rhs!=0,('Zero denominator in current source',k,key,v,c)
            left,right=(Decimal(str(old)),Decimal(str(rhs))) if 'precision' in s else (old,rhs)
            new=right if k.startswith('set_') else left+right if k.startswith('add_') else left-right if k.startswith('subtract_') else left*right if k.startswith('multiply_') else left/right
            write(s,c,key,new,temp)
        elif k in ('clamp_variable','clamp_temp_variable'):
            d={a:b for a,o,b in v};key=d['var'];val=value(s,c,key)
            if 'min' in d:val=max(val,value(s,c,d['min']))
            if 'max' in d:val=min(val,value(s,c,d['max']))
            write(s,c,key,val,k=='clamp_temp_variable')
        elif k=='round_temp_variable':write(s,c,v,round(value(s,c,v)),True)
        elif k in ('set_country_flag','clr_country_flag'):
            key=v if isinstance(v,str) else one(v,'flag');name=flag(s,c,key)
            if k=='set_country_flag':owner['flags'].add(name)
            else:owner['flags'].discard(name)
        elif k in ('set_global_flag','clr_global_flag'):
            assert isinstance(v,str),'No invented native timed global flag semantics'
            if k=='set_global_flag':s['global']['flags'].add(v)
            else:s['global']['flags'].discard(v)
        elif k=='clear_variable':owner['vars'].pop(v,None)
        elif k=='clear_array':
            scope,name=target(s,c,v);data=s['global'] if scope=='global' else s['countries'][scope];data['arrays'][name]=[]
        elif k=='add_to_array':
            scope,name=target(s,c,one(v,'array'));data=s['global'] if scope=='global' else s['countries'][scope];data['arrays'].setdefault(name,[]).append(value(s,c,one(v,'value')))
        elif k=='remove_from_array':owner['arrays'][one(v,'array')].pop(int(value(s,c,one(v,'index'))))
        elif k=='for_each_loop':
            d={a:b for a,o,b in v if a in ('array','value','index','break')}
            scope,name=target(s,c,d['array']);data=s['global'] if scope=='global' else s['countries'][scope]
            for idx,entry in enumerate(list(data['arrays'].get(name,[]))):
                write(s,c,d.get('value','v'),entry,True);write(s,c,d.get('index','i'),idx,True)
                execute([node for node in v if node[0] not in d],s,c)
                if 'break' in d and value(s,c,d['break']):break
        elif k=='every_country':
            limits=[body for name,o,body in v if name=='limit']
            for scope,data in list(s['countries'].items()):
                if data['exists'] and (not limits or trigger(limits[0],s,switch(c,scope))):execute([node for node in v if node[0]!='limit'],s,switch(c,scope))
        elif k=='while_loop_effect':
            count=0
            while trigger(one(v,'limit'),s,c):
                count+=1;assert count<=1000
                execute([node for node in v if node[0]!='limit'],s,c)
        elif k=='add_dynamic_modifier':owner['modifiers'].add(one(v,'modifier'))
        elif k=='country_event':
            ident=v if isinstance(v,str) else one(v,'id')
            s['events'].append((c['scope'],ident))
            if isinstance(v,list) and any(name=='hours' for name,o,b in v):
                # Scheduled delivery is an explicit native clock fixture. The
                # current script's hours operand, not a copied schedule, is read.
                s.setdefault('scheduled',[]).append((value(s,c,'global.date')+float(one(v,'hours')),c['scope'],ident))
        elif k in ('custom_effect_tooltip','log'):native[k]+=1
        elif k in ('update_energy_dirty_variable','calculate_interest_rate'):native[k]+=1
        else:raise AssertionError(('Unknown effect',k,op,v))

def state(inputs,order=None):
    result={'global':{'vars':{'num_days':100,'date':2400},'flags':set(),'arrays':{}},'countries':{},'temp':{},'events':[]}
    for identity in (order or list(inputs)):
        generation,demand=inputs[identity]
        result['countries'][identity]={'vars':{'modifier@energy_gain':generation,'modifier@energy_use':demand/1.25,
            'fuel_k':10,'stored_energy':0,'max_stored_energy':0,'treasury':500,'gdp_total':1},
            'arrays':{'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]},
            'flags':{'disable_fossil_fuel_power_plant_flag'},'ideas':set(),'modifiers':set(),'wars':set(),'exists':True,'ai':True}
    return result
def pair(s,supplier,buyer,quantity,price=.05):
    for country,partner,amount in ((supplier,buyer,-quantity),(buyer,supplier,quantity)):
        data=s['countries'][country];data['arrays']['energy_contractors'].append(partner)
        data['arrays']['energy_contracts_ammount'].append(amount);data['arrays']['energy_contracts_price'].append(price)
        data['flags'].add('energy_agreement@'+str(partner))
def run(s,name='eon_energy_delivery_reconcile_world',actor=None):
    s['temp']={};execute(effects[name],s,context(actor or next(iter(s['countries']))));return s
def delivered(s,owner,partner):
    a=s['countries'][owner]['arrays'];return a['eon_energy_delivered'][a['energy_contractors'].index(partner)]
def close(actual,wanted):assert abs(actual-wanted)<.003,(actual,wanted)
def conservation(s):
    total=0;income=0;expense=0
    for identity,data in s['countries'].items():
        v=data['vars'];a=data['arrays']
        if not data['exists']:continue
        total+=v.get('eon_energy_delivery_imports',0)-v.get('eon_energy_delivery_exports',0)
        income+=v.get('energy_selling_income',0);expense+=v.get('energy_buying_expenses',0)
        assert v.get('eon_energy_delivery_exports',0)<=max(0,v.get('eon_energy_delivery_generation',0)+v.get('eon_energy_delivery_imports',0)-v.get('eon_energy_delivery_demand',0))+.002
        for idx,q in enumerate(a.get('eon_energy_delivered',[])):
            assert abs(q)<=abs(a['energy_contracts_ammount'][idx])+.002
            if q:close(q,-delivered(s,a['energy_contractors'][idx],identity))
    close(total,0);close(income,expense)
