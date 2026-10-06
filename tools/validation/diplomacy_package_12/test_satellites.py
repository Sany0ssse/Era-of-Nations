"""Bounded ordered actual-source civilian satellite access, not HOI4 runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '347cfd22e65a812ae609264ff1a043cbdc87145d'
groups = Counter()

# Only reusable definitions run here; previous scenarios run in their own runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_10/test_antiterror.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# The actual native declaration callback must contribute once to both countries.'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'satellite_ordered_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch = (source[name] for name in ('ast', 'one', 'context', 'switch'))
source_trigger, source_execute, source_value = source['trigger'], source['execute'], model['value']

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

def reference(result, ctx, expression):
    """Native scoped variable/array destination; global is a separate fixture."""
    if '.' in expression:
        head, tail = expression.split('.', 1)
        if head == 'global': return result['global'], tail
        if head in ('ROOT', 'FROM', 'THIS', 'PREV') or head in result['countries']:
            actor = model['country_ref'](result, ctx, head)
            assert actor in result['countries'], ('Missing native reference actor', head, ctx)
            return result['countries'][actor], tail
    return result['countries'][ctx['scope']], expression

def value(result, ctx, expression):
    if isinstance(expression, str) and expression.startswith('global.'):
        data, field = reference(result, ctx, expression)
        if '^' in field:
            name, index = field.split('^', 1)
            array = data['arrays'].get(name, [])
            if index == 'num': return len(array)
            position = int(value(result, ctx, index))
            return array[position] if 0 <= position < len(array) else 0
        return data['variables'].get(field, 0)
    return source_value(result, ctx, expression)

def array_ref(result, ctx, expression):
    data, name = reference(result, ctx, expression)
    return data['arrays'].setdefault(name, [])

def destination(result, ctx, expression, temporary=False):
    if temporary: return result['temp'], expression
    data, field = reference(result, ctx, expression)
    if '^' in field:
        name, index = field.split('^', 1)
        position = int(value(result, ctx, index)); array = data['arrays'].setdefault(name, [])
        assert position >= 0, ('Negative native destination index', field)
        while len(array) <= position: array.append(0)
        return array, position
    return data['variables'], field

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'is_in_array':
            if len(val) == 1: name, op, wanted = val[0]; assert op == '='
            else: name, wanted = one(val, 'array'), one(val, 'value')
            passed = value(result, ctx, wanted) in array_ref(result, ctx, name)
        elif key == 'divide_temp_variable':
            execute(grouped, result, ctx); passed = True
        else: passed = source_trigger(grouped, result, ctx)
        if not passed: return False
    return True

def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                   'subtract_from_variable', 'subtract_from_temp_variable', 'multiply_variable', 'multiply_temp_variable',
                   'divide_variable', 'divide_temp_variable'):
            assert len(val) == 1, ('Native variable assignment shape', key, val)
            field, op, rhs = val[0]; assert op == '=' and not isinstance(rhs, list)
            dest, field = destination(result, ctx, field, 'temp_variable' in key)
            wanted = value(result, ctx, rhs)
            old = dest[field] if isinstance(dest, list) else dest.get(field, 0)
            if key.startswith('set_'): dest[field] = wanted
            elif key.startswith('add_'): dest[field] = old + wanted
            elif key.startswith('subtract_'): dest[field] = old - wanted
            elif key.startswith('multiply_'): dest[field] = old * wanted
            else:
                assert wanted != 0, ('Unguarded native divide by zero in declared fixture', field)
                dest[field] = old / wanted
        elif key == 'clear_variable':
            dest, field = destination(result, ctx, val); assert not isinstance(dest, list)
            dest.pop(field, None)
        elif key in ('clamp_variable', 'clamp_temp_variable'):
            parameters = {name: wanted for name, op, wanted in val}
            dest, field = destination(result, ctx, parameters['var'], key == 'clamp_temp_variable')
            current = dest[field] if isinstance(dest, list) else dest.get(field, 0)
            if 'min' in parameters: current = max(current, value(result, ctx, parameters['min']))
            if 'max' in parameters: current = min(current, value(result, ctx, parameters['max']))
            dest[field] = current
        elif key in ('add_to_array', 'remove_from_array'):
            array = array_ref(result, ctx, one(val, 'array'))
            if key == 'add_to_array': array.append(value(result, ctx, one(val, 'value')))
            elif any(name == 'index' for name, op, wanted in val):
                position = int(value(result, ctx, one(val, 'index')))
                assert 0 <= position < len(array), ('Invalid native remove index', position, array)
                array.pop(position)
            else:
                wanted = value(result, ctx, one(val, 'value'))
                # Explicit native primitive fixture. Initial regressions do not
                # depend on first-vs-all duplicate removal behavior.
                if wanted in array: array.remove(wanted)
        elif key == 'clear_array': array_ref(result, ctx, val).clear()
        elif key in ('for_each_loop', 'for_each_scope_loop'):
            parameters = {name: wanted for name, op, wanted in val if name in ('array', 'value', 'index', 'break')}
            body = [node for node in val if node[0] not in parameters]
            for position, element in enumerate(list(array_ref(result, ctx, parameters['array']))):
                result['temp'][parameters.get('value', 'v')] = element
                result['temp'][parameters.get('index', 'i')] = position
                if key == 'for_each_scope_loop':
                    assert element in result['countries'], ('Native scope array contains unknown country', element)
                    execute(body, result, switch(ctx, element))
                else: execute(body, result, ctx)
                if 'break' in parameters and value(result, ctx, parameters['break']): break
        elif key == 'force_update_dynamic_modifier':
            assert val == 'yes'
            result.setdefault('dynamic_updates', []).append(ctx['scope'])
        else: source_execute(grouped, result, ctx)

for namespace in (source, source['source'], source['source']['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute; namespace['value'] = value

missile_effects = ast(read('common/scripted_effects/00_missiles_scripted_effects.txt'))
for name in ('add_access_GNSS_civ_vars', 'add_offer_access_GNSS_civ_vars', 'add_access_COM_civ_vars', 'add_offer_access_COM_civ_vars',
             'add_treaty_COM_civ_receiver_num', 'update_COM_system_stats', 'add_treaty_COM_mil_receiver_num'):
    model['effects'][name] = one(missile_effects, name)
for registry, path in (('effects', 'common/scripted_effects/eon_satellite_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_satellite_triggers.txt'),
                       # The shared current COM reducer calls the extended
                       # canonical treaty helper. Load its real definitions;
                       # these do not execute or recount package13 scenarios.
                       ('effects', 'common/scripted_effects/eon_satellite_extended_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_satellite_extended_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, operator, body in ast(read(path))}
        assert not additions.keys() & model[registry].keys(), 'Satellite helpers overwrite a prior helper'
        model[registry].update(additions)
actions = one(ast(read('common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt')), 'scripted_diplomatic_actions')
model['capacity_triggers']['NOT_share_COM_civ_satellites_above_network_traffic_limit'] = one(
    ast(read('common/scripted_triggers/MD_missile_scripted_triggers.txt')),
    'NOT_share_COM_civ_satellites_above_network_traffic_limit')
extra_actions = ROOT / 'common/scripted_diplomatic_actions/eon_satellite_actions.txt'
if extra_actions.exists():
    additions = one(ast(extra_actions.read_text(encoding='utf-8-sig')), 'scripted_diplomatic_actions')
    assert not {key for key, op, body in additions} & {key for key, op, body in actions}
    actions += additions

FACTORS = {'GNSS': ('production_speed_buildings_factor', 'production_speed_infrastructure_factor', 'local_resources_factor'),
           'COM': ('political_power_factor', 'decryption_factor', 'encryption_factor', 'intel_network_gain_factor', 'operation_outcome')}

def state():
    result = source['state']()
    result['global'] = {'variables': {}, 'arrays': {}}
    for actor, country in result['countries'].items():
        for family, factors in FACTORS.items():
            country['variables']['var_' + family + '_civ_system_idx'] = 0 if actor == 'A' else 3
            for suffix in ('access_array', 'treaty_array', 'access_system_idx_array'):
                country['arrays'][family + '_civ_' + suffix] = []
            for factor in factors:
                name = family + '_civ_' + factor
                country['variables']['var_' + name + '_base'] = .01 if actor == 'A' else .03
                country['variables']['var_' + name] = country['variables']['var_' + name + '_base']
                result['global']['arrays'][name + '_max_array'] = [0, .1, .2, .3, .4, .5, .6, .7]
        country['variables'].update(num_controlled_states=1, var_COM_civ_receiver_num=100,
                                    var_COM_civ_receiver_cap=1000, var_COM_civ_sat_system_num=10,
                                    var_COM_civ_sat_system_max=10)
    return result

def effect(result, identity, entry='complete_effect', actor='A', partner='B'):
    result['temp'] = {}
    body = one(actions, identity)
    optional = [nodes for name, op, nodes in body if name == entry]
    assert len(optional) <= 1
    if optional: execute(optional[0], result, context(actor, scope=partner))

def grants(result, recipient='A', family='GNSS'):
    return result['countries'][recipient]['arrays'][family + '_civ_access_array']

def indices(result, recipient='A', family='GNSS'):
    return result['countries'][recipient]['arrays'][family + '_civ_access_system_idx_array']

def check(result, identity, entry, actor='A', partner='B'):
    result['temp'] = {}
    bodies = [body for name, op, body in one(actions, identity) if name == entry]
    assert len(bodies) <= 1
    return not bodies or trigger(bodies[0], result, context(actor, scope=partner))

def send(result, family='gnss', kind='request', actor='A', partner='B', force=False):
    identity = kind + '_civ_' + family + '_access'
    ready = all(check(result, identity, entry, actor, partner) for entry in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    assert float(one(one(actions, identity), 'cost')) == 0, 'Civilian proposal gained an unexpected native cost'
    if ready or force: effect(result, identity, 'on_sent_effect', actor, partner)
    return ready

def response(result, family='gnss', kind='request', accepted=True, actor='A', partner='B', force=False):
    identity = kind + '_civ_' + family + '_access'
    native_ready = not accepted or check(result, identity, 'can_be_accepted', actor, partner)
    result['temp'] = {}
    # The current action has no native acceptance gate. Report its actual
    # scripted authorization separately while delivering the actual callback;
    # an invalid consumed answer clears its owned record without a grant.
    authorized = not accepted or trigger([('eon_sat_' + family + '_' + kind + '_authorized', '=', 'yes')],
                                         result, switch(context(actor, scope=partner), actor))
    if native_ready or force: effect(result, identity, 'complete_effect' if accepted else 'reject_effect', actor, partner)
    return native_ready and authorized

def helper(result, name, actor='A', partner=None, temporary=None):
    result['temp'] = dict(temporary or {})
    ctx = context(actor) if partner is None else switch(context(actor, scope=partner), actor)
    execute([(name, '=', 'yes')], result, ctx)

def pending(result, family='gnss', actor='A'):
    country = result['countries'][actor]
    return (country['variables'].get('eon_sat_' + family + '_partner', 0),
            country['variables'].get('eon_sat_' + family + '_kind', 0),
            country['variables'].get('eon_sat_' + family + '_level', 0),
            frozenset(flag for flag in country['flags'] if flag.startswith('eon_sat_' + family + '_')))

def snapshot(result):
    return deepcopy(result['countries'])

def withdraw(result, family='gnss', actor='A', force=False):
    decisions = one(ast(read('common/decisions/eon_satellite_decisions.txt')), 'eon_satellite_agreements')
    body = one(decisions, 'eon_withdraw_civ_' + family + '_proposal')
    assert float(one(body, 'cost')) == 0
    ctx = context(actor); result['temp'] = {}
    ready = all(trigger(one(body, entry), result, ctx) for entry in ('allowed', 'visible', 'available'))
    if ready or force: execute(one(body, 'complete_effect'), result, ctx)
    return ready

def daily(result, actor='A'):
    hooks = one(ast(read('common/on_actions/eon_satellite_on_actions.txt')), 'on_actions')
    result['temp'] = {}
    execute(one(one(hooks, 'on_daily'), 'effect'), result, context(actor))

def annex(result, victim='A', subject=False):
    hooks = one(ast(read('common/on_actions/eon_satellite_on_actions.txt')), 'on_actions')
    ctx = context(victim, 'D') if subject else context('D', victim)
    result['temp'] = {}
    execute(one(one(hooks, 'on_subject_annexed' if subject else 'on_annex'), 'effect'), result, ctx)

def seed_consent(result, family='GNSS', recipient='A', provider='B', duplicates=1):
    result['countries'][recipient]['arrays'][family + '_civ_access_array'].extend([provider] * duplicates)
    result['countries'][provider]['arrays'][family + '_civ_treaty_array'].extend([recipient] * duplicates)
    result['countries'][recipient]['arrays'][family + '_civ_access_system_idx_array'].extend([3] * duplicates)

def unchanged_non_civilian(result):
    return {actor: {key: deepcopy(value) for key, value in data.items() if key not in ('variables', 'arrays', 'flags')}
            | {'variables': {key: deepcopy(value) for key, value in data['variables'].items()
                             if not key.startswith(('eon_sat_', 'var_GNSS_civ_', 'var_COM_civ_', 'temp_GNSS_civ_', 'temp_COM_civ_'))
                             and key not in ('pending_civ_access_country', 'pending_civ_com_access_country', 'var_treaty_COM_civ_receiver_num', 'var_sat_network_traffic_civ')},
               'arrays': {key: deepcopy(value) for key, value in data['arrays'].items()
                          if not key.startswith(('GNSS_civ_', 'COM_civ_', 'eon_sat_'))},
               'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_sat_', 'recently_accepted_civ_gnss', 'recently_revoke_civ_', 'recently_accepted_mil_com'))}}
            for actor, data in result['countries'].items()}

# Focused actual-source regressions. Root must observe RED before gameplay edits.
focus = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == '--focus' else None
assert focus in (None, 'duplicate', 'index', 'orphan', 'pending', 'receivers'), ('Unknown focused proof', sys.argv[1:])
if focus in (None, 'duplicate'):
    result = state()
    effect(result, 'request_civ_gnss_access', 'on_sent_effect')
    effect(result, 'request_civ_gnss_access')
    effect(result, 'request_civ_gnss_access')
    assert grants(result) == ['B'] and indices(result) == [3], ('Repeated accepted callback duplicated civilian provider', grants(result), indices(result))
    groups['accepted_callback_grants_each_provider_once'] += 1
if focus in (None, 'index'):
    result = state()
    for peer in ('B', 'C'):
        effect(result, 'request_civ_gnss_access', 'on_sent_effect', partner=peer)
        effect(result, 'request_civ_gnss_access', partner=peer)
    result['countries']['B']['variables']['var_GNSS_civ_system_idx'] = 5
    effect(result, 'revoke_civ_gnss_access', actor='B', partner='A')
    assert grants(result) == ['C'] and indices(result) == [3], ('Revoke used changed provider index instead of rebuilding recipient cache', grants(result), indices(result))
    groups['revoke_rebuilds_live_index_for_remaining_equal_provider'] += 1
if focus in (None, 'orphan'):
    result = state()
    effect(result, 'request_civ_gnss_access', 'on_sent_effect', partner='C')
    effect(result, 'request_civ_gnss_access', partner='C')
    effect(result, 'revoke_civ_gnss_access', actor='B', partner='A')
    assert grants(result) == ['C'] and indices(result) == [3], ('Unowned forced revoke destroyed a different provider cache', grants(result), indices(result))
    groups['unowned_revoke_cannot_modify_other_provider'] += 1
if focus in (None, 'pending'):
    result = state()
    result['countries']['A']['variables']['var_GNSS_civ_system_idx'] = 3
    effect(result, 'offer_civ_gnss_access', 'on_sent_effect')
    effect(result, 'offer_civ_gnss_access', 'reject_effect')
    effect(result, 'offer_civ_gnss_access', 'on_sent_effect', partner='C')
    effect(result, 'offer_civ_gnss_access', 'reject_effect')
    assert result['countries']['A']['variables'].get('pending_civ_access_country') == 'C', ('Old civilian reject cleared later different-partner pending owner', result['countries']['A']['variables'].get('pending_civ_access_country'))
    groups['civilian_response_preserves_different_partner_pending_owner'] += 1
if focus in (None, 'receivers'):
    result = state()
    result['countries']['A']['arrays']['COM_civ_treaty_array'] = ['B', 'C']
    result['countries']['B']['arrays']['COM_civ_access_array'] = ['A']
    result['countries']['C']['arrays']['COM_civ_access_array'] = ['A']
    result['countries']['B']['variables']['num_controlled_states'] = 2
    result['countries']['C']['variables']['num_controlled_states'] = 5
    result['countries']['A']['variables']['var_COM_civ_receiver_num'] = 100
    execute([('add_treaty_COM_civ_receiver_num', '=', 'yes')], result, context('A'))
    variables = result['countries']['A']['variables']
    assert variables.get('var_treaty_COM_civ_receiver_num') == 700 and variables['var_COM_civ_receiver_num'] == 800, ('Receiver load dropped all recipients except the last', variables.get('var_treaty_COM_civ_receiver_num'), variables['var_COM_civ_receiver_num'])
    groups['COM_receiver_load_counts_all_current_civilian_recipients'] += 1

if focus is None:
    for family in ('gnss', 'com'):
        upper = family.upper()
        for kind in ('request', 'offer'):
            result = state()
            actor, peer = 'A', 'B'
            provider, recipient = (peer, actor) if kind == 'request' else (actor, peer)
            if kind == 'offer':
                result['countries'][provider]['variables']['var_' + upper + '_civ_system_idx'] = 3
                result['countries'][recipient]['variables']['var_' + upper + '_civ_system_idx'] = 0
            original_pp = {key: data['variables']['political_power'] for key, data in result['countries'].items()}
            provider_base = {factor: result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor]
                             for factor in FACTORS[upper]}
            assert send(result, family, kind)
            assert pending(result, family)[:3] == (peer, 1 if kind == 'request' else 2, 3), (family, kind, pending(result, family))
            assert ('A', 'eon_sat_' + family + '_window', 30.0) in result.get('timer_declarations', [])
            assert response(result, family, kind)
            assert grants(result, recipient, upper) == [provider] and indices(result, recipient, upper) == [3]
            assert result['countries'][provider]['arrays'][upper + '_civ_treaty_array'] == [recipient]
            assert pending(result, family)[:3] == (0, 0, 0)
            assert original_pp == {key: data['variables']['political_power'] for key, data in result['countries'].items()}
            for factor in FACTORS[upper]:
                name = 'var_' + upper + '_civ_' + factor
                expected = result['countries'][recipient]['variables'][name + '_base'] + result['countries'][provider]['variables'][name + '_base']
                assert model['compare'](result['countries'][recipient]['variables'][name], '=', expected)
                assert model['compare'](result['countries'][provider]['variables'][name], '=', provider_base[factor])
            response(result, family, kind, force=True)
            assert grants(result, recipient, upper) == [provider] and indices(result, recipient, upper) == [3]
            groups['four_free_native_request_offer_routes_own_frozen_terms_consume_once_and_credit_only_recipient'] += 1

            result = state()
            if kind == 'offer':
                result['countries']['A']['variables']['var_' + upper + '_civ_system_idx'] = 3
                result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0
            assert send(result, family, kind)
            response(result, family, kind, accepted=False)
            assert pending(result, family)[:3] == (0, 0, 0) and not grants(result, recipient, upper)
            assert send(result, family, kind), 'Consumed refusal must allow a fresh serialized proposal'
            groups['consumed_refusal_changes_no_grant_and_allows_fresh_round'] += 1

        result = state()
        assert send(result, family)
        owned = snapshot(result)
        assert not send(result, family, partner='C')
        send(result, family, partner='C', force=True)
        assert snapshot(result) == owned, 'Forced cached target cannot overwrite current serialized proposal'
        response(result, family, 'offer', force=True)
        assert snapshot(result) == owned, 'Wrong request/offer callback kind cannot consume current proposal'
        response(result, family, partner='C', force=True)
        assert snapshot(result) == owned, 'Wrong partner callback cannot consume current proposal'
        groups['fresh_serialization_blocks_overwrite_wrong_kind_and_wrong_partner_callbacks'] += 1

        for mutation in ('provider upgraded', 'provider lost system', 'recipient upgraded', 'peer absent', 'direct war', 'response window expired'):
            result = state(); assert send(result, family)
            if mutation == 'provider upgraded': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 5
            elif mutation == 'provider lost system': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0
            elif mutation == 'recipient upgraded': result['countries']['A']['variables']['var_' + upper + '_civ_system_idx'] = 4
            elif mutation == 'peer absent': result['countries']['B']['exists'] = False
            elif mutation == 'direct war': result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
            else: result['countries']['A']['flags'].discard('eon_sat_' + family + '_window')
            assert not response(result, family), (family, mutation, pending(result, family))
            response(result, family, force=True)
            assert not grants(result, 'A', upper) and pending(result, family)[:3] == (0, 0, 0), (family, mutation, pending(result, family))
            groups['actual_acceptance_rechecks_current_frozen_level_liveness_peace_eligibility_and_response_deadline'] += 1

    result = state()
    assert send(result, 'gnss', partner='B') and send(result, 'com', partner='C')
    com_owned = pending(result, 'com')
    response(result, 'gnss', accepted=False)
    assert pending(result, 'com') == com_owned
    assert response(result, 'com', partner='C') and grants(result, 'A', 'COM') == ['C'] and not grants(result)
    groups['GNSS_and_COM_pending_pipelines_are_independent'] += 1

    for family, old_pointer in (('gnss', 'pending_civ_access_country'), ('com', 'pending_civ_com_access_country')):
        result = state(); result['countries']['A']['variables'][old_pointer] = 'C'
        assert not send(result, family)
        before = snapshot(result)
        response(result, family, accepted=False, force=True)
        response(result, family, force=True)
        assert snapshot(result) == before, 'Unidentified legacy reply must preserve unknown pending ownership'
        other = 'com' if family == 'gnss' else 'gnss'
        assert send(result, other), 'Unmanaged pointer must not lock a separate family'
        groups['unmanaged_legacy_family_pointer_is_preserved_and_does_not_lock_other_family'] += 1

    for family in ('gnss', 'com'):
        upper = family.upper()
        for kind in ('request', 'offer'):
            result = state()
            if kind == 'offer':
                result['countries']['A']['variables']['var_' + upper + '_civ_system_idx'] = 3
                result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0
            assert send(result, family, kind)
            owned = pending(result, family)
            assert not withdraw(result, family, actor='B'), 'Peer has no ownership of the actor-only outgoing proposal'
            withdraw(result, family, actor='B', force=True)
            assert pending(result, family) == owned
            original_pp = result['countries']['A']['variables']['political_power']
            assert withdraw(result, family)
            assert pending(result, family)[:3] == owned[:3] and 'eon_sat_' + family + '_cancelled' in pending(result, family)[3]
            assert not withdraw(result, family)
            assert not send(result, family, partner='C'), 'Withdrawal must hold the serialized slot until the original reply is consumed'
            assert not response(result, family, kind)
            recipient = 'A' if kind == 'request' else 'B'
            assert not grants(result, recipient, upper) and pending(result, family)[:3] == (0, 0, 0)
            assert result['countries']['A']['variables']['political_power'] == original_pp
            assert send(result, family, kind), 'Consumed withdrawal reply allows a fresh round without forced retirement'
            groups['four_human_free_withdrawals_hold_original_identity_and_consume_without_grant_or_cost'] += 1

        for mutation in ('AI actor', 'dead actor', 'no owned proposal'):
            result = state()
            if mutation != 'no owned proposal': assert send(result, family)
            if mutation == 'AI actor': result['countries']['A']['ai'] = True
            elif mutation == 'dead actor': result['countries']['A']['exists'] = False
            before = snapshot(result)
            assert not withdraw(result, family)
            withdraw(result, family, force=True)
            assert snapshot(result) == before
            groups['withdrawal_current_human_liveness_and_owned_pending_guards'] += 1

        for mutation in ('expired window', 'dead peer', 'zero peer', 'changed tier', 'direct war'):
            result = state(); assert send(result, family)
            if mutation == 'expired window': result['countries']['A']['flags'].discard('eon_sat_' + family + '_window')
            elif mutation == 'dead peer': result['countries']['B']['exists'] = False
            elif mutation == 'zero peer': result['countries']['A']['variables']['eon_sat_' + family + '_partner'] = 0
            elif mutation == 'changed tier': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 5
            else: result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
            daily(result)
            if mutation in ('changed tier', 'direct war'):
                assert pending(result, family)[:3] == ('B', 1, 3) and 'eon_sat_' + family + '_cancelled' in pending(result, family)[3]
                assert not send(result, family, partner='C')
                # Invalid policy is held for the original modal, rather than
                # force released while it may still be unconsumed.
                response(result, family, accepted=False)
                assert pending(result, family)[:3] == (0, 0, 0)
            else:
                assert pending(result, family)[:3] == (0, 0, 0)
                if mutation != 'zero peer':
                    assert 'eon_sat_' + family + '_quarantine@B' in result['countries']['A']['flags']
                    result['countries']['B']['exists'] = True
                    assert not send(result, family)
                    assert send(result, family, partner='C')
                    active_c = pending(result, family)
                    response(result, family, force=True)
                    assert pending(result, family) == active_c and not grants(result, 'A', upper)
            groups['daily_forced_cleanup_quarantines_known_pair_while_policy_change_keeps_original_reply_lock'] += 1

        result = state()
        result['countries']['A']['variables'].update({'eon_sat_' + family + '_partner': 'D', 'eon_sat_' + family + '_kind': 2,
                                                     'eon_sat_' + family + '_level': 7})
        result['countries']['A']['flags'].update({'eon_sat_' + family + '_cancelled', 'eon_sat_' + family + '_window'})
        assert send(result, family) and response(result, family) and grants(result, 'A', upper) == ['B']
        groups['fresh_unreserved_family_initialization_clears_orphans_without_poisoning_reply'] += 1

        for subject in (False, True):
            for victim in ('A', 'B'):
                result = state(); assert send(result, family)
                result['countries'][victim]['exists'] = False
                annex(result, victim, subject)
                assert pending(result, family)[:3] == (0, 0, 0)
                assert 'eon_sat_' + family + '_quarantine@B' in result['countries']['A']['flags']
                result['countries'][victim]['exists'] = True
                assert not send(result, family)
                assert send(result, family, partner='C')
                owned_c = pending(result, family)
                response(result, family, force=True)
                assert pending(result, family) == owned_c and not grants(result, 'A', upper)
                groups['both_native_annex_hooks_for_each_pending_role_keep_retirement_with_original_actor'] += 1

        for subject in (False, True):
            result = state(); assert send(result, family) and response(result, family)
            # Explicit callback-order fixture: native existence has not flipped
            # yet. The victim's arrays clear before survivor canonicalization.
            annex(result, 'B', subject)
            assert not grants(result, 'A', upper) and not indices(result, 'A', upper)
            assert not result['countries']['B']['arrays'][upper + '_civ_treaty_array']
            groups['active_annex_removes_consent_even_with_preflip_existence_fact'] += 1

        for mutation in ('duplicate equal providers', 'provider changed tier', 'provider dormant zero', 'provider below own tier',
                         'provider invalid fractional tier', 'provider beyond supported tier', 'dead provider', 'direct war', 'unilateral access', 'self entry'):
            result = state()
            seed_consent(result, upper, duplicates=2 if mutation == 'duplicate equal providers' else 1)
            seed_consent(result, upper, provider='C')
            if mutation == 'provider changed tier': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 5
            elif mutation == 'provider dormant zero': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0
            elif mutation == 'provider below own tier': result['countries']['A']['variables']['var_' + upper + '_civ_system_idx'] = 4
            elif mutation == 'provider invalid fractional tier': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 3.5
            elif mutation == 'provider beyond supported tier': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 8
            elif mutation == 'dead provider': result['countries']['B']['exists'] = False
            elif mutation == 'direct war': result['countries']['B']['wars'].add('A'); result['countries']['A']['wars'].add('B')
            elif mutation == 'unilateral access': result['countries']['B']['arrays'][upper + '_civ_treaty_array'] = []
            elif mutation == 'self entry':
                result['countries']['A']['arrays'][upper + '_civ_access_array'].append('A')
                result['countries']['A']['arrays'][upper + '_civ_treaty_array'].append('A')
            helper(result, 'eon_sat_refresh_' + family)
            expected_providers = ['C'] if mutation in ('dead provider', 'unilateral access') else ['B', 'C']
            expected_indices = [3] if len(expected_providers) == 1 else [5 if mutation == 'provider changed tier' else 0 if mutation in ('provider dormant zero', 'provider invalid fractional tier', 'provider beyond supported tier') else 3, 3]
            assert grants(result, 'A', upper) == expected_providers and indices(result, 'A', upper) == expected_indices, (family, mutation, grants(result, 'A', upper), indices(result, 'A', upper))
            eligible = [] if mutation == 'provider below own tier' else [provider for provider in expected_providers
                       if provider != 'B' or mutation not in ('provider dormant zero', 'provider invalid fractional tier', 'provider beyond supported tier', 'direct war')]
            for factor in FACTORS[upper]:
                name = 'var_' + upper + '_civ_' + factor
                expected = result['countries']['A']['variables'][name + '_base'] + sum(result['countries'][provider]['variables'][name + '_base'] for provider in eligible)
                assert model['compare'](result['countries']['A']['variables'][name], '=', expected), (family, mutation, name, result['countries']['A']['variables'][name], expected)
            groups['canonical_live_provider_IDs_dedup_cache_current_tier_retain_dormant_consent_and_filter_invalid_bonus'] += 1

        result = state()
        seed_consent(result, upper, duplicates=3); seed_consent(result, upper, provider='C', duplicates=2)
        helper(result, 'eon_sat_refresh_' + family, 'B'); helper(result, 'eon_sat_refresh_' + family, 'C')
        for factor in FACTORS[upper]: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][3] = .035
        helper(result, 'eon_sat_refresh_' + family)
        assert grants(result, 'A', upper) == ['B', 'C'] and indices(result, 'A', upper) == [3, 3]
        assert result['countries']['B']['arrays'][upper + '_civ_treaty_array'] == ['A']
        effect(result, 'revoke_civ_' + family + '_access', actor='B', partner='A')
        assert grants(result, 'A', upper) == ['C'] and indices(result, 'A', upper) == [3]
        for factor in FACTORS[upper]: assert model['compare'](result['countries']['A']['variables']['var_' + upper + '_civ_' + factor], '=', .035)
        before = snapshot(result)
        effect(result, 'revoke_civ_' + family + '_access', actor='B', partner='A')
        assert snapshot(result) == before
        effect(result, 'revoke_civ_' + family + '_access', actor='C', partner='A')
        assert not grants(result, 'A', upper) and not indices(result, 'A', upper)
        for factor in FACTORS[upper]:
            name = 'var_' + upper + '_civ_' + factor
            assert model['compare'](result['countries']['A']['variables'][name], '=', result['countries']['A']['variables'][name + '_base'])
        groups['equal_tier_duplicate_legacy_consent_caps_once_revoke_one_provider_and_return_to_own_base'] += 1

        for level in (0, 1, 7, 8, -1, 3.5):
            result = state(); result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = level
            ready = send(result, family)
            assert ready == (level in (1, 7)), (family, level, ready)
            if ready: assert response(result, family) and indices(result, 'A', upper) == [level]
            else:
                before = snapshot(result); send(result, family, force=True)
                assert snapshot(result) == before
            groups['literal_supported_provider_tiers_and_fresh_forced_entry_guard'] += 1

    for controlled_states, expected_treaty, expected_traffic, expected_bonus in ((2, 700, .8, 1), (10, 1500, 1.6, .4), (30, 3500, 3.6, 0)):
        result = state(); provider = result['countries']['A']
        provider['variables'].update(var_COM_civ_system_idx=3, var_COM_mil_system_idx=3, var_COM_mil_sat_system_max=10,
                                     num_battalions=0, num_ships=0, num_deployed_planes=0)
        provider['arrays']['COM_satellite_array'] = [0, 0, 0, 10, 0, 0, 0, 0]
        provider['arrays']['COM_sat_receiver_tech_array'] = [100] * 8
        provider['arrays']['COM_mil_treaty_array'] = []
        seed_consent(result, 'COM', recipient='B', provider='A', duplicates=2)
        seed_consent(result, 'COM', recipient='C', provider='A')
        result['countries']['B']['variables']['num_controlled_states'] = controlled_states
        result['countries']['C']['variables']['num_controlled_states'] = 5
        helper(result, 'update_COM_system_stats')
        variables = provider['variables']
        assert variables['var_treaty_COM_civ_receiver_num'] == expected_treaty
        assert variables['var_COM_civ_receiver_num'] == expected_treaty + 100
        assert model['compare'](variables['var_sat_network_traffic_civ'], '=', expected_traffic)
        assert model['compare'](variables['var_COM_civ_sat_system_bonus'], '=', expected_bonus)
        groups['actual_unchanged_COM_traffic_and_coverage_formula_uses_all_deduplicated_recipient_load_and_clamps_bonus'] += 1

    for traffic, capacity, existing_load, target_states, expected in ((1.25, 1000, 1000, 1, True), (.9, 1000, 900, 3, False),
                                                                  (.9, 1000, 900, 4, True), (1, 1000, 1000, 10, False)):
        result = state()
        result['countries']['A']['variables'].update(var_sat_network_traffic_civ=traffic, var_COM_civ_receiver_cap=capacity,
                                                     var_COM_civ_receiver_num=existing_load)
        result['countries']['B']['variables']['num_controlled_states'] = target_states
        result['temp'] = {}
        passed = trigger([('NOT_share_COM_civ_satellites_above_network_traffic_limit', '=', 'yes')], result, context('A', scope='B'))
        assert passed == expected, (traffic, existing_load, target_states, passed)
        groups['unchanged_COM_AI_load_policy_native_current_and_projected_thresholds_are_soft_facts'] += 1

    result = state()
    for country in result['countries'].values():
        country['arrays']['GNSS_mil_access_array'] = ['D']
        country['arrays']['COM_mil_access_array'] = ['C']
        country['arrays']['SPY_civ_access_array'] = ['B']
        country['variables'].update(var_GNSS_mil_system_idx=7, var_COM_mil_system_idx=6, var_SPY_civ_system_idx=5,
                                    pending_mil_access_country='D', pending_mil_com_access_country='C', pending_civ_spy_access_country='B')
        country['flags'].update({'anti_terror_agreement@D', 'eon_ct_contribution@D'})
    before = unchanged_non_civilian(result)
    assert send(result, 'gnss') and response(result, 'gnss')
    assert send(result, 'com', partner='C')
    assert withdraw(result, 'com')
    response(result, 'com', accepted=False, partner='C')
    effect(result, 'revoke_civ_gnss_access', actor='B', partner='A')
    daily(result)
    assert unchanged_non_civilian(result) == before
    groups['civilian_lifecycle_preserves_military_spy_satellites_economy_energy_CT_and_other_diplomacy'] += 1

source_paths = ('common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt',
                'common/scripted_effects/00_missiles_scripted_effects.txt',
                'common/scripted_effects/eon_satellite_effects.txt', 'common/scripted_triggers/eon_satellite_triggers.txt',
                'common/decisions/eon_satellite_decisions.txt', 'common/decisions/categories/eon_satellite_categories.txt',
                'common/on_actions/eon_satellite_on_actions.txt', 'localisation/english/eon_satellite_l_english.yml',
                'localisation/russian/eon_satellite_l_russian.yml')
print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'adapter_semantics_cases': 0,
                  'total_cases': sum(groups.values()), 'groups': dict(groups), 'baseline': BASELINE,
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths if (ROOT / path).exists()},
                  'proof_scope': 'bounded ordered actual-source civilian satellite access; not HOI4 runtime',
                  'not_proven': ['native callback or timer implementation', 'elapsed 30-day expiry', 'country-valued array native implementation',
                                 'first-versus-all duplicate removal behavior', 'arbitrary duplicate consumed callback into a later identical proposal',
                                 'complete AI political-policy outcomes', 'playable HOI4 campaign']}, indent=2))
