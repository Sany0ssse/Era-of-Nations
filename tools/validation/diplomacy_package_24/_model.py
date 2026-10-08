"""Package 24 source interpreter adapted from the existing package 02 investment model.

Country and state IDs share an entity map; state IDs are negative, as in project
arrays. Temporary variables belong to their country/state scope; scoped writes
and reads resolve explicitly, including PREV/ROOT. Event
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
events = {one(v, 'id'): v for path in ('events/00_AC_events.txt', 'events/eon_investment_lifecycle_events.txt') for k, o, v in load(path) if k == 'country_event'}
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
    if name == 'OWNER': return s['entities'][c['scope']].get('owner', 0)
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
    match = re.match(r'^(ROOT|FROM|THIS|CONTROLLER|OWNER|PREV(?:\.PREV)*)\.(.+)$', expression)
    if match:
        head, tail = match.groups(); target = ref(s, c, head)
        return address(s, {**c, 'scope': target}, tail)
    return s['entities'][c['scope']]['variables'], flag(s, c, expression) if '@' in expression else expression


def value(s, c, expression):
    try: return float(expression)
    except (TypeError, ValueError): pass
    if expression in ('ROOT', 'FROM', 'THIS', 'PREV', 'CONTROLLER', 'OWNER') or expression.startswith('var:'):
        return ref(s, c, expression)
    if expression == 'id': return c['scope']
    if expression.endswith('.id'): return ref(s, c, expression[:-3])
    if expression.startswith('building_level@'):
        return s['entities'][c['scope']].get('levels', {}).get(expression.split('@')[1], 0)
    dest, key = address(s, c, expression)
    scope = next((ident for ident, ent in s['entities'].items() if ent['variables'] is dest), 'global')
    if key in s['temp'].get(scope, {}): return s['temp'][scope][key]
    if '^' in key:
        name, index = key.split('^', 1)
        entity = next((ent for ent in s['entities'].values() if ent['variables'] is dest), None)
        arrays = entity['arrays'] if entity else s['global_arrays']
        if name in arrays:
            if index == 'num': return len(arrays[name])
            index = int(index); return arrays[name][index] if 0 <= index < len(arrays[name]) else 0
    return dest.get(key, 0)


def temp_address(s, c, expression):
    dest, key = address(s, c, expression)
    assert '^' not in key, ('Temporary array write unsupported', expression)
    scope = next((ident for ident, ent in s['entities'].items() if ent['variables'] is dest), 'global')
    return s['temp'].setdefault(scope, {}), key


def cmp(left, op, right):
    if op in ('=', '=='): return abs(left-right) < 1e-8
    return {'>': lambda: left > right, '<': lambda: left < right,
            '>=': lambda: left >= right, '<=': lambda: left <= right,
            '!=': lambda: abs(left-right) >= 1e-8}[op]()


CHECK_VARIABLE_COMPARISONS = {
    'less_than': '<', 'less_than_or_equals': '<=',
    'greater_than': '>', 'greater_than_or_equals': '>=',
    'equals': '=', 'not_equals': '!=',
}


def variable_comparison(nodes):
    """Decode only the documented native check_variable grammar.

    The general AST still recognizes other operators for native building
    triggers. This trigger's shorter form accepts only =, < and >.
    """
    assert isinstance(nodes, list) and nodes, ('Invalid check_variable body', nodes)
    if len(nodes) == 1:
        name, operator, other = nodes[0]
        assert name != '__item__' and operator in ('=', '<', '>'), ('Unsupported short check_variable', nodes)
        assert isinstance(other, str), ('Non-scalar check_variable value', nodes)
        return name, operator, other
    fields = {}
    for name, operator, other in nodes:
        assert name in ('var', 'value', 'compare', 'tooltip'), ('Unknown check_variable field', nodes)
        assert name not in fields and operator == '=' and isinstance(other, str), ('Invalid check_variable field', nodes)
        fields[name] = other
    assert {'var', 'value', 'compare'} <= fields.keys(), ('Missing check_variable field', nodes)
    assert fields['compare'] in CHECK_VARIABLE_COMPARISONS, ('Unknown check_variable comparison', nodes)
    return fields['var'], CHECK_VARIABLE_COMPARISONS[fields['compare']], fields['value']


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
            name, operator, other = variable_comparison(v)
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
        elif k in ('ROOT', 'FROM', 'PREV', 'THIS', 'CONTROLLER', 'OWNER') or k.startswith(('var:', 'PREV.')):
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
        elif k in ('ROOT', 'FROM', 'PREV', 'THIS', 'CONTROLLER', 'OWNER') or k.startswith(('var:', 'PREV.')):
            target = ref(s, c, k)
            if target in s['entities']: execute(v, s, switch(c, target))
        elif k in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                   'subtract_from_variable', 'subtract_from_temp_variable', 'multiply_variable',
                   'multiply_temp_variable', 'divide_variable', 'divide_temp_variable'):
            d = {a: b for a, o, b in v}
            if 'var' in d: name, rhs = d['var'], d['value']
            else: name, rhs = next(iter(d.items()))
            rhs = value(s, c, rhs)
            if 'temp_variable' in k: dest, key = temp_address(s, c, name)
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
            dest, key = temp_address(s, c, name) if 'temp_variable' in k else address(s, c, name)
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
                dest, key = temp_address(s, c, d.get('value', 'v')); dest[key] = element
                dest, key = temp_address(s, c, d.get('index', 'i')); dest[key] = index
                execute([n for n in v if n[0] not in d], s, c)
                if value(s, c, d.get('break', 'break')): break
        elif k == 'every_country':
            for target in (1, 2, 3, 4): execute(v, s, switch(c, target))
        elif k == 'country_event':
            ident = v if isinstance(v, str) else one(v, 'id')
            s['events'].append((ident, c['scope'], c['root']))
        elif k == 'random_list':
            # Deterministic successful-building branch. Corruption probability is not modelled.
            selected = one(v, '0' if s.get('corruption') else '75')
            # Weight modifiers select an outcome in the engine; explicit fixtures
            # choose it here. Their statements are not construction effects.
            execute([node for node in selected if node[0] != 'modifier'], s, c)
        elif k == 'add_building_construction':
            if not s.get('native_build_failure'):
                s['buildings'].append((c['scope'], one(v, 'type')))
                ent['slots'][one(v, 'type')] -= int(one(v, 'level'))
                ent['levels'][one(v, 'type')] = ent['levels'].get(one(v, 'type'), 0) + int(one(v, 'level'))
        elif k in ('activate_decision', 'activate_targeted_decision', 'remove_targeted_decision',
                   'modify_capitalization_support', 'change_influence_percentage', 'add_opinion_modifier',
                   'update_gui', 'ingame_update_setup', 'save_event_target_as'):
            s['external'].append((c['scope'], k, deepcopy(v), deepcopy(s['temp'].get(c['scope'], {}))))
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
    s['entities'][-101]['owner'] = 2
    s['entities'][-102]['controller'] = 3
    s['entities'][-102]['owner'] = 3
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
