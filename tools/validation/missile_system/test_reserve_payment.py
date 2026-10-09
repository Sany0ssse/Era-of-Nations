"""Execute the actual scripted AI reserve payment helper with bounded stock.

Native stockpile removal is an explicit fixture input until separately
observed in the game; this suite exercises the real helper's family choice,
quantity boundaries, readiness and the post-payment success check.
"""
from copy import deepcopy
import json

from test_launch import one, read
from readiness_model import assert_default_off_contract, is_ready

SHORT = 'nuclear_ballistic_missile_equipment'
LONG = 'nuclear_missile_equipment'
HELPER = one(read('common/scripted_effects/eon_nuclear_scripted_launch_effects.txt'), 'eon_nuclear_scripted_pay_reserve')


def value(state, key):
    if key.startswith('num_equipment@'):
        family = key.split('@', 1)[1]
        # Native positive-save probes show this getter is reserve stock only.
        return state['stock'][family]
    if key in state['temp']:
        return state['temp'][key]
    if key in state['variables']:
        return state['variables'][key]
    return float(key)


def predicate(nodes, state):
    result = []
    for key, op, body in nodes:
        if key == 'OR':
            allowed = any(predicate([child], state) for child in body)
        elif key == 'eon_nuclear_arsenal_ready':
            allowed = is_ready(state['ready'], state['flags'],
                               state['variables'].get('eon_nuclear_arsenal_recovery_remaining', 0),
                               state.get('prototype_enabled')) == (body == 'yes')
        elif key == 'check_variable':
            assert len(body) == 1
            variable, operator, expected = body[0]
            actual, expected = value(state, variable), value(state, expected)
            assert operator == '='
            allowed = actual == expected
        elif key == 'has_equipment':
            assert len(body) == 1
            family, operator, expected = body[0]
            assert operator == '>', 'has_equipment accepts the proven strict > syntax'
            allowed = state['stock'][family] > value(state, expected)
        else:
            raise AssertionError(('Unknown payment predicate', key, op, body))
        result.append(allowed)
    return all(result)


def execute(nodes, state):
    branch_taken = None
    for key, op, body in nodes:
        if key in ('if', 'else_if'):
            if key == 'if':
                branch_taken = False
            assert branch_taken is not None
            if not branch_taken and predicate(one(body, 'limit'), state):
                branch_taken = True
                execute([node for node in body if node[0] != 'limit'], state)
        elif key in ('set_temp_variable', 'set_variable', 'subtract_from_temp_variable'):
            variables = state['variables'] if key == 'set_variable' else state['temp']
            for variable, operator, quantity in body:
                assert operator == '='
                amount = value(state, quantity)
                variables[variable] = variables[variable]-amount if key == 'subtract_from_temp_variable' else amount
        elif key == 'clr_country_flag':
            state['flags'].discard(body)
        elif key == 'set_country_flag':
            state['flags'].add(body)
        elif key == 'add_equipment_to_stockpile':
            family, amount = one(body, 'type'), value(state, one(body, 'amount'))
            assert set(node[0] for node in body) == {'type', 'amount'}, 'Removal must apply to all creators without a transfer target'
            if not state['native_transfer_fails']:
                assert amount < 0 and state['stock'][family] >= -amount
                state['stock'][family] += amount
                state['sink'][family] -= amount
        else:
            raise AssertionError(('Unknown payment effect', key, op, body))


def fixture(short, long, request, ready=True, transfer_fails=False, prototype_enabled=None):
    return {'stock': {SHORT: short, LONG: long}, 'deployed': {SHORT: 20, LONG: 10},
            'sink': {SHORT: 0, LONG: 0}, 'variables': {}, 'flags': {'eon_nuclear_scripted_reserve_paid'},
            'temp': {'eon_nuclear_scripted_request': request}, 'ready': ready,
            'native_transfer_fails': transfer_fails, 'prototype_enabled': prototype_enabled}


