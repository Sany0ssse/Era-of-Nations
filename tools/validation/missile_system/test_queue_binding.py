"""Pending native response pairs survive unrelated callback context changes.

Execute actual queue constructors, monthly callers and daily handler AST. Raid
eligibility has been selected explicitly; state selection, native inventory
removal and hit resolution are bounded fixtures, not a fired native raid.
"""
from copy import deepcopy
import json

from test_ai_outcomes import (Runtime, LAUNCHES, STRATEGIC, SUCCESS, after_limit,
                              minimal_callers, project, walk)
from test_launch import one, read
from test_native_ammo_source import restore_queued_victim
from test_reserve_payment import SHORT

SHOOTER = 'eon_nuclear_queued_shooter'
LEVEL = 'eon_nuclear_queued_level'


class QueueRuntime(Runtime):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raid_actor = 'GER'

    def value(self, name, stack):
        if name == 'ROOT.actor_country':
            return self.raid_actor
        return super().value(name, stack)


def run():
    raid = one(one(read('common/raids/nuclear_raids.txt'), 'types'), 'strategic_nuclear_strike')
    actions = one(read('common/on_actions/00_ai_nuclear_raids.txt'), 'on_actions')
    daily = one(one(actions, 'on_daily'), 'effect')
    monthly = [body for key, op, body in actions if key == 'on_monthly']
    helpers = {name: project(body) for name, op, body in read('common/scripted_effects/00_ai_nuclear_raids.txt')
               if name in LAUNCHES}
    constructors = []
    for outcome, op, body in one(raid, 'success_levels'):
        victim = one(one(body, 'victim_effects'), 'var:victim_country')
        restore_queued_victim(victim)  # Exact source policy and insertion shape.
        constructor = after_limit(victim[0][2])
        assert not any(key == 'set_variable' and any(name.startswith('global.') for name, op, value in variables)
                       for key, op, variables in walk(constructor))
        constructors.append(constructor)
    assert len(constructors) == 4

    def runtime_for(constructor, prototype_enabled=True):
        runtime = QueueRuntime(short=10, targets=('SOV',), eligible_state={'SOV': False, 'GER': True}, prototype_enabled=prototype_enabled)
        runtime.helpers = helpers
        runtime.countries['USA']['vars']['arctic_nuclear_level'] = 2
        runtime.countries['FRA']['vars']['arctic_nuclear_level'] = 7
        runtime.countries['FRA']['stock'][SHORT] = 10
        runtime.variables.update({'global.nuke_striker': 'SOV', 'global.temp_arctic_nuclear_level': 42})
        runtime.root = 'raid'
        runtime.execute(constructor, ['raid', 'USA'])
        assert runtime.countries['GER']['vars'][SHOOTER] == 'USA'
        assert runtime.countries['GER']['vars'][LEVEL] == 2
        assert runtime.variables == {'global.nuke_striker': 'SOV', 'global.temp_arctic_nuclear_level': 42}
        assert 'sugoma' in runtime.countries['GER']['flags'] and 'sussy_baka' in runtime.countries['USA']['flags']
        assert 'amogus' in runtime.global_flags
        return runtime

    def finish(runtime, incoming):
        runtime.temp.clear()  # Separate native callback, no temporary carryover.
        runtime.root = 'GER'
        runtime.execute(daily, ['GER'])
        assert runtime.countries['USA']['stock'][SHORT] == 0
        assert runtime.countries['FRA']['stock'][SHORT] == 10
        assert runtime.launch_frames == [('USA', 2, 'GER')]
        assert runtime.countries['GER']['damage'] == 1
        assert runtime.countries['USA']['threat'] == 100
        assert runtime.variables == incoming, 'Incoming callback context must survive queue completion'
        assert SHOOTER not in runtime.countries['GER']['vars'] and LEVEL not in runtime.countries['GER']['vars']

    corrected_bleeds = 0
    for name in LAUNCHES:
        callers = [body for block in monthly for body in minimal_callers(block, name)]
        assert len(callers) == 1
        for constructor in constructors:
            runtime = runtime_for(constructor)
            runtime.root = 'FRA'
            runtime.execute(after_limit(callers[0]), ['FRA'])
            assert runtime.countries['FRA']['stock'][SHORT] == 10  # No eligible state.
            incoming = deepcopy(runtime.variables)
            finish(runtime, incoming)
            corrected_bleeds += 1
    assert corrected_bleeds == 12

    # Actual report-event options may clear the transient global frame before
    # daily processing. The persistent target pair remains sufficient.
    event_clears = [[node for node in walk(one(body, 'option')) if node[0] == 'clear_variable']
                    for key, op, body in read('events/00_Nuclear_ai_events.txt')
                    if key == 'country_event' and one(body, 'id') in ('nuclear_ai_raid.1', 'nuclear_ai_raid.2')]
    assert event_clears == [[('clear_variable', '=', 'global.temp_arctic_nuclear_level'),
                            ('clear_variable', '=', 'global.nuke_striker')]]*2
    absent_frame_cases = 0
    for constructor in constructors:
        for clears in event_clears:
            runtime = runtime_for(constructor)
            runtime.root = 'GER'
            runtime.execute(clears, ['GER'])
            finish(runtime, {})
            absent_frame_cases += 1

    canceled = 0
    for missing in ('both', 'shooter', 'level', 'invalid_shooter', 'queue_flag', 'unready_shooter', 'capitulated_target'):
        for constructor in constructors:
            runtime = runtime_for(constructor)
            target = runtime.countries['GER']
            if missing in ('both', 'shooter'):
                target['vars'].pop(SHOOTER)
            if missing in ('both', 'level'):
                target['vars'].pop(LEVEL)
            if missing == 'invalid_shooter':
                target['vars'][SHOOTER] = 0
            if missing == 'queue_flag':
                runtime.global_flags.clear()
            if missing == 'unready_shooter':
                runtime.countries['USA']['ready'] = False
            if missing == 'capitulated_target':
                target['capitulated'] = True
            # Runtime seeds stale SUCCESS deliberately. Cancellation must not
            # interpret it as a paid fresh launch or charge an unrelated state.
            assert SUCCESS in target['flags']
            incoming = deepcopy(runtime.variables)
            runtime.root = 'GER'
            runtime.execute(daily, ['GER'])
            assert runtime.countries['USA']['stock'][SHORT] == 10
            assert runtime.countries['FRA']['stock'][SHORT] == 10
            assert all(country['threat'] == country['damage'] == 0 for country in runtime.countries.values())
            assert SUCCESS not in target['flags'] and 'sugoma' not in target['flags']
            assert SHOOTER not in target['vars'] and LEVEL not in target['vars']
            assert runtime.launch_frames == []
            assert runtime.variables == incoming
            canceled += 1

    refused_target_constructors = 0
    for constructor in constructors:
        runtime = QueueRuntime(short=10, prototype_enabled=True)
        runtime.root = 'raid'
        runtime.countries['GER']['capitulated'] = True
        runtime.execute(constructor, ['raid', 'USA'])
        assert not runtime.global_flags
        assert 'sugoma' not in runtime.countries['GER']['flags']
        assert 'sussy_baka' not in runtime.countries['USA']['flags']
        assert SHOOTER not in runtime.countries['GER']['vars']
        refused_target_constructors += 1

    # A real context-capture regression must fail even when helpers and payment
    # themselves remain valid. Replacing target bindings with globals recreates
    # the previously confirmed wrong-country charge.
    def global_capture(nodes):
        result = []
        for key, op, value in nodes:
            if key == 'set_variable' and value == [('global.nuke_striker', '=', SHOOTER)]:
                value = [('global.nuke_striker', '=', 'eon_nuclear_daily_previous_shooter')]
            elif key == 'set_variable' and value == [('global.temp_arctic_nuclear_level', '=', LEVEL)]:
                value = [('global.temp_arctic_nuclear_level', '=', 'eon_nuclear_daily_previous_level')]
            elif isinstance(value, list):
                value = global_capture(value)
            result.append((key, op, value))
        return result
    mutant = runtime_for(constructors[0])
    mutant.variables.update({'global.nuke_striker': 'FRA', 'global.temp_arctic_nuclear_level': 7})
    mutant.root = 'GER'
    mutant.execute(global_capture(daily), ['GER'])
    assert mutant.countries['FRA']['stock'][SHORT] == 0 and mutant.countries['USA']['stock'][SHORT] == 10
    assert mutant.launch_frames == [('FRA', 7, 'GER')]
    default_off_cases = 0
    for constructor in constructors:
        runtime = runtime_for(constructor, prototype_enabled=None)
        runtime.countries['USA']['ready'] = False
        runtime.countries['USA']['flags'].add('eon_nuclear_arsenal_safety_mode')
        runtime.countries['USA']['vars']['eon_nuclear_arsenal_recovery_remaining'] = 4
        finish(runtime, deepcopy(runtime.variables))
        default_off_cases += 1
    print(json.dumps({'status': 'PASS', 'corrected_actual_AST_context_bleeds': corrected_bleeds,
                      'default_off_stale_queue_cases': default_off_cases,
                      'cleared_global_frame_cases': absent_frame_cases, 'unbound_stale_outcome_cancellations': canceled,
                      'constructor_refused_target_cases': refused_target_constructors,
                      'wrong_global_capture_mutant_detected': True,
                      'native_queue_compilation_or_firing_verified': False}, indent=2))


if __name__ == '__main__':
    run()
