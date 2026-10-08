"""Strict source execution for the additive consultation navigation.

Extends the current package28 interpreter, retaining its explicit influence and
Singapore witnesses. No unknown command is skipped. Country variables contain
numeric country identities; scopes contain tags. Native event delivery, rendered
UI, multiplayer and .hoi4 saves are not simulated or claimed by these checks.
"""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('channel_framework_adapter', ROOT / 'tools/validation/diplomacy_package_28/_support.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m = f.m
parse, one, compare, ctx, switch = f.parse, f.one, f.compare, f.ctx, f.switch
IDS = f.IDS
TRIGGERS, EFFECTS = f.TRIGGERS, f.EFFECTS

def definitions(path):
    return {name: body for name, op, body in parse((ROOT / path).read_text(encoding='utf-8-sig'))}

BASE_FILES = [
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_aid_triggers.txt',
    'common/scripted_effects/eon_aid_effects.txt',
    'common/scripted_effects/eon_energy_contract_effects.txt',
    'common/scripted_effects/00_money_system.txt',
    'common/scripted_effects/00_influence_scripted_effects.txt',
    'events/eon_consultation_events.txt',
]
for path in BASE_FILES[:4]:
    (TRIGGERS if '/scripted_triggers/' in path else EFFECTS).update(definitions(path))
# Only exact reachable dependency bodies are registered, with source receipts.
for path, names in [
    (BASE_FILES[4], ('eon_energy_read_pair_record',)),
    (BASE_FILES[5], ('update_energy_dirty_variable',)),
    (BASE_FILES[6], ('update_dirty_influence_var',)),
]:
    source = definitions(path)
    for name in names:
        EFFECTS[name] = source[name]

UI_FILES = [
    'common/scripted_triggers/eon_consultation_ui_triggers.txt',
    'common/scripted_effects/eon_consultation_ui_effects.txt',
    'common/scripted_diplomatic_actions/eon_consultation_ui_actions.txt',
    'common/decisions/eon_consultation_ui_decisions.txt',
    'common/decisions/categories/eon_consultation_ui_categories.txt',
    'events/eon_consultation_ui_events.txt',
    'common/scripted_localisation/eon_consultation_ui_scripted_localisation.txt',
    *[f'localisation/{lang}/eon_consultation_ui_l_{lang}.yml' for lang in ('english', 'russian')],
    'common/scripted_triggers/eon_consultation_energy_ui_triggers.txt',
    'common/scripted_effects/eon_consultation_energy_ui_effects.txt',
]
for path in UI_FILES:
    if (ROOT / path).exists() and ('/scripted_triggers/' in path or '/scripted_effects/' in path):
        (TRIGGERS if '/scripted_triggers/' in path else EFFECTS).update(definitions(path))
FILES = list(dict.fromkeys([*f.FILES, *BASE_FILES, *UI_FILES]))

def variable_slot(result, context, field, temporary=False):
    if temporary and result.get('temp_semantics') in ('shared', 'native'):
        return result['global']['temps'], field.removeprefix('global.')
    if field.startswith('global.'):
        return result.setdefault('global', {}).setdefault('temps' if temporary else 'variables', {}), field[7:]
    return result['countries'][context['scope']]['temps' if temporary else 'variables'], key(result, context, field)

def country_ref(result, context, token):
    if token in ('ROOT', 'FROM', 'THIS', 'PREV'):
        return {'ROOT': context['root'], 'FROM': context['from'], 'THIS': context['scope'], 'PREV': context['prev'][0] if context['prev'] else None}[token]
    if token in result['countries']:
        return token
    field = token[4:] if token.startswith('var:') else token
    c = result['countries'][context['scope']]
    if token.startswith('var:') or field in c['temps'] or field in c['variables'] or field in result.get('global', {}).get('temps', {}):
        identity = value(result, context, field)
        if identity in result['countries']:
            return identity
        return next((tag for tag, number in IDS.items() if number == identity), None)
    raise AssertionError(('Unknown country identity', token, context))

def key(result, context, token):
    if '@' not in token:
        return token
    field, target = token.split('@', 1)
    tag = country_ref(result, context, target)
    assert tag is not None, ('Missing flag/variable target', token, context)
    return field + '@' + tag

previous_value = f.value
def value(result, context, token):
    token = token[4:] if token.startswith('var:') else token
    try:
        return float(token)
    except ValueError:
        pass
    if token in ('ROOT', 'FROM', 'THIS', 'PREV') or token in result['countries']:
        tag = country_ref(result, context, token)
        return IDS.get(tag, 0)
    if result.get('temp_semantics') in ('shared', 'native') and token in result.get('global', {}).get('temps', {}):
        return result['global']['temps'][token]
    if token.startswith('global.'):
        field = token[7:]
        return result.get('global', {}).get('temps', {}).get(field, result.get('global', {}).get('variables', {}).get(field, 0))
    if '^' in token:
        field, ordinal = token.split('^', 1)
        array = result['countries'][context['scope']]['arrays'].get(field, [])
        if ordinal == 'num':
            return len(array)
        index = int(value(result, context, ordinal))
        return array[index] if 0 <= index < len(array) else 0
    if result.get('temp_semantics') == 'native' and '.' in token:
        scope, field = token.split('.', 1)
        tag = country_ref(result, context, scope)
        if tag is None:
            return 0
        if field == 'id':
            return IDS[tag]
        # Native10 proves a scope-prefixed scalar cannot retrieve execution temp.
        # Such reads use persistent variables of the explicitly selected scope.
        return result['countries'][tag]['variables'].get(key(result, switch(context, tag), field), 0)
    return previous_value(result, context, token)

previous_condition, previous_execute = f.condition, f.execute

def condition(nodes, result, context):
    for group in f.chunks(nodes):
        name, op, data = group[0]
        c = result['countries'][context['scope']]
        if name == 'is_ai':
            ready = c['ai'] == (data == 'yes')
        elif name == 'has_variable':
            field = data
            if field.startswith('global.'):
                ready = field[7:] in result.get('global', {}).get('variables', {})
            else:
                ready = key(result, context, field) in c['variables']
        elif name.startswith('var:'):
            target = country_ref(result, context, name)
            ready = target is not None and condition(data, result, switch(context, target))
        elif name in ('all_of', 'any_of'):
            fields = {k: v for k, o, v in data if k in ('array', 'value', 'index')}
            body = [node for node in data if node[0] not in fields]
            outcomes = []
            for ordinal, item in enumerate(list(c['arrays'].get(fields['array'], []))):
                target, field = variable_slot(result, context, fields.get('value', 'v'), True)
                target[field] = item
                target, field = variable_slot(result, context, fields.get('index', 'i'), True)
                target[field] = ordinal
                outcomes.append(condition(body, result, context))
                if (name == 'all_of' and not outcomes[-1]) or (name == 'any_of' and outcomes[-1]):
                    break
            ready = all(outcomes) if name == 'all_of' else any(outcomes)
        else:
            ready = previous_condition(group, result, context)
        if not ready:
            return False
    return True

def execute(nodes, result, context):
    for group in f.chunks(nodes):
        name, op, data = group[0]
        if name in ('set_variable', 'set_temp_variable', 'add_to_variable', 'subtract_from_variable', 'clear_variable'):
            if name == 'clear_variable':
                target, field = variable_slot(result, context, data)
                target.pop(field, None)
            else:
                assert len(data) == 1 and data[0][1] == '=', ('Unexpected variable body', data)
                field, operator, wanted = data[0]
                target, field = variable_slot(result, context, field, name == 'set_temp_variable')
                amount = value(result, context, wanted)
                target[field] = amount if name.startswith('set_') else target.get(field, 0) + amount * (-1 if name == 'subtract_from_variable' else 1)
        elif name in ('add_to_temp_variable', 'subtract_from_temp_variable', 'multiply_temp_variable', 'divide_temp_variable'):
            assert len(data) == 1 and data[0][1] == '=', ('Unexpected temp arithmetic', data)
            field, operator, wanted = data[0]
            target, field = variable_slot(result, context, field, True)
            amount, before = value(result, context, wanted), target.get(field, 0)
            target[field] = {'add_to_temp_variable': lambda: before + amount, 'subtract_from_temp_variable': lambda: before - amount, 'multiply_temp_variable': lambda: before * amount, 'divide_temp_variable': lambda: before / amount}[name]()
        elif name == 'for_each_loop':
            fields = {k: v for k, o, v in data}
            for ordinal, item in enumerate(list(result['countries'][context['scope']]['arrays'].get(fields['array'], []))):
                target, field = variable_slot(result, context, fields.get('value', 'v'), True)
                target[field] = item
                target, field = variable_slot(result, context, fields.get('index', 'i'), True)
                target[field] = ordinal
                execute([n for n in data if n[0] not in ('array', 'value', 'index', 'break')], result, context)
                if fields.get('break') and value(result, context, fields['break']):
                    break
        elif name.startswith('var:'):
            target = country_ref(result, context, name)
            if target is not None:
                execute(data, result, switch(context, target))
        elif name == 'for_each_scope_loop':
            array = one(data, 'array')
            for identity in list(result['countries'][context['scope']]['arrays'].get(array, [])):
                tag = next((tag for tag, number in IDS.items() if number == identity), None)
                assert tag is not None, ('Invalid scope-loop identity', identity)
                execute([n for n in data if n[0] != 'array'], result, switch(context, tag))
        elif name == 'country_event':
            event_id = one(data, 'id') if isinstance(data, list) else data
            sender = context['prev'][0] if context['prev'] else context['root']
            result['events'].append({'id': event_id, 'scope': context['scope'], 'root': context['scope'], 'from': sender})
        else:
            previous_execute(group, result, context)

# Existing adapter recursive calls also pass through these strict extensions.
for module in (m, f):
    module.value, module.key, module.country_ref = value, key, country_ref
    module.condition, module.execute = condition, execute

def state(temp_semantics='native'):
    assert temp_semantics in ('country', 'shared', 'native')
    result = f.state()
    result['global'] = {'variables': {}, 'temps': {}}
    result['temp_semantics'] = temp_semantics
    for country in result['countries'].values():
        country['ai'] = False
        country['variables'].update(gdp_total=100, num_of_civilian_factories=10)
        country['arrays'].update(energy_contractors=[], energy_contracts_ammount=[], energy_contracts_price=[])
    return result

def native_ctx(actor='A', peer='B'):
    return ctx(actor, peer) | {'scope': peer}

def stable(result):
    output = deepcopy(result)
    output.pop('events', None)
    output.pop('external', None)
    output.get('global', {}).pop('temps', None)
    for country in output['countries'].values():
        country['temps'] = {}
    return output

def active_pair(result, actor='A', peer='B', topic=1):
    """Fixture setup, not a substitute for consent-cycle assertions."""
    for owner, partner in ((actor, peer), (peer, actor)):
        country = result['countries'][owner]
        country['flags'].update(('eon_consultation_reserved', 'eon_consultation_active', 'eon_consultation_active_window'))
        country['expires']['eon_consultation_active_window'] = result['day'] + 30
        country['variables'].update(eon_consultation_partner=IDS[partner], eon_consultation_topic=topic)
    return result

def hashes():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in FILES}