def verify_case(helper, short, long, request, ready, removal_fails, prototype_enabled=True):
    state = fixture(short, long, request, ready, removal_fails, prototype_enabled)
    before = deepcopy(state)
    execute(helper, state)
    allowed = (ready or prototype_enabled is not True) and request in (1, 10) and (short >= request or long >= request)
    paid = allowed and not removal_fails
    assert ('eon_nuclear_scripted_reserve_paid' in state['flags']) == paid
    family = SHORT if allowed and short >= request else LONG
    assert state['variables']['eon_nuclear_scripted_paid_family'] == (1 if paid and family == SHORT else 2 if paid else 0)
    assert state['variables']['eon_nuclear_scripted_paid_amount'] == (request if paid else 0)
    for kind in (SHORT, LONG):
        expected = request if paid and kind == family else 0
        assert before['stock'][kind]-state['stock'][kind] == state['sink'][kind] == expected
        assert state['deployed'][kind] == before['deployed'][kind]


def run():
    assert_default_off_contract()
    cases = 0
    for request in (0, 1, 10, 11, -1):
        for short in (0, 1, 9, 10, 11, 1000):
            for long in (0, 1, 9, 10, 11, 1000):
                for ready in (False, True):
                    for removal_fails in (False, True):
                        verify_case(HELPER, short, long, request, ready, removal_fails)
                        cases += 1
    default_off_cases = 0
    for request in (0, 1, 10, 11, -1):
        for short, long in ((0, 0), (1, 1), (9, 0), (10, 10), (0, 10)):
            for removal_fails in (False, True):
                verify_case(HELPER, short, long, request, False, removal_fails, prototype_enabled=None)
                default_off_cases += 1
    stale = fixture(10, 10, 1, ready=False)
    stale['flags'].add('eon_nuclear_arsenal_safety_mode')
    stale['variables']['eon_nuclear_arsenal_recovery_remaining'] = 4
    execute(HELPER, stale)
    assert stale['stock'] == {SHORT: 9, LONG: 10} and 'eon_nuclear_scripted_reserve_paid' in stale['flags']
    default_off_cases += 1
    def walk(nodes):
        for node in nodes:
            yield node
            if isinstance(node[2], list):
                yield from walk(node[2])
    mutants = []
    for mutation in ('positive_amount', 'second_family', 'producer_restricted', 'readiness_bypass', 'payment_verification_bypass'):
        mutant = deepcopy(HELPER)
        nodes = list(walk(mutant))
        first_remove = next(node[2] for node in nodes if node[0] == 'add_equipment_to_stockpile')
        if mutation == 'positive_amount':
            first_remove[1] = ('amount', '=', 'eon_nuclear_scripted_request')
        elif mutation == 'second_family':
            parent = next(node[2] for node in nodes if isinstance(node[2], list) and any(child[0] == 'add_equipment_to_stockpile' for child in node[2]))
            parent.append(('add_equipment_to_stockpile', '=', [('type', '=', LONG), ('amount', '=', 'eon_nuclear_scripted_remove_amount')]))
        elif mutation == 'producer_restricted':
            first_remove.append(('producer', '=', 'THIS'))
        elif mutation == 'readiness_bypass':
            limit = next(node[2] for node in nodes if node[0] == 'limit' and any(child[0] == 'eon_nuclear_arsenal_ready' for child in node[2]))
            limit[:] = [child for child in limit if child[0] != 'eon_nuclear_arsenal_ready']
        else:
            limit = next(node[2] for node in nodes if node[0] == 'limit' and any(child[0] == 'check_variable' and child[2][0][0].startswith('num_equipment@') for child in node[2]))
            limit.clear()
        try:
            verify_case(mutant, 10, 10, 1, mutation != 'readiness_bypass', mutation == 'payment_verification_bypass')
        except AssertionError:
            mutants.append(mutation)
        else:
            raise AssertionError(('Undetected payment mutation', mutation))
    print(json.dumps({'status': 'PASS', 'actual_source_payment_cases': cases,
                      'default_off_payment_cases': default_off_cases,
                      'negative_controls_detected': mutants,
                      'scope': 'Actual disabled readiness plus explicit enabled prototype contract; source reserve removal outcome fixture boundary'}, indent=2))


if __name__ == '__main__':
    run()
