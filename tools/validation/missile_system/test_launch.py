"""Execute the current game launch predicates at their exact count boundaries.

This bounded source interpreter does not prove a native raid or rendered UI.
Native inventory/deployment counters require the separate game probe.
"""
from pathlib import Path
from copy import deepcopy
import json
import re

ROOT = Path(__file__).resolve().parents[3]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff')) if not m[0].startswith('#')]
    cursor = 0

    def parse():
        nonlocal cursor
        nodes = []
        while cursor < len(tokens) and tokens[cursor] != '}':
            key = tokens[cursor]
            cursor += 1
            if cursor >= len(tokens) or tokens[cursor] not in ('=', '<', '>', '<=', '>=', '!=', '=='):
                nodes.append(('__item__', '=', key))
                continue
            op = tokens[cursor]
            cursor += 1
            if tokens[cursor] == '{':
                cursor += 1
                value = parse()
                assert tokens[cursor] == '}'
                cursor += 1
            else:
                value = tokens[cursor]
                cursor += 1
            nodes.append((key, op, value))
        return nodes

    result = parse()
    assert cursor == len(tokens)
    return result


def one(nodes, key):
    found = [value for name, op, value in nodes if name == key]
    assert len(found) == 1, (key, len(found))
    return found[0]


def read(path):
    return ast((ROOT / path).read_text(encoding='utf-8-sig'))


def compare(actual, op, expected):
    return {'=': actual == expected, '==': actual == expected,
            '>': actual > expected, '<': actual < expected,
            '>=': actual >= expected, '<=': actual <= expected,
            '!=': actual != expected}[op]


def evaluate(nodes, state, scope='actor'):
    checks = []
    for key, op, value in nodes:
        country = state[scope]
        if key in ('tooltip', 'localization_key'):
            continue
        if key in ('custom_override_tooltip', 'custom_trigger_tooltip', 'AND'):
            result = evaluate(value, state, scope)
        elif key == 'OR':
            result = any(evaluate([item], state, scope) for item in value)
        elif key == 'NOT':
            result = not evaluate(value, state, scope)
        elif key == 'FROM':
            result = evaluate(value, state, 'target')
        elif key == 'ROOT':
            result = evaluate(value, state, 'actor')
        elif key == 'var:target_state':
            result = evaluate(value, state, 'state')
        elif key == 'if':
            condition = one(value, 'limit')
            result = not evaluate(condition, state, scope) or evaluate([node for node in value if node[0] != 'limit'], state, scope)
        elif key == 'set_temp_variable':
            for variable, assignment, amount in value:
                assert assignment == '='
                state['temp'][variable] = state['temp'][amount] if amount in state['temp'] else float(amount)
            continue
        elif key == 'subtract_from_temp_variable':
            for variable, assignment, amount in value:
                assert assignment == '='
                state['temp'][variable] -= state['temp'][amount] if amount in state['temp'] else float(amount)
            continue
        elif key == 'has_equipment':
            result = all(compare(country['inventory'].get(kind, 0), operator, state['temp'].get(amount, float(amount) if amount.replace('.', '', 1).isdigit() else 0)) for kind, operator, amount in value)
        elif key == 'check_variable':
            result = all(compare(country['variables'].get(variable, 0), operator, state['temp'].get(amount, float(amount) if amount.replace('.', '', 1).isdigit() else 0)) for variable, operator, amount in value)
        elif key == 'has_idea':
            result = value in country['ideas']
        elif key == 'has_country_flag':
            result = value in country['flags']
        elif key == 'has_global_flag':
            result = value in state['global_flags']
        elif key == 'exists':
            result = country['exists'] == (value == 'yes')
        elif key == 'has_war_with':
            assert value == 'FROM'
            result = country['war']
        elif key == 'is_ai':
            result = country['ai'] == (value == 'yes')
        elif key in ('is_owned_by', 'is_claimed_by'):
            assert value == 'ROOT'
            result = country[key]
        elif key == 'surrender_progress':
            result = compare(country['surrender_progress'], op, float(value))
        elif key in triggers:
            result = evaluate(triggers[key], state, scope) == (value == 'yes')
        elif key == 'eon_nuclear_arsenal_ready':
            from readiness_model import is_ready
            result = is_ready(country['ready'], country['flags'],
                              country['variables'].get('eon_nuclear_arsenal_recovery_remaining', 0),
                              state.get('prototype_enabled')) == (value == 'yes')
        else:
            raise AssertionError(('Unsupported predicate', key, op, value))
        checks.append(result)
    return all(checks)


