"""Execute the actual retaliation callback's shooter save/restore sequence."""
import json

from test_launch import read, one


def walk(nodes):
    for key, op, value in nodes:
        if isinstance(value, list):
            if key == 'if' and any(k == 'launch_nuclear_ai_country_strike' for k, o, v in value):
                yield value
            yield from walk(value)


def run():
    candidates = list(walk(read('events/00_Nuclear_ai_events.txt')))
    assert len(candidates) == 1
    callback = candidates[0]
    outcome_guard = one(callback, 'if')
    assert one(outcome_guard, 'limit') == [('has_country_flag', '=', 'eon_nuclear_scripted_launch_succeeded')]
    assert len([node for node in outcome_guard if node[0] == 'var:v']) == 1
    statements = [(key, value) for key, op, value in callback if key not in ('limit', 'if')]
    assert [key for key, value in statements] == ['set_temp_variable', 'set_variable', 'set_temp_variable', 'set_variable',
                                                'launch_nuclear_ai_country_strike', 'set_variable', 'set_variable']
    cases = 0
    for incoming in ('USA', 'GER', 'FRA', 'RAJ'):
        for retaliating in ('SOV', 'CHI', 'PAK'):
            for nested_replaces_handle in (False, True):
                state = {'global.nuke_striker': incoming, 'global.temp_arctic_nuclear_level': 0,
                         'var:v': retaliating, 'var:v.arctic_nuclear_level': 7}
                invoked = []
                for key, value in statements:
                    if key in ('set_variable', 'set_temp_variable'):
                        for variable, op, source in value:
                            assert op == '='
                            state[variable] = state[source]
                    else:
                        assert value == 'yes'
                        invoked.append(state['global.nuke_striker'])
                        if nested_replaces_handle:
                            state['global.nuke_striker'] = 'nested_callback_actor'
                assert invoked == [retaliating]
                assert state['global.nuke_striker'] == incoming
                assert state['global.temp_arctic_nuclear_level'] == 0
                cases += 1
    gate = one(callback, 'limit')
    scoped = one(gate, 'var:v')
    assert ('eon_nuclear_arsenal_ready', '=', 'yes') in scoped
    assert ('has_country_flag', '=', 'perimetr_system') in scoped
    assert one(scoped, 'OR') == [('check_variable', '=', [('num_equipment@nuclear_missile_equipment', '>', '9')]),
                               ('check_variable', '=', [('num_equipment@nuclear_ballistic_missile_equipment', '>', '9')])]
    print(json.dumps({'status': 'PASS', 'actual_source_retaliation_frame_cases': cases,
                      'scope': 'Callback shooter save/set/restore and scoped readiness/ammunition; not a launched strike'}, indent=2))


if __name__ == '__main__':
    run()
