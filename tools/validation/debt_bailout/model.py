"""Execute current bailout AST, with explicit country/clock/economy boundaries.

The queue below is a supplied popup-consumption fixture, not native consumption.
Autonomy and economy refresh are native-call observations, not emulated systems.
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('eon_bailout_base', ROOT/'tools/validation/diplomacy_package_27/_model.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
m.effects.update({k:v for k,o,v in m.ast(m.read('common/scripted_effects/eon_debt_bailout_effects.txt'))})
m.triggers.update({k:v for k,o,v in m.ast(m.read('common/scripted_triggers/eon_debt_bailout_triggers.txt'))})
base_trigger, base_execute = m.trigger, m.execute

def groups(nodes):
    i = 0
    while i < len(nodes):
        group = [nodes[i]]; i += 1
        if group[0][0] == 'if':
            while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                group.append(nodes[i]); i += 1
        yield group

def trigger(nodes, s, c):
    for group in groups(nodes):
        k,o,v = group[0]; owner = s['countries'].get(c['scope'], {})
        if k == 'custom_trigger_tooltip':
            passed = trigger([n for n in v if n[0] != 'tooltip'], s, c)
        elif k == 'clamp_temp_variable':
            execute(group, s, c); passed = True
        elif k == 'is_subject': passed = bool(owner.get('overlord')) == (v == 'yes')
        elif k == 'is_subject_of': passed = owner.get('overlord') == m.resolve(s, c, v)
        elif k == 'is_neighbor_of': passed = m.resolve(s, c, v) in owner.get('neighbors', set())
        elif k == 'is_full_state': passed = owner.get('full_state', False) == (v == 'yes')
        elif k == 'has_opinion':
            wanted = next(n for n in v if n[0] == 'value')
            passed = m.compare(owner.get('opinions', {}).get(m.resolve(s,c,m.one(v,'target')),0), wanted[1], m.value(s,c,wanted[2]))
        elif k == 'has_decision': passed = v in owner.get('active_decisions', set())
        elif k == 'original_tag': passed = owner.get('tag') == (s['countries'].get(m.resolve(s,c,v),{}).get('tag') if v.startswith('var:') else v)
        elif k == 'overlord':
            peer = owner.get('overlord'); passed = peer in s['countries'] and trigger(v,s,m.switch(c,peer))
        else: passed = base_trigger(group, s, c)
        if not passed: return False
    return True

def execute(nodes, s, c):
    for group in groups(nodes):
        k,o,v = group[0]; owner = s['countries'].get(c['scope'])
        if k in ('name','trigger','ai_chance'): continue
        if k == 'overlord':
            peer = owner.get('overlord')
            if peer in s['countries']: execute(v,s,m.switch(c,peer))
        elif k == 'add_political_power': owner['vars']['political_power'] += m.value(s,c,v)
        elif k == 'add_autonomy_ratio':
            delta = m.value(s,c,m.one(v,'value'))
            owner['vars']['autonomy_ratio'] = owner['vars'].get('autonomy_ratio',0) + delta
            s.setdefault('autonomy_calls',[]).append((c['scope'],delta))
        elif k == 'ingame_update_setup': s.setdefault('refresh_calls',[]).append(c['scope'])
        elif k == 'country_event':
            ident = v if isinstance(v,str) else m.one(v,'id')
            # Country event queued in peer scope inherits the emitting country.
            s['events'].append({'id':ident,'target':c['scope'],'sender':c['prev'][0] if c['prev'] else c['scope']})
        else: base_execute(group,s,c)

m.trigger, m.execute = trigger, execute
DECISIONS = dict((k,v) for k,o,v in m.one(m.ast(m.read('common/decisions/bankruptcy_decisions.txt')),'bankruptcy_decisions'))
EVENTS = {m.one(v,'id'):v for path in ('events/00_Econ_events.txt','events/eon_debt_bailout_events.txt')
          for k,o,v in m.ast(m.read(path)) if k in ('country_event','news_event')}
ROUTES = ('bankruptcy_seek_bailout_from_biggest_influencer','bankruptcy_seek_bailout_from_second_biggest_influencer','bankruptcy_seek_bailout_from_neighbour','bankruptcy_seek_bailout_from_overlord')

def state(kind=1, debt=100, cash=100, borrower=1, donor=2):
    s = m.state({i:(0,0) for i in (1,2,3,4)})
    for i, tag in enumerate(('USA','SWI','NEP','BRA'),1):
        d = s['countries'][i]
        d.update(tag=tag,neighbors=set(s['countries'])-{i},full_state=True,
                 opinions={j:100 for j in s['countries']},overlord=None,active_decisions=set())
        d['vars'].update(debt=0,treasury=100,political_power=500,interest_rate=12,gdp_total=200)
        d['arrays']['influence_array'] = [0]*7
    b = s['countries'][borrower]
    b['vars'].update(debt=debt,treasury=0,gdp_total=100)
    s['countries'][donor]['vars']['treasury'] = cash
    if kind in (1,2): b['arrays']['influence_array'][kind-1] = donor
    if kind == 4: b['overlord'] = donor
    return s

def invoke(s,name,actor,from_=None,temps=None):
    s['temp'] = dict(temps or {})
    execute([(name,'=','yes')],s,m.context(actor,from_))

def prepare(s,kind=1,borrower=1,donor=2):
    s['temp'] = {}
    execute(m.one(DECISIONS[ROUTES[kind-1]],'complete_effect'),s,m.context(borrower,donor if kind==3 else borrower))

def respond(s,kind=1,borrower=1,donor=2,accept=True):
    # Deliberately supplied consumption boundary; runtime must prove real popups.
    ident = 'eon_debt_bailout.'+str(kind)
    queued = next(e for e in s['events'] if e == {'id':ident,'target':donor,'sender':borrower})
    s['events'].remove(queued)
    option = next(v for k,o,v in EVENTS[ident] if k=='option' and m.one(v,'name') == ('eon_debt_bailout_accept' if accept else 'eon_debt_bailout_refuse'))
    s['temp'] = {}; c = m.context(donor,borrower)
    assert trigger(m.one(option,'trigger'),s,c), ('Matching modal must remain consumable',kind,c)
    execute(option,s,c)
