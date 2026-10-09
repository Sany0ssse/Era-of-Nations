"""Interpret CURRENT ordered energy scripts; native state aggregation is a fixture boundary.

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
       'common/scripted_effects/eon_investment_income_effects.txt',
       'common/scripted_effects/eon_uranium_effects.txt',
       'common/scripted_effects/eon_uranium_seed_effects.txt']
effects={k:v for path in FILES for k,o,v in ast(read(path))}
TRIGGER_FILES=['common/scripted_triggers/eon_energy_delivery_triggers.txt',
               'common/scripted_triggers/eon_energy_capacity_triggers.txt',
               'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
               'common/scripted_triggers/eon_energy_settlement_triggers.txt']
GUI_FILE='common/scripted_guis/01_energy_gui.txt'
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
        elif k=='custom_trigger_tooltip':passed=trigger([node for node in v if node[0]!='tooltip'],s,c)
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
    # These electricity-delivery fixtures have no reactors, ore or enrichment.
    # Geography/unit initialization is an explicit already-initialized boundary;
    # the real fuel projection AST still executes on every energy calculation.
    result={'global':{'vars':{'num_days':100,'date':2400},
        'flags':{'eon_uranium_geology_initialized'},'arrays':{}},'countries':{},'temp':{},'events':[]}
    for identity in (order or list(inputs)):
        generation,demand=inputs[identity]
        result['countries'][identity]={'vars':{'modifier@energy_gain':generation,'modifier@energy_use':demand/1.25,
            'fuel_k':10,'stored_energy':0,'max_stored_energy':0,'treasury':500,'gdp_total':1,
            'resource@uranium':0,'eon_natural_uranium_stock_kg':0,'var_reactor_material_stockpile':0,
            'enrichment_facilities':0,'number_of_damaged_enrichment_facilities':0,
            'modifier@nuclear_reactor_fuel_production':0,'nuclear_reactors':0,
            'num_of_damaged_nuclear_reactor':0,'modifier@nuclear_fuel_consumption':0,
            'modifier@nuclear_energy_gain':0},
            'arrays':{'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]},
            'flags':{'disable_fossil_fuel_power_plant_flag','eon_uranium_country_initialized',
                     'eon_uranium_reactor_stock_in_kg'},
            'ideas':set(),'modifiers':set(),'wars':set(),'exists':True,'ai':True}
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

def tests():
    # An enabled processing plant still cannot manufacture fuel without feed.
    # Execute current source; do not replace the newly called helper with a stub.
    s=state({1:(30,5)});data=s['countries'][1]
    data['vars']['enrichment_facilities']=1
    data['flags'].add('enabled_nuclear_reactor_fuel_production')
    run(s,'calculate_energy_use')
    close(data['vars']['nuclear_reactor_fuel_production'],0)
    close(data['vars']['eon_natural_uranium_stock_kg'],0)
    close(data['vars']['var_reactor_material_stockpile'],0)
    close(data['vars']['eon_energy_delivery_generation'],30)
    groups['actual_uranium_projection_no_feed_preserves_delivery_inputs']+=1
    for generation in (0,5,10,30,100):
        s=state({1:(generation,5),2:(0,10),3:(0,20)});pair(s,1,2,10);pair(s,1,3,20)
        run(s);close(delivered(s,2,1),min(max(generation-5,0),30)/3);close(delivered(s,3,1),2*min(max(generation-5,0),30)/3);conservation(s);groups['proportional_shortage']+=1
    s=state({1:(40,10),2:(0,5),3:(0,4),4:(20,5)});pair(s,1,2,20);pair(s,2,3,12);pair(s,4,3,10)
    run(s);close(delivered(s,3,2),12);close(delivered(s,3,4),10);conservation(s);groups['multi_supplier_chain_reexport']+=1
    signatures=[]
    for order in permutations((1,2,3,4)):
        p=state({1:(40,10),2:(0,5),3:(0,4),4:(20,5)},order)
        for args in ((1,2,20),(2,3,12),(4,3,10)):pair(p,*args)
        run(p,actor=order[0]);signatures.append({k:v['arrays']['eon_energy_delivered'] for k,v in p['countries'].items()});conservation(p);groups['country_order_permutation']+=1
    assert all(signature==signatures[0] for signature in signatures)
    for source in (0,.01,10):
        s=state({1:(source,0),2:(0,0),3:(0,0)});pair(s,1,2,10);pair(s,2,3,10);pair(s,3,1,10)
        run(s);conservation(s)
        if source==0:assert all(q==0 for data in s['countries'].values() for q in data['arrays']['eon_energy_delivered'])
        if source==.01:assert 'eon_energy_delivery_conservative_incomplete' in s['global']['flags'] and s['global']['vars']['eon_energy_delivery_round']==64
        if source==10:close(delivered(s,2,1),10)
        groups['cycles_zero_source_real_source_incomplete']+=1
    s=state({1:(30,5),2:(0,5),3:(0,5)});pair(s,1,2,10,0);pair(s,1,3,10,.1);run(s)
    close(s['countries'][2]['vars']['energy_buying_expenses'],0);conservation(s);groups['zero_price_free_delivery']+=1
    original=deepcopy(s['countries'][1]['arrays']['energy_contracts_ammount']);s['countries'][1]['vars']['modifier@energy_gain']=10;run(s);close(delivered(s,2,1),2.5)
    assert s['countries'][1]['arrays']['energy_contracts_ammount']==original
    s['countries'][1]['vars']['modifier@energy_gain']=30;run(s);close(delivered(s,2,1),10);groups['shortage_preserves_terms_and_recovers']+=1
    for cause in ('war','missing','mismatched_price','duplicate','malformed_arrays','framework_removed'):
        s=state({1:(30,5),2:(0,5),3:(0,5)});pair(s,1,2,10);pair(s,1,3,10)
        if cause=='war':s['countries'][1]['wars'].add(2);s['countries'][2]['wars'].add(1)
        if cause=='missing':s['countries'][2]['exists']=False
        if cause=='mismatched_price':s['countries'][2]['arrays']['energy_contracts_price'][0]=.8
        if cause=='duplicate':pair(s,1,2,10)
        if cause=='malformed_arrays':s['countries'][2]['arrays']['energy_contracts_price'].clear()
        if cause=='framework_removed':s['countries'][2]['flags'].discard('energy_agreement@1')
        run(s);close(delivered(s,1,2),0);close(delivered(s,3,1),10);conservation(s);groups['invalid_only_affected_pair']+=1
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10);run(s)
    for actor in (1,2):s['countries'][actor]['arrays']['energy_contracts_ammount'][0]*=-1
    run(s,'eon_energy_delivery_calculate_bill',1);close(s['countries'][1]['vars']['energy_selling_income'],0)
    run(s);close(delivered(s,1,2),0);conservation(s);groups['opposite_direction_replacement_no_stale_benefit']+=1
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10);run(s)
    for actor in (1,2):s['countries'][actor]['arrays']['energy_contracts_price'][0]=.1
    run(s,'eon_energy_delivery_calculate_bill',1);close(s['countries'][1]['vars']['energy_selling_income'],0)
    run(s);close(s['countries'][1]['vars']['energy_selling_income'],1);groups['price_replacement_reconciles']+=1
    # Native daily hooks can visit every country: only one date-scoped snapshot.
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10);before=native['update_state_variables']
    for actor in (1,2,1,2):run(s,'eon_energy_delivery_daily_tick',actor)
    assert native['update_state_variables']-before==2
    s['global']['vars']['num_days']+=1;run(s,'eon_energy_delivery_daily_tick',2)
    assert native['update_state_variables']-before==4;groups['global_num_days_once_per_tick']+=1
    # Repeating reconciliation changes no cash; forecasts are excluded from weekly cash.
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10,.1);run(s);first=deepcopy(s)
    run(s);close(s['countries'][1]['vars']['additional_income_rate'],1);close(s['countries'][2]['vars']['additional_expenses_rate'],1)
    assert all(data['vars']['treasury']==500 for data in s['countries'].values())
    weekly=read('common/on_actions/01_on_actions.txt');body=ast(weekly.split('# Pay down debt automatically this weekly tick',1)[1].split('#Automated taking debt',1)[0])
    for actor in (1,2):s['temp']={};execute(body,s,context(actor))
    close(s['countries'][1]['vars']['treasury'],500);close(s['countries'][2]['vars']['treasury'],500);groups['actual_weekly_cash_excludes_energy_forecast']+=1
    # Replacement releases only actual old export (5), not contracted 10.
    s=state({1:(10,5),2:(0,5)});pair(s,1,2,10);run(s);s['temp']={}
    c=context(1);write(s,c,'eon_energy_capacity_counterparty',2,True);write(s,c,'eon_energy_capacity_quantity',8,True)
    assert not trigger(triggers['eon_energy_supplier_capacity_available'],s,c)
    write(s,c,'eon_energy_capacity_quantity',5,True);assert trigger(triggers['eon_energy_supplier_capacity_available'],s,c);groups['replacement_releases_actual_not_promised']+=1
    # Storage cannot fulfill 100 GW from one GWh; exports do not use storage.
    s=state({1:(0,100)});s['countries'][1]['vars'].update(stored_energy=1,max_stored_energy=1)
    run(s,'calculate_energy_use');close(s['countries'][1]['vars']['energy_withdrawal_from_storage'],1/24);groups['storage_physical_gwh_limit']+=1
    # The second balance application must NOT multiply domestic hydro/gain again.
    s=state({1:(10,5),2:(0,5)});s['countries'][1]['state_aggregates']={'hydroelectric_energy_generation':5}
    s['countries'][1]['vars']['modifier@energy_gain_multiplier']=.5;pair(s,1,2,10);run(s)
    close(s['countries'][1]['vars']['eon_energy_delivery_generation'],22.5);run(s)
    close(s['countries'][1]['vars']['eon_energy_delivery_generation'],22.5);conservation(s);groups['generation_refreshed_once_no_multiplier_compounding']+=1
    # Zero generation infrastructure executes its explicit denominator guards.
    s=state({1:(0,5)});s['countries'][1]['flags'].discard('disable_fossil_fuel_power_plant_flag')
    s['countries'][1]['ideas'].add('nuclear_energy');run(s,'calculate_energy_use')
    close(s['countries'][1]['vars']['energy_sum'],0);groups['zero_infrastructure_no_division_by_zero']+=1
    # Safe read rejects tampered/old unmatched actual amounts on both budgets.
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10);run(s)
    s['countries'][2]['arrays']['eon_energy_delivered'][0]=99
    for actor in (1,2):run(s,'eon_energy_delivery_calculate_bill',actor)
    close(s['countries'][1]['vars']['energy_selling_income'],0);close(s['countries'][2]['vars']['energy_buying_expenses'],0);groups['unmatched_actuals_fail_closed_both_bills']+=1
    # A malformed snapshot on either side fails closed on BOTH readers/bills.
    for field,wrong in (('eon_energy_delivery_prices',.10),('eon_energy_delivery_terms',7),
                        ('eon_energy_delivery_prices',None),('eon_energy_delivery_terms',None)):
        s=state({1:(30,5),2:(0,5)});pair(s,1,2,10,.05);run(s)
        if wrong is None:s['countries'][2]['arrays'][field].clear()
        else:s['countries'][2]['arrays'][field][0]=wrong
        for actor in (1,2):run(s,'eon_energy_delivery_calculate_bill',actor)
        close(s['countries'][1]['vars']['energy_selling_income'],0)
        close(s['countries'][2]['vars']['energy_buying_expenses'],0)
        groups['bilateral_snapshot_terms_prices_fail_closed']+=1
    # Execute the real receiving AI counter source with shared execution temporaries: the
    # supplier's insufficient projection must reach the recipient before false.
    for generation,wanted in ((10,5),(9.8,4),(5,0)):
        s=state({1:(generation,5),2:(0,5)});pair(s,1,2,5,.05);run(s)
        c=context(1);s['temp']={};write(s,c,'eon_energy_pair_partner',2,True)
        execute(effects['eon_energy_read_pair_record'],s,c)
        s['countries'][1]['vars'].update(energy_selling_selected_TAG=2,temp_energy_ammount=-8,temp_energy_price=.05)
        execute(effects['eon_energy_send_offer'],s,c)
        c=context(2,1);execute(effects['eon_energy_evaluate_offer'],s,c)
        old_score=s['countries'][2]['vars']['eon_energy_ai_accept_chance']
        execute(effects['eon_energy_prepare_ai_counter'],s,c)
        close(s['countries'][2]['vars']['eon_energy_counter_amount'],wanted)
        assert s['countries'][2]['vars']['eon_energy_counter_ready']==(1 if wanted else 0)
        close(s['countries'][2]['vars']['eon_energy_ai_accept_chance'],old_score)
        assert s['countries'][2]['vars']['eon_energy_offer_amount']==8
        groups['actual_scoped_ai_counter_supplier_output']+=1
    s=state({1:(10,5),2:(0,5)});pair(s,1,2,5);run(s);s['temp']={};c=context(2,1)
    s['countries'][1]['arrays']['energy_contracts_price'].clear()
    for key,val in (('eon_energy_capacity_partner',1),('eon_energy_capacity_amount',8),('eon_energy_projected_balance',-8)):
        write(s,c,key,val,True)
    assert not trigger(triggers['eon_energy_proposed_capacity_available'],s,c)
    assert value(s,c,'eon_energy_projected_balance')==-8
    groups['capacity_structural_failure_preserves_caller_sentinel']+=1
    # Different edge insertion order cannot favour one buyer over another.
    outputs=[]
    for edges in permutations(((1,2,10),(1,3,20),(2,4,5),(3,4,9))):
        s=state({1:(20,5),2:(0,2),3:(0,2),4:(0,5)})
        for edge in edges:pair(s,*edge)
        run(s);outputs.append({(a,b):delivered(s,a,b) for a,b,q in edges});conservation(s);groups['contract_order_permutation']+=1
    assert all(output==outputs[0] for output in outputs)
    # Execute the real proposal/acceptance/end helpers, including immediate
    # global reconciliation AFTER reciprocal contract tables have been written.
    s=state({1:(30,5),2:(0,5)});pair(s,1,2,10);run(s)
    for amount,price in ((-8,.07),(-5,0)):
        c=context(1);s['temp']={};write(s,c,'eon_energy_pair_partner',2,True)
        execute(effects['eon_energy_read_pair_record'],s,c)
        s['countries'][1]['vars'].update(energy_selling_selected_TAG=2,temp_energy_ammount=amount,temp_energy_price=price)
        execute(effects['eon_energy_send_offer'],s,c)
        execute(effects['eon_energy_accept_offer'],s,context(2,1))
        close(delivered(s,2,1),-amount);close(s['countries'][2]['vars']['energy_buying_expenses'],-amount*price)
        conservation(s);groups['native_frame_source_replacement_acceptance_immediate_actual']+=1
    s['temp']={};c=context(1);write(s,c,'eon_energy_pair_partner',2,True)
    execute(effects['eon_energy_end_pair'],s,c)
    assert not s['countries'][1]['arrays']['energy_contractors'] and not s['countries'][2]['arrays']['energy_contractors']
    close(s['countries'][1]['vars']['energy_selling_income'],0);close(s['countries'][2]['vars']['energy_buying_expenses'],0)
    groups['source_termination_immediate_actual_and_bill_clear']+=1
    # Evaluate the current button and the guarded producer branch independently;
    # no mouse/UI simulation or replacement send predicate is used here.
    gui=one(one(ast(read(GUI_FILE)),'scripted_gui'),'energy_scripted_gui')
    enabled=one(one(gui,'triggers'),'confirm_energy_sell_click_enabled')
    send=one(one(gui,'effects'),'confirm_energy_sell_click')
    send_limit=one(one(one(send,'else'),'if'),'limit')
    def old_gui_scalar(nodes):
        proper=[('PREV','=',[('has_country_flag','=','energy_agreement@PREV')])]
        result=[]
        for key,op,body in nodes:
            if key=='var:energy_selling_selected_TAG' and body==proper:
                result.append(('has_country_flag','=','energy_agreement@energy_selling_selected_TAG'))
            else:result.append((key,op,old_gui_scalar(body) if isinstance(body,list) else body))
        return result
    for amount in (16,32,64):
        s=state({1:(100,5),2:(0,5),3:(0,5)});pair(s,1,2,10);run(s)
        s['countries'][1]['vars'].update(energy_selling_selected_TAG=2,temp_energy_ammount=-amount,temp_energy_price=.0625)
        for key,body in (('enabled',enabled),('send_limit',send_limit)):
            s['temp']={};assert trigger(body,s,context(1)),(key,amount)
            mutant=old_gui_scalar(body);assert mutant!=body
            s['temp']={};assert not trigger(mutant,s,context(1)),('Old scalar flag accepted',key,amount)
            groups['actual_GUI_'+key+'_16_32_64_and_old_scalar_mutant']+=1
        # A flag for country3 cannot grant permission for selected country2.
        s['countries'][1]['flags'].remove('energy_agreement@2')
        s['countries'][1]['flags'].add('energy_agreement@3')
        assert 'energy_agreement@1' in s['countries'][2]['flags']
        for key,body in (('enabled',enabled),('send_limit',send_limit)):
            s['temp']={};assert not trigger(body,s,context(1)),('Wrong caller pair accepted',key,amount)
            groups['actual_GUI_'+key+'_wrong_pair_flag_rejected']+=1
    return dict(groups)

if __name__=='__main__':
    scenarios=tests();print(json.dumps({'suite':'package25 actual-source energy delivery','scenarios':sum(scenarios.values()),'groups':scenarios,
        'native_boundaries':dict(native),'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES+TRIGGER_FILES+[GUI_FILE]},
        'proof_limitations':['Current-source interpreter, not native engine execution','State/GDP aggregation supplied by explicit fixtures',
            'Tax/welfare outside selected current update_display rate nodes are zero fixtures',
            'Uranium geography is preinitialized; no-reactor/no-feed inputs execute actual fuel projection, not mining/trade settlement',
            'Native country enumeration and numeric precision require separate engine verification',
            'Interval metering, escrow and arrears are separately exercised by package27',
            'No certified network capacity; native hourly queue and cash scheduling require campaign verification'],
        'native_campaign_verified':False},indent=2))
