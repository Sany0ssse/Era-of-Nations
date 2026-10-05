"""Execute actual investment proposal/project/refund branches symbolically.

Country and state IDs share an entity map; state IDs are negative, as in project
arrays. Temporary variables share one effect environment across scopes. Event
delivery, AI selection and external influence/capitalization formulas are not
emulated: their actual calls are witnessed, and require engine verification.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'd4ec4a02a1a6dac362554ac85d4b001fbf32f488'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff')) if not m[0].startswith('#')]
    pos = 0

    def parse():
        nonlocal pos
        nodes = []
        while pos < len(tokens) and tokens[pos] != '}':
            key = tokens[pos]; pos += 1
            if pos >= len(tokens) or tokens[pos] not in ('=', '>', '<', '>=', '<=', '!=', '=='):
                nodes.append(('__item__', '=', key)); continue
            op = tokens[pos]; pos += 1
            if tokens[pos] == '{':
                pos += 1; value = parse(); assert tokens[pos] == '}'; pos += 1
            else:
                value = tokens[pos]; pos += 1
            nodes.append((key, op, value))
        return nodes

    nodes = parse(); assert pos == len(tokens), (pos, len(tokens)); return nodes


def one(nodes, key):
    found = [v for k, o, v in nodes if k == key]
    assert len(found) == 1, (key, len(found))
    return found[0]


def load(relative):
    return ast((ROOT / relative).read_text(encoding='utf-8-sig'))


def old(relative):
    return ast(subprocess.check_output(['git', 'show', BASELINE + ':' + relative], cwd=ROOT).decode('utf-8-sig'))


effects = {}
for path in ('common/scripted_effects/00_investment_scripted_effects.txt',
             'common/scripted_effects/eon_investment_project_effects.txt',
             'common/scripted_effects/00_ai_investment_scripted_effects.txt'):
    effects.update({k: v for k, o, v in load(path)})
budget = load('common/scripted_effects/00_budget_effects.txt')
effects['modify_treasury_effect'] = one(budget, 'modify_treasury_effect')
triggers = {}
for path in ('common/scripted_triggers/eon_investment_project_triggers.txt',
             'common/scripted_triggers/00_investment_scripted_triggers.txt'):
    triggers.update({k: v for k, o, v in load(path)})
events = {one(v, 'id'): v for k, o, v in load('events/00_AC_events.txt') if k == 'country_event'}
gui = one(one(one(load('common/scripted_guis/01_investment_scripted_gui.txt'), 'scripted_gui'), 'AC_allied_construction_window'), 'effects')
ACCEPT = next(v for k, o, v in events['AC_event.10'] if k == 'option' and one(v, 'name') == 'AC_event.1.o1')
REJECT = next(v for k, o, v in events['AC_event.10'] if k == 'option' and one(v, 'name') == 'AC_event.1.o2')


def context(root=1, from_=None, scope=None, previous=()):
    return {'root': root, 'from': from_, 'scope': root if scope is None else scope, 'previous': previous}


def switch(c, target):
    return {**c, 'scope': target, 'previous': (c['scope'],) + c['previous']}


def ref(s, c, name):
    if name.startswith('var:'): return value(s, c, name[4:])
    if name == 'ROOT': return c['root']
    if name == 'FROM': return c['from']
    if name == 'THIS': return c['scope']
    if name == 'PREV': return c['previous'][0] if c['previous'] else 0
    if name == 'CONTROLLER': return s['entities'][c['scope']].get('controller', 0)
    if name.startswith('PREV.'):
        parts = name.split('.'); depth = 0
        while depth < len(parts) and parts[depth] == 'PREV': depth += 1
        target = c['previous'][depth-1] if len(c['previous']) >= depth else 0
        if depth == len(parts): return target
        return value(s, {**c, 'scope': target, 'previous': c['previous'][depth:]}, '.'.join(parts[depth:]))
    return value(s, c, name)


def address(s, c, expression):
    if '^' in expression:
        name, index = expression.split('^', 1)
        index = 'num' if index == 'num' else str(int(value(s, c, index)))
        dest, key = address(s, c, name)
        return dest, key + '^' + index
    if expression.startswith('global.'):
        return s['global'], expression[7:]
    match = re.match(r'^(ROOT|FROM|THIS|CONTROLLER|PREV(?:\.PREV)*)\.(.+)$', expression)
    if match:
        head, tail = match.groups(); target = ref(s, c, head)
        return address(s, {**c, 'scope': target}, tail)
    return s['entities'][c['scope']]['variables'], expression


def value(s, c, expression):
    try: return float(expression)
    except (TypeError, ValueError): pass
    if expression in ('ROOT', 'FROM', 'THIS', 'PREV', 'CONTROLLER') or expression.startswith('var:'):
        return ref(s, c, expression)
    if expression == 'id': return c['scope']
    if expression.endswith('.id'): return ref(s, c, expression[:-3])
    if expression.startswith('building_level@'):
        return s['entities'][c['scope']].get('levels', {}).get(expression.split('@')[1], 0)
    if expression in s['temp']: return s['temp'][expression]
    dest, key = address(s, c, expression)
    if '^' in key:
        name, index = key.split('^', 1)
        entity = next((ent for ent in s['entities'].values() if ent['variables'] is dest), None)
        arrays = entity['arrays'] if entity else s['global_arrays']
        if name in arrays:
            if index == 'num': return len(arrays[name])
            index = int(index); return arrays[name][index] if 0 <= index < len(arrays[name]) else 0
    return dest.get(key, 0)


def cmp(left, op, right):
    if op in ('=', '=='): return abs(left-right) < 1e-8
    return {'>': lambda: left > right, '<': lambda: left < right,
            '>=': lambda: left >= right, '<=': lambda: left <= right,
            '!=': lambda: abs(left-right) >= 1e-8}[op]()


def flag(s, c, name):
    if '@' not in name: return name
    base, target = name.split('@', 1)
    return base + '@' + str(int(ref(s, c, target)))


def condition(nodes, s, c):
    i = 0
    while i < len(nodes):
        k, op, v = nodes[i]; i += 1
        ent = s['entities'][c['scope']]
        if k in triggers: passed = condition(triggers[k], s, c) == (v == 'yes')
        elif k in ('AND', 'hidden_trigger'): passed = condition(v, s, c)
        elif k == 'OR': passed = any(condition([node], s, c) for node in v)
        elif k == 'NOT': passed = not condition(v, s, c)
        elif k == 'custom_trigger_tooltip': passed = condition([n for n in v if n[0] != 'tooltip'], s, c)
        elif k == 'always': passed = v == 'yes'
        elif k == 'check_variable':
            if len(v) == 1:
                name, operator, other = v[0]
            else:
                name, other = one(v, 'var'), one(v, 'value')
                operator = {'less_than': '<', 'greater_than': '>', 'greater_than_or_equals': '>=', 'less_than_or_equals': '<='}[one(v, 'compare')]
            passed = cmp(value(s, c, name), operator, value(s, c, other))
        elif k == 'has_variable':
            dest, key = address(s, c, v); passed = key in dest
        elif k == 'has_country_flag': passed = flag(s, c, v) in ent['flags']
        elif k == 'has_state_flag': passed = v in ent['flags']
        elif k == 'has_global_flag': passed = v in s['global_flags']
        elif k == 'is_in_array':
            d = {a: b for a, o, b in v}
            if 'array' in d:
                array, element = d['array'], d['value']
            else:
                array, element = next(iter(d.items()))
            if '.' in array:
                head, array = array.split('.', 1)
                arrays = s['entities'][ref(s, c, head)]['arrays'] if head != 'global' else s['global_arrays']
            else: arrays = ent['arrays']
            passed = value(s, c, element) in arrays.get(array, [])
        elif k == 'exists': passed = ent['exists'] == (v == 'yes')
        elif k == 'has_war_with': passed = ref(s, c, v) in ent['wars']
        elif k == 'is_justifying_wargoal_against': passed = ref(s, c, v) in ent['justifying']
        elif k == 'is_controlled_by': passed = ent.get('controller') == ref(s, c, v)
        elif k == 'has_idea': passed = v in ent['ideas']
        elif k == 'has_tech': passed = v in ent['techs']
        elif k in ('tag', 'original_tag'): passed = ref(s, c, v) == c['scope']
        elif k == 'free_building_slots':
            building = one(v, 'building'); n = next(n for n in v if n[0] == 'size')
            passed = cmp(ent['slots'].get(building, 0), n[1], float(n[2]))
        elif k in BUILDINGS:
            passed = cmp(ent['levels'].get(k, 0), op, float(v))
        elif k == 'if':
            branches = [v]
            while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                branches.append(nodes[i][2]); i += 1
            passed = True
            for branch in branches:
                limits = [n[2] for n in branch if n[0] == 'limit']
                if not limits or condition(limits[0], s, c):
                    passed = condition([n for n in branch if n[0] != 'limit'], s, c); break
        elif k in ('ROOT', 'FROM', 'PREV', 'THIS', 'CONTROLLER') or k.startswith(('var:', 'PREV.')):
            target = ref(s, c, k)
            passed = target in s['entities'] and condition(v, s, switch(c, target))
        else: raise AssertionError(('Unsupported investment trigger', k, op, v))
        if not passed: return False
    return True


def execute(nodes, s, c):
    i = 0
    while i < len(nodes):
        k, op, v = nodes[i]; i += 1
        ent = s['entities'][c['scope']]
        if k == 'if':
            branches = [v]
            while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                branches.append(nodes[i][2]); i += 1
            for branch in branches:
                limits = [n[2] for n in branch if n[0] == 'limit']
                if not limits or condition(limits[0], s, c):
                    execute([n for n in branch if n[0] != 'limit'], s, c); break
        elif k in effects: execute(effects[k], s, c)
        elif k == 'hidden_effect': execute(v, s, c)
        elif k in ('ROOT', 'FROM', 'PREV', 'THIS', 'CONTROLLER') or k.startswith(('var:', 'PREV.')):
            target = ref(s, c, k)
            if target in s['entities']: execute(v, s, switch(c, target))
        elif k in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                   'subtract_from_variable', 'subtract_from_temp_variable', 'multiply_variable',
                   'multiply_temp_variable', 'divide_variable', 'divide_temp_variable'):
            d = {a: b for a, o, b in v}
            if 'var' in d: name, rhs = d['var'], d['value']
            else: name, rhs = next(iter(d.items()))
            rhs = value(s, c, rhs)
            if 'temp_variable' in k: dest, key = s['temp'], name
            else: dest, key = address(s, c, name)
            current = value(s, c, name)
            if k.startswith('set_'): new = rhs
            elif k.startswith('add_'): new = current + rhs
            elif k.startswith('subtract_'): new = current - rhs
            elif k.startswith('multiply_'): new = current * rhs
            else: new = current / rhs
            if '^' in key and not name.startswith('global.'):
                base, index = key.split('^', 1)
                # Cross-scope addressed fixed arrays need the actual destination entity.
                entity = next((entity for entity in s['entities'].values() if entity['variables'] is dest), None)
                ar = entity['arrays'].get(base) if entity else None
                if ar is not None: ar[int(index)] = new; continue
            dest[key] = new
        elif k in ('clamp_variable', 'clamp_temp_variable'):
            name = one(v, 'var'); current = value(s, c, name)
            d = {a: b for a, o, b in v}
            if 'min' in d: current = max(current, value(s, c, d['min']))
            if 'max' in d: current = min(current, value(s, c, d['max']))
            dest, key = (s['temp'], name) if 'temp_variable' in k else address(s, c, name)
            dest[key] = current
        elif k == 'round_variable':
            dest, key = address(s, c, v); dest[key] = round(value(s, c, v))
        elif k == 'clear_variable':
            dest, key = address(s, c, v); dest.pop(key, None)
        elif k == 'set_country_flag':
            name = v if isinstance(v, str) else one(v, 'flag'); ent['flags'].add(flag(s, c, name))
        elif k == 'clr_country_flag': ent['flags'].discard(flag(s, c, v))
        elif k == 'resize_array': ent['arrays'][one(v, 'array')] = [value(s, c, one(v, 'value'))] * int(value(s, c, one(v, 'size')))
        elif k == 'add_to_array':
            d = {a: b for a, o, b in v}
            name, element = (d['array'], d['value']) if 'array' in d else next(iter(d.items()))
            ent['arrays'].setdefault(name, []).append(value(s, c, element))
        elif k == 'remove_from_array':
            name = one(v, 'array'); ar = ent['arrays'][name]; d = {a: b for a, o, b in v}
            if 'index' in d: ar.pop(int(value(s, c, d['index'])))
            elif value(s, c, d['value']) in ar: ar.remove(value(s, c, d['value']))
        elif k == 'for_each_loop':
            d = {a: b for a, o, b in v if a in ('array', 'value', 'index', 'break')}
            for index, element in enumerate(list(ent['arrays'].get(d['array'], []))):
                s['temp'][d.get('value', 'v')] = element
                s['temp'][d.get('index', 'i')] = index
                execute([n for n in v if n[0] not in d], s, c)
                if s['temp'].get(d.get('break', 'break'), 0): break
        elif k == 'every_country':
            for target in (1, 2, 3, 4): execute(v, s, switch(c, target))
        elif k == 'country_event':
            ident = v if isinstance(v, str) else one(v, 'id')
            s['events'].append((ident, c['scope'], c['root']))
        elif k == 'random_list':
            # Deterministic successful-building branch. Corruption probability is not modelled.
            execute(one(v, '75'), s, c)
        elif k == 'add_building_construction':
            s['buildings'].append((c['scope'], one(v, 'type')))
            ent['slots'][one(v, 'type')] -= int(one(v, 'level'))
        elif k in ('activate_decision', 'activate_targeted_decision', 'remove_targeted_decision',
                   'modify_capitalization_support', 'change_influence_percentage', 'add_opinion_modifier',
                   'update_gui', 'ingame_update_setup', 'save_event_target_as'):
            s['external'].append((c['scope'], k, deepcopy(v), deepcopy(s['temp'])))
        elif k in ('name', 'ai_chance', 'log', 'custom_effect_tooltip', 'trigger'): pass
        else: raise AssertionError(('Unsupported investment effect', k, op, v))


BUILDINGS = ['industrial_complex', 'arms_factory', 'dockyard', 'infrastructure', 'offices',
             'anti_air_building', 'radar_station', 'air_base', 'fuel_silo', 'internet_station',
             'synthetic_refinery', 'fossil_powerplant', 'nuclear_reactor', 'agriculture_district', 'rubber_refinery']


def state():
    s = dict(entities={}, global_={}, temp={}, events=[], external=[], buildings=[], global_flags=set(), global_arrays={})
    s['global'] = s.pop('global_')
    for ident in (1, 2, 3, 4, -101, -102):
        s['entities'][ident] = dict(variables={}, arrays={}, flags=set(), wars=set(), justifying=set(), exists=True,
                                   ideas={'defense_industry', 'the_military', 'maritime_industry'}, techs={'fuel_silos', 'radar', 'reactor1'},
                                   slots={b: 10 for b in BUILDINGS}, levels={})
        s['entities'][ident]['variables'].update(treasury=1000, int_investments=0, active_projects=0)
    s['entities'][-101]['controller'] = 2
    s['entities'][-102]['controller'] = 3
    execute(effects['init_investment_system'], s, context())
    return s


def stage(s, donor=1, receiver=2, target=-101, kind=1, amount=2, cost=30, duration=100):
    s['entities'][donor]['variables'].update(AC_nation_target=receiver, AC_state_target=target,
        **{'project_building_type^-1': kind, 'project_build_amount^-1': amount,
           'project_monetary_cost^-1': cost, 'project_monetary_cost_effect': -cost,
           'project_construction_duration^-1': duration, 'project_total_construction_duration_display^-1': duration*amount})


def send(s, donor=1):
    s['temp'] = {}
    execute(one(events['AC_event.3'], 'immediate'), s, context(donor))
    return bool(s['entities'][donor]['variables'].get('eon_investment_offer_partner', 0))


def respond(s, receiver=2, donor=1, accept=True):
    s['temp'] = {}
    execute(ACCEPT if accept else REJECT, s, context(receiver, donor))


def money(s):
    return [(s['entities'][i]['variables']['treasury'], s['entities'][i]['variables']['int_investments']) for i in (1, 2, 3, 4)]


def persistent(s):
    return deepcopy({k: v for k, v in s.items() if k != 'temp'})


def drain(s):
    while s['events']:
        ident, target, from_ = s['events'].pop(0)
        ev = events[ident]
        if any(k == 'hidden' and v == 'yes' for k, o, v in ev):
            execute(one(ev, 'immediate'), s, context(target, from_))


cases = []
# Frozen offers for every existing building type, quantities, and accept/reject.
for kind in range(1, 16):
    for amount in (1, 2, 3):
        for accept in (False, True):
            s = state(); stage(s, kind=kind, amount=amount); assert send(s)
            before = money(s)
            stage(s, receiver=3, target=-102, kind=15, amount=3, cost=300, duration=900)
            # Actual event cannot overwrite an outstanding snapshot.
            assert send(s)
            assert s['entities'][1]['variables']['eon_investment_offer_partner'] == 2
            respond(s, accept=accept)
            donor = s['entities'][1]
            if accept:
                assert donor['arrays']['project_array'][0] == -101
                assert donor['variables']['project_building_type^0'] == kind
                assert donor['variables']['project_build_amount^0'] == amount
                assert donor['variables']['project_construction_duration^0'] == 100
                assert donor['variables']['eon_project_cofinancer^0'] == 2
                assert money(s)[:2] == [(970, 30), (997, 0)]
                assert s['entities'][-101]['arrays']['projects_in_state'] == [1]
                assert s['entities'][-102]['arrays'].get('projects_in_state', []) == []
                influence = [x for x in s['external'] if x[1] == 'change_influence_percentage']
                assert len(influence) == 1 and influence[0][0] == 2
                assert influence[0][3]['tag_index'] == 1 and influence[0][3]['influence_target'] == 2
            else:
                assert money(s) == before and donor['arrays']['project_array'] == [0]*15
                assert not [x for x in s['external'] if x[1] == 'modify_capitalization_support']
            assert not donor['variables'].get('eon_investment_offer_partner', 0)
            assert 'AC_ai_investment_pending' not in donor['flags']
            before = persistent(s); respond(s, accept=accept); assert persistent(s) == before
            cases.append(f'frozen kind={kind} amount={amount} accept={accept}')

# Response-time changes must not charge either country or start a project.
mutations = {
    'donor funds': lambda s: s['entities'][1]['variables'].update(treasury=29),
    'recipient funds': lambda s: s['entities'][2]['variables'].update(treasury=2.9),
    'war recipient': lambda s: s['entities'][2]['wars'].add(1),
    'war donor': lambda s: s['entities'][1]['wars'].add(2),
    'justification': lambda s: s['entities'][1]['justifying'].add(2),
    'changed controller': lambda s: s['entities'][-101].update(controller=3),
    'building slots': lambda s: s['entities'][-101]['slots'].update(industrial_complex=1),
    'full project array': lambda s: s['entities'][1]['arrays'].update(project_array=[-102]*15),
    'active project limit': lambda s: s['entities'][1]['variables'].update(active_projects=15),
    'existing state project': lambda s: s['entities'][-101]['arrays'].update(projects_in_state=[1]),
    'misaligned legacy state arrays': lambda s: s['entities'][-101]['arrays'].update(projects_in_state=[4], project_type_in_state=[]),
    'auto rejection': lambda s: s['entities'][2]['flags'].add('int_auto_reject_investment_flag'),
    'foreign investments disabled': lambda s: s['entities'][1]['flags'].add('disabled_foreign_investment'),
    'withdrawn': lambda s: s['entities'][1]['flags'].add('eon_investment_offer_withdrawn'),
    'recipient gone': lambda s: s['entities'][2].update(exists=False),
    'donor gone': lambda s: s['entities'][1].update(exists=False),
}
for name, mutate in mutations.items():
    s = state(); stage(s); assert send(s); mutate(s)
    before_money = money(s); before_arrays = deepcopy({i: d['arrays'] for i, d in s['entities'].items()})
    assert not condition(one(ACCEPT, 'trigger'), s, context(2, 1))
    # Even forced execution cannot commit stale conditions.
    respond(s)
    assert money(s) == before_money
    assert {i: d['arrays'] for i, d in s['entities'].items()} == before_arrays
    assert not [x for x in s['external'] if x[1] == 'modify_capitalization_support']
    assert not s['entities'][1]['variables'].get('eon_investment_offer_partner', 0)
    cases.append('response revalidation: '+name)

# Wrong recipient neither changes money nor consumes another recipient's offer.
for accept in (False, True):
    s = state(); stage(s); send(s); before = persistent(s); respond(s, receiver=3, accept=accept); assert persistent(s) == before
    cases.append('foreign response '+str(accept))

# Independent donors can agree with the same recipient; all charges are distinct.
s = state(); stage(s); send(s); stage(s, donor=4, kind=5, amount=1, cost=20); send(s, donor=4)
respond(s); respond(s, donor=4)
assert money(s) == [(970, 30), (995, 0), (1000, 0), (980, 20)]
assert s['entities'][-101]['arrays']['projects_in_state'] == [1, 4]
cases.append('independent donors share recipient')

# Automatic consent uses exactly the same validation and atomic charges.
for valid in (False, True):
    s = state(); stage(s); s['entities'][2]['flags'].add('int_auto_accept_investment_flag')
    if not valid: s['entities'][2]['variables']['treasury'] = 2
    send(s)
    assert s['entities'][1]['variables']['active_projects'] == int(valid)
    assert money(s)[0] == ((970, 30) if valid else (1000, 0))
    assert not s['entities'][1]['variables'].get('eon_investment_offer_partner', 0)
    assert not any(x[0] == 'AC_event.10' for x in s['events'])
    cases.append('automatic consent '+str(valid))

# Refusal information must stay passive after a later proposal is prepared.
s = state(); stage(s); send(s); respond(s, accept=False); stage(s, receiver=3, target=-102); send(s)
before = persistent(s)
ack = next(v for k, o, v in events['AC_event.11'] if k == 'option')
execute(ack, s, context(1, 2)); assert persistent(s) == before
cases.append('informational refusal preserves new proposal')

# Annex cleanup uses original pair; unrelated requests survive. A stale answer
# from the annexed partner cannot create a project or debit a new unrelated pair.
for annexed in (2, 3):
    s = state(); stage(s); send(s); s['temp'] = {'eon_investment_annexed_partner': annexed}
    execute(effects['eon_investment_project_cleanup_annexed_pair'], s, context())
    assert bool(s['entities'][1]['variables'].get('eon_investment_offer_partner', 0)) == (annexed != 2)
    if annexed == 2:
        stage(s, receiver=3, target=-102); send(s); before = persistent(s); respond(s); assert persistent(s) == before
    cases.append('annex pair '+str(annexed))

# Correct donor equality refund and immutable new-project cofinancer, including
# a territorial transfer. Low portfolio keeps the inherited no-investor-refund
# behavior; old projects without payer metadata retain controller fallback.
for portfolio in (0, 29, 30, 31, 100):
    for legacy in (False, True):
        for original_exists in (False, True):
            s = state(); stage(s); send(s); respond(s)
            donor = s['entities'][1]; donor['variables']['int_investments'] = portfolio
            if legacy: donor['variables'].pop('eon_project_cofinancer^0')
            s['entities'][-101]['controller'] = 3
            s['entities'][2]['exists'] = original_exists
            donor['variables']['project'] = 0
            execute(effects['end_project'], s, context())
            drain(s)
            assert donor['variables']['treasury'] == (1000 if portfolio >= 30 else 970)
            assert donor['variables']['int_investments'] == (portfolio-30 if portfolio >= 30 else portfolio)
            assert donor['variables']['active_projects'] == 0 and donor['arrays']['project_array'][0] == 0
            assert s['entities'][2]['variables']['treasury'] == (1000 if not legacy and original_exists else 997)
            assert s['entities'][3]['variables']['treasury'] == (1003 if legacy else 1000)
            assert 'project_target_state_@1' not in s['entities'][-101]['variables']
            assert s['entities'][-101]['arrays']['projects_in_state'] == []
            assert s['entities'][-101]['arrays']['project_type_in_state'] == []
            assert 'eon_project_cofinancer^0' not in donor['variables']
            before = money(s); donor['variables']['project'] = 0; execute(effects['end_project'], s, context()); assert money(s) == before
            cases.append(f'refund portfolio={portfolio} legacy={legacy} original_exists={original_exists}')

# Actual completion branch builds the agreed state/type and consumes remaining
# project principal. Deterministic successful construction excludes corruption AI.
for kind in (1, 5, 14, 15):
    s = state(); stage(s, kind=kind, amount=1); send(s); respond(s)
    s['entities'][1]['variables']['project'] = 0
    execute(effects['complete_project'], s, context()); drain(s)
    assert s['buildings'] == [(-101, BUILDINGS[kind-1])]
    assert money(s)[:2] == [(970, 30), (997, 0)]
    assert s['entities'][1]['variables']['active_projects'] == 0
    cases.append('source completion type '+str(kind))

for finish_all in (False, True):
    s = state(); stage(s, amount=2); send(s); respond(s)
    donor = s['entities'][1]
    donor['variables']['project'] = 0
    execute(effects['complete_project'], s, context())
    assert donor['variables']['project_build_amount^0'] == 1
    assert donor['variables']['project_monetary_cost^0'] == 15
    donor['variables']['project'] = 0
    execute(effects['complete_project'] if finish_all else effects['end_project'], s, context())
    drain(s)
    assert len(s['buildings']) == (2 if finish_all else 1)
    assert money(s)[:2] == ([(970, 30), (997, 0)] if finish_all else [(985, 15), (998.5, 0)])
    assert donor['variables']['active_projects'] == 0
    cases.append('queue completion or partial cancellation '+str(finish_all))

# A new proposal can coexist with an already executing project. The actual GUI
# business branch allows cancellation without clearing the other proposal.
s = state(); stage(s); send(s); respond(s)
stage(s, receiver=3, target=-102); send(s)
gui_window = one(one(load('common/scripted_guis/01_investment_scripted_gui.txt'), 'scripted_gui'), 'AC_allied_construction_window')
enabled = one(one(gui_window, 'triggers'), 'AC_build_button_click_enabled')
branches = [n for n in enabled if n[0] in ('if', 'else_if', 'else')]
assert condition(branches, s, context(1, scope=-101, previous=(1,)))
snapshot_offer = {k: v for k, v in s['entities'][1]['variables'].items() if k.startswith('eon_investment_offer_')}
execute(one(gui, 'AC_build_button_click'), s, context(1, scope=-101, previous=(1,)))
assert {k: v for k, v in s['entities'][1]['variables'].items() if k.startswith('eon_investment_offer_')} == snapshot_offer
assert money(s)[:2] == [(1000, 0), (1000, 0)]
cases.append('GUI existing cancellation preserves other pending offer')

# Aligned legacy state entries remain aligned and untouched when our new entry
# is canceled. An unmatched legacy array is rejected before proposal execution.
s = state(); s['entities'][-101]['arrays'].update(projects_in_state=[4], project_type_in_state=[5])
stage(s); send(s); respond(s)
assert s['entities'][-101]['arrays']['projects_in_state'] == [4, 1]
assert s['entities'][-101]['arrays']['project_type_in_state'] == [5, 1]
s['entities'][1]['variables']['project'] = 0
s['temp'] = {}
execute(effects['end_project'], s, context()); drain(s)
assert s['entities'][-101]['arrays']['projects_in_state'] == [4]
assert s['entities'][-101]['arrays']['project_type_in_state'] == [5]
cases.append('aligned legacy state entries survive our cancellation')

# Stale available-project variables must not allow reuse of a filled index.
s = state(); s['entities'][1]['variables']['new_project'] = 0
s['entities'][1]['arrays']['project_array'] = [-101]*15
execute(effects['get_available_project'], s, context())
assert 'new_project' not in s['entities'][1]['variables']
cases.append('full project array clears stale index')

# Reproduce the original refund equality bug from preserved actual source.
s = state(); stage(s); send(s); respond(s)
s['entities'][1]['variables']['project'] = 0
legacy_end = one(old('common/scripted_effects/00_investment_scripted_effects.txt'), 'end_project')
execute(legacy_end, s, context()); drain(s)
assert s['entities'][1]['variables']['treasury'] == 970
assert s['entities'][1]['variables']['int_investments'] == 30
cases.append('reproduced baseline refund equality bug')

# Frozen availability clones must be exact transformations of the baseline
# building restrictions, preventing accidental price/technology rebalance.
baseline_triggers = old('common/scripted_triggers/00_investment_scripted_triggers.txt')
availability = ['AC_building_cic_available','AC_building_mic_available','AC_building_nic_available','AC_building_infra_available','AC_building_offices_available','AC_building_antiair_available','AC_building_radar_available','AC_building_airbase_available','building_fuel_silos_available','building_internet_station_available','AC_building_ref_available','AC_building_foss_fuel_powerplant_available','AC_building_reactor_available','AC_building_agriculture_district_available','AC_building_rubber_refinery_available']
for index, key in enumerate(availability, 1):
    def transform(nodes):
        out = []
        for k, op, v in nodes:
            k = re.sub(r'\bROOT\b', 'PREV', k).replace('project_build_amount^-1', 'eon_investment_offer_amount')
            v = transform(v) if isinstance(v, list) else re.sub(r'\bROOT\b', 'PREV', v).replace('project_build_amount^-1', 'eon_investment_offer_amount')
            out.append((k, op, v))
        return out
    assert transform(one(baseline_triggers, key)) == triggers['eon_investment_building_'+str(index)]

# No direct legacy scripted path can bypass central frozen proposal creation.
legacy_helpers = ['invest_cic','invest_mic','invest_nic','invest_infra','invest_offices','invest_anti_air','invest_radar','invest_air_bases','invest_fuel_silo','invest_internet_station','invest_biofuel_refinery','invest_fossil_powerplant','invest_nuclear_powerplant','invest_agriculture_district','invest_rubber_refinery']
for name in legacy_helpers:
    assert one(effects[name], 'eon_investment_prepare_scripted_offer') == 'yes'
assert ('check_variable', '=', [('eon_investment_offer_partner', '=', '0')]) in one(events['AC_event.500'], 'trigger')

# Every quantity supported by the existing literal building eligibility rules.
# Compare transformed frozen eligibility to the actual preserved original rules.
for index, key in enumerate(availability, 1):
    for quantity in range(1, 11):
        s = state(); stage(s, kind=index, amount=quantity)
        expected = condition(one(baseline_triggers, key), s, context(1, scope=-101, previous=(1,)))
        actual = send(s)
        assert actual == expected, (key, quantity, expected, actual)
        if actual:
            respond(s); assert s['entities'][1]['variables']['project_build_amount^0'] == quantity
        else:
            assert money(s)[:2] == [(1000, 0), (1000, 0)]
        cases.append(f'original building eligibility kind={index} quantity={quantity} allowed={actual}')

# Full GUI and legacy scripted entry paths calculate their existing actual price
# and duration before snapshot creation, rather than trusting a copied test price.
for kind in (1, 5, 15):
    s = state(); stage(s, kind=kind, amount=2, cost=999, duration=999)
    execute(one(gui, 'AC_build_button_click'), s, context(1, scope=-101, previous=(1,)))
    drain(s)
    offered = s['entities'][1]['variables']['eon_investment_offer_cost']
    expected = {1: 30, 5: 40, 15: 16}[kind]
    assert offered == expected, (kind, offered)
    respond(s); assert s['entities'][1]['variables']['treasury'] == 1000-expected
    assert s['entities'][2]['variables']['treasury'] == 1000-expected*0.1
    cases.append('full GUI actual cost type '+str(kind))
for helper, cost in (('invest_cic', 15), ('invest_mic', 12), ('invest_rubber_refinery', 8)):
    s = state(); execute(effects[helper], s, context(1, scope=-101, previous=(1,))); drain(s)
    assert s['entities'][1]['variables']['eon_investment_offer_cost'] == cost
    respond(s); assert s['entities'][1]['variables']['treasury'] == 1000-cost
    cases.append('legacy scripted frozen entry '+helper)

# Reproduce the original mutable-GUI contract defect using preserved actual
# callbacks and start_project_two, then restore the current implementation.
s = state(); stage(s); send(s); stage(s, receiver=3, target=-102, kind=5, amount=1, cost=300)
current_start = effects['start_project_two']
effects['start_project_two'] = one(old('common/scripted_effects/00_investment_scripted_effects.txt'), 'start_project_two')
baseline_events = {one(v, 'id'): v for k, o, v in old('events/00_AC_events.txt') if k == 'country_event'}
baseline_accept = next(v for k, o, v in baseline_events['AC_event.10'] if k == 'option' and one(v, 'name') == 'AC_event.1.o1')
execute(baseline_accept, s, context(2, 1)); effects['start_project_two'] = current_start
assert s['entities'][1]['arrays']['project_array'][0] == -102
assert money(s)[:3] == [(700, 300), (970, 0), (1000, 0)]
cases.append('reproduced baseline mutable offer starts wrong country')
source_paths = ['common/scripted_effects/eon_investment_project_effects.txt', 'common/scripted_triggers/eon_investment_project_triggers.txt', 'common/scripted_effects/00_investment_scripted_effects.txt', 'events/00_AC_events.txt']
report = dict(cases_passed=len(cases), source_checks=32, scenarios=cases,
              source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
              limits=['HOI4 engine not executed', 'Native event delivery and save/load unverified',
                      'Influence/capitalization formulas witnessed, not emulated',
                      'Only deterministic successful building branch; corruption probabilities unchanged',
                      'Legacy cofinancer fallback cannot reconstruct original history'])
if __name__ == '__main__': print(json.dumps(report, ensure_ascii=False))