triggers = {key: value for key, op, value in read('common/scripted_triggers/00_raids_triggers.txt')}
raids = {key: value for key, op, value in one(read('common/raids/nuclear_raids.txt'), 'types')}
raids.update({key: value for key, op, value in one(read('common/raids/eon_tactical_nuclear_missile_raid.txt'), 'types')})


def fixture(kind='nuclear_missile_equipment', count=1, prototype_enabled=None):
    actor = {'inventory': {kind: count}, 'variables': {}, 'ideas': {'full_first_use', 'nuclear_power_off'},
             'flags': set(), 'exists': True, 'war': True, 'ai': False, 'surrender_progress': 0, 'ready': True}
    return {'actor': actor, 'target': deepcopy(actor),
            'state': {'is_owned_by': False, 'is_claimed_by': False}, 'temp': {}, 'global_flags': set(),
            'prototype_enabled': prototype_enabled}


def run():
    from readiness_model import assert_default_off_contract
    assert_default_off_contract()
    cases = 0
    # Reserve-based scripted AI eligibility remains separate from native units.
    for kind in ('nuclear_missile_equipment', 'nuclear_ballistic_missile_equipment'):
        for minimum in (1, 10):
            for count in (0, minimum - 1, minimum, minimum + 1):
                state = fixture(kind, count)
                state['temp']['temp_check'] = minimum
                assert evaluate(triggers['check_if_nuclear_weapons_in_stockpile'], state) == (count >= minimum)
                cases += 1

    def native_unit_requirements_met(raid, unit_equipment, modules=()):
        # These amounts belong to ONE selected unit. Installed raid docs say
        # any unit matching a block is eligible; country totals cannot stand in
        # for that unit, and this bounded fixture does not prove the game UI.
        for key, op, value in raid:
            if key != 'unit_requirements':
                continue
            equipment = one(value, 'equipment')
            allowed = [kind for item, equals, kind in one(equipment, 'type')]
            needed = int(one(one(equipment, 'amount'), 'min'))
            required_modules = [kind for item, equals, kind in
                                next((v for k, o, v in equipment if k == 'modules'), [])]
            if any(unit_equipment.get(kind, 0) >= needed for kind in allowed) and all(module in modules for module in required_modules):
                return True
        return False

    def native_payload_collected(raid, payload):
        # Native collection is an explicit fixture boundary: source declares
        # the payload but exposes no invented scripting getter for its ledger.
        required = [value for key, op, value in raid if key == 'essential_equipment']
        assert len(required) <= 1
        return all(payload.get(kind, 0) >= int(quantity)
                   for kind, op, quantity in (required[0] if required else []))

    for raid_name, minimum in (('tactical_nuclear_strike', 1), ('eon_tactical_nuclear_missile_strike', 1),
                               ('state_nuclear_strike', 1), ('strategic_nuclear_strike', 10)):
        raid = raids[raid_name]
        bomber = raid_name == 'tactical_nuclear_strike'
        tactical = bomber or raid_name == 'eon_tactical_nuclear_missile_strike'
        for kind in ('nuclear_missile_equipment', 'nuclear_ballistic_missile_equipment'):
            for count in (0, minimum - 1, minimum, minimum + 1):
                expected = kind == 'nuclear_ballistic_missile_equipment' and count >= 1 if bomber else True
                assert evaluate(one(raid, 'available'), fixture(kind, count)) == expected, (raid_name, kind, count, 'available')
                assert evaluate(one(raid, 'launchable'), fixture(kind, count)), (raid_name, kind, count, 'launchable policy')
                cases += 2
                for payload_count in (0, 1):
                    state = fixture(kind, 0)
                    unit_equipment = {kind: count}
                    if bomber:
                        unit_equipment = {'strategic_bomber': count}
                    permitted = (evaluate(one(raid, 'launchable'), state) and
                                 native_unit_requirements_met(raid, unit_equipment, ('spec_nuclear_consent',)) and
                                 native_payload_collected(raid, {kind: payload_count}))
                    eligible_family = kind == 'nuclear_ballistic_missile_equipment' if tactical else True
                    expected_native = (count >= minimum and eligible_family and (payload_count >= 1 if bomber else True))
                    assert permitted == expected_native, (raid_name, kind, count, payload_count, 'single-unit and collected-payload requirements')
                    cases += 1
        for mutation in ('lost_country', 'peace', 'doctrine_changed', 'deterrence_only', 'not_ready'):
            state = fixture('nuclear_ballistic_missile_equipment', minimum + 1, prototype_enabled=True)
            assert evaluate(one(raid, 'available'), deepcopy(state))
            if mutation == 'lost_country':
                state['target']['exists'] = False
            elif mutation == 'peace':
                state['actor']['war'] = False
            elif mutation == 'doctrine_changed':
                state['actor']['ideas'].discard('full_first_use')
            elif mutation == 'deterrence_only':
                state['actor']['ideas'] = {'full_first_use', 'nuclear_power_def'}
            else:
                state['actor']['ready'] = False
            assert not evaluate(one(raid, 'launchable'), state), (raid_name, mutation)
            cases += 1
        # Production ignores stale prototype flags; all other policy remains.
        for recovery in (0, 4):
            state = fixture('nuclear_ballistic_missile_equipment', minimum + 1)
            state['actor']['ready'] = False
            state['actor']['flags'].add('eon_nuclear_arsenal_safety_mode')
            state['actor']['variables']['eon_nuclear_arsenal_recovery_remaining'] = recovery
            assert evaluate(one(raid, 'available'), deepcopy(state))
            assert evaluate(one(raid, 'launchable'), deepcopy(state))
            state['actor']['war'] = False
            assert not evaluate(one(raid, 'launchable'), state)
            cases += 3
        # Accepted doctrine for retaliation is retained and still permits launch.
        for doctrine in ('strategic_retaliation_only', 'tac_and_strat_retaliation', 'tac_first_use_strat_retaliation'):
            state = fixture('nuclear_ballistic_missile_equipment', minimum)
            state['actor']['ideas'].discard('full_first_use')
            state['actor']['ideas'].add(doctrine)
            state['actor']['flags'].add('has_been_nuked')
            expected = not tactical or doctrine != 'strategic_retaliation_only'
            assert evaluate(one(raid, 'launchable'), state) == expected, (raid_name, doctrine)
            cases += 1
        for level, operator, effects in one(raid, 'success_levels'):
            actor_effects = [value for key, op, value in effects if key == 'actor_effects']
            for actor in actor_effects:
                def check_scope(nodes, scope='raid'):
                    nonlocal cases
                    for key, op, value in nodes:
                        if key == 'raid_damage_units':
                            assert scope == 'raid', (raid_name, level, 'wrong raid_damage_units scope')
                            cases += 1
                        if isinstance(value, list):
                            nested_scope = 'country' if key == 'var:actor_country' else scope
                            check_scope(value, nested_scope)
                check_scope(actor)
    bomber = raids['tactical_nuclear_strike']
    state = fixture('nuclear_ballistic_missile_equipment', 1)
    assert evaluate(one(bomber,'available'),state)
    state['actor']['inventory']['nuclear_ballistic_missile_equipment'] = 0
    assert not evaluate(one(bomber,'available'),state), 'Cannot prepare another raid with an empty reserve'
    assert evaluate(one(bomber,'launchable'),state), 'Collected payload must not require a second reserve copy'
    assert native_payload_collected(bomber, {'nuclear_ballistic_missile_equipment': 1})
    assert not native_payload_collected(bomber, {})
    cases += 5
    print(json.dumps({'status': 'PASS', 'source_predicate_and_scope_cases': cases,
                      'scope': 'Current source predicates and native schema; not a launched raid or human UI'}, indent=2))


if __name__ == '__main__':
    run()
