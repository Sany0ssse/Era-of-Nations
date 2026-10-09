"""Read shooter-scoped readiness barriers without executing nuclear damage."""
from copy import deepcopy
import json
import subprocess

from test_launch import ROOT, ast, one, read
from readiness_model import assert_default_off_contract, is_ready

BASELINE = '2b6a26e76c80f7923d11ebc2c0694e882253fb32'
PATH = 'common/scripted_effects/00_ai_nuclear_raids.txt'
SUCCESS = 'eon_nuclear_scripted_launch_succeeded'


def readiness_gate(nodes, shooter_ready, victim_ready, shooter_exists=True, handle_exists=True, scope='victim', target_exists=True, prototype_enabled=None):
    checks = []
    for key, op, value in nodes:
        if key == 'has_variable':
            assert value == 'global.nuke_striker'
            result = handle_exists
        elif key == 'var:global.nuke_striker':
            result = handle_exists and readiness_gate(value, shooter_ready, victim_ready, shooter_exists, handle_exists, 'shooter', target_exists, prototype_enabled)
        elif key == 'any_owned_state':
            assert scope == 'victim' and value == [('is_fully_controlled_by', '=', 'PREV')]
            result = target_exists
        elif key == 'exists':
            assert scope == 'shooter' and value == 'yes'
            result = shooter_exists
        elif key == 'eon_nuclear_arsenal_ready':
            assert scope == 'shooter' and value == 'yes', 'Readiness must apply to the shooter'
            result = is_ready(shooter_ready, prototype_enabled=prototype_enabled)
        else:
            raise AssertionError(('Unsupported or wrong-scope barrier', key, op, value))
        checks.append(result)
    return all(checks)


def run():
    assert_default_off_contract()
    def active_gate(*args, **kwargs):
        return readiness_gate(*args, **kwargs, prototype_enabled=True)
    original = ast(subprocess.check_output(['git', 'show', BASELINE+':'+PATH], cwd=ROOT).decode('utf-8-sig'))
    current = read(PATH)
    assert {key for key, op, value in original} == {key for key, op, value in current}
    cases = 0
    payments = 0
    removed_old_transfers = 0
    target_guards = 0
    paid_attempt_markers = 0

    def walk(nodes):
        for key, op, value in nodes:
            yield key, op, value
            if isinstance(value, list):
                yield from walk(value)

    def normalize(nodes, original=False):
        nonlocal payments, removed_old_transfers, target_guards, paid_attempt_markers
        result = []
        for key, op, value in nodes:
            if key == 'clr_country_flag' and value == SUCCESS:
                continue
            if key == 'set_temp_variable' and value == [('eon_nuclear_scripted_actor', '=', 'global.nuke_striker')]:
                continue
            if key == 'set_country_flag' and value == SUCCESS:
                paid_attempt_markers += 1
                continue
            if not original and key in ('every_neighbor_country', 'every_enemy_country'):
                value = deepcopy(value)
                gate = one(value, 'limit')
                selector = [node for node in walk(value) if node[0] in ('random_controlled_state', 'random_owned_state', 'capital_scope')]
                # The country gate's copied capital predicate is also a
                # capital_scope, so select the effect with its nested if.
                selector = [node for node in selector if node[0] != 'capital_scope' or any(k == 'if' for k, o, v in node[2])]
                assert len(selector) == 1
                selector_key, selector_op, selector_body = selector[0]
                expected_key = {'random_controlled_state': 'any_controlled_state', 'random_owned_state': 'any_owned_state',
                                'capital_scope': 'capital_scope'}[selector_key]
                selector_gate = one(one(selector_body, 'if'), 'limit') if selector_key == 'capital_scope' else one(selector_body, 'limit')
                assert gate[-1] == (expected_key, '=', selector_gate), (name, 'Target eligibility must exactly match selected state')
                gate.pop()
                target_guards += 1
            if original and key == 'send_equipment':
                family = one(value, 'equipment')
                if family in ('nuclear_ballistic_missile_equipment', 'nuclear_missile_equipment') and one(value, 'amount') == 'global.amogusus_count':
                    removed_old_transfers += 1
                    continue
            if key == 'var:global.nuke_striker' and isinstance(value, list) and any(k == 'eon_nuclear_scripted_pay_reserve' for k, o, v in value):
                assert value == [('set_temp_variable', '=', [('eon_nuclear_scripted_request', '=', '10' if name == 'launch_nuclear_ai_country_strike' else '1')]),
                                 ('eon_nuclear_scripted_pay_reserve', '=', 'yes')]
                payments += 1
                continue
            if key == 'if' and isinstance(value, list):
                limits = [v for k, o, v in value if k == 'limit']
                if limits == [[('has_country_flag', '=', SUCCESS)]]:
                    if any(k == 'var:eon_nuclear_scripted_actor' for k, o, v in value):
                        assert one(value, 'var:eon_nuclear_scripted_actor') == [('set_country_flag', '=', SUCCESS)]
                        continue
                    assert any(k == 'add_named_threat' for k, o, v in value)
                    value = [('limit', '=', [('check_variable', '=', [('global.amogusus_count', '>', '0')])])]+[node for node in value if node[0] != 'limit']
                    limits = [one(value, 'limit')]
                if limits == [[('var:global.nuke_striker', '=', [('has_country_flag', '=', 'eon_nuclear_scripted_reserve_paid')])]]:
                    result.extend(normalize([node for node in value if node[0] != 'limit']))
                    continue
            result.append((key, op, normalize(value, original) if isinstance(value, list) else value))
        return result

    for name, op, old_body in original:
        wrapper = one(current, name)
        assert len(wrapper) == 2 and wrapper[0] == ('clr_country_flag', '=', SUCCESS) and wrapper[1][0] == 'if', (name, 'Missing readiness barrier or stale outcome reset')
        body = wrapper[1][2]
        gate = one(body, 'limit')
        if name == 'launch_nuclear_ai_country_strike':
            assert not active_gate(gate, True, True, target_exists=False)
            cases += 1
        assert normalize([node for node in body if node[0] != 'limit']) == normalize(old_body, True), (name, 'Unrelated damage source changed')
        for shooter_ready in (False, True):
            for victim_ready in (False, True):
                for shooter_exists in (False, True):
                    for handle_exists in (False, True):
                        entered = active_gate(gate, shooter_ready, victim_ready, shooter_exists, handle_exists)
                        assert entered == (shooter_ready and shooter_exists and handle_exists), name
                        cases += 1
        # A mutation that accidentally applies readiness to the victim fails
        # closed in this source interpreter instead of being assumed correct.
        wrong = deepcopy(gate)
        for index, (key, operator, value) in enumerate(wrong):
            if key == 'var:global.nuke_striker':
                wrong[index] = ('eon_nuclear_arsenal_ready', '=', 'yes')
        try:
            active_gate(wrong, True, False)
        except AssertionError:
            cases += 1
        else:
            raise AssertionError('Wrong-scope mutant survived')
        for shooter_exists in (False, True):
            for handle_exists in (False, True):
                assert readiness_gate(gate, False, False, shooter_exists, handle_exists) == (shooter_exists and handle_exists)
                cases += 1
    assert payments == 7 and removed_old_transfers == 12, (payments, removed_old_transfers)
    assert target_guards == 6 and paid_attempt_markers == 7, (target_guards, paid_attempt_markers)
    print(json.dumps({'status': 'PASS', 'actual_source_gate_cases': cases,
                      'unchanged_damage_bodies': len(original),
                      'atomic_reserve_payment_barriers': payments, 'old_duplicate_family_transfers_removed': removed_old_transfers,
                      'exact_actual_target_gates': target_guards, 'paid_attempt_outcome_markers': paid_attempt_markers,
                      'scope': 'Shooter readiness barrier and unchanged source; no destructive native strike'}, indent=2))


if __name__ == '__main__':
    run()
