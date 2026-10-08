"""Execute current protocol 24 source with a bounded country/state interpreter.

Native construction success/failure and random choice are explicit fixtures.
Tests prove the actual script reaction to each outcome, not engine execution.
"""
from copy import deepcopy
import json
from _model import *

cases = []

def run(s, name, donor=1, index=0):
    s['temp'] = {}
    s['entities'][donor]['variables']['project'] = index
    execute(effects[name], s, context(donor))

def tick(s, days=1, donor=1):
    for _ in range(days):
        s['temp'] = {}
        execute(effects['eon_investment_lifecycle_daily_update'], s, context(donor))

def v(s, name, donor=1):
    return s['entities'][donor]['variables'].get(name, 0)

def close(a, b):
    assert abs(a-b) < 1e-6, (a, b)

def invariant(s, donor=1, recipient=2, original=1000):
    # Investor value is cash + claims + pending principal + actual operating
    # principal + explicitly lost principal; no unbuilt unit can earn ROI.
    close(sum(v(s, k, donor) for k in ('treasury', 'eon_investment_refund_claims',
          'eon_construction_capital', 'int_investments', 'eon_investment_construction_losses')), original)
    close(sum(v(s, k, recipient) for k in ('treasury', 'eon_investment_refund_claims',
          'eon_construction_contributions', 'eon_investment_contribution_spent')), 1000)
    assert v(s, 'eon_construction_capital', donor) >= -1e-8
    assert v(s, 'eon_construction_contributions', recipient) >= -1e-8

# Qualified state result writers have not been calibrated in native HOI4.
# Financial lifecycle cases retain an explicit result-routing assumption;
# the default adapter rejects those writers and never claims engine acceptance.
unqualified_state = state
def state():
    result = unqualified_state()
    result['qualified_build_result_fixture'] = 'shared_result_assumption'
    return result


def accepted(kind=1, amount=2, cost=30, duration=3, recipient=2, target=-101):
    s = state()
    stage(s, receiver=recipient, target=target, kind=kind, amount=amount,
          cost=cost, duration=duration)
    assert send(s)
    respond(s, receiver=recipient)
    assert v(s, 'eon_project_protocol^0') == 24
    assert v(s, 'int_investments') == 0
    close(v(s, 'eon_construction_capital'), cost)
    assert not any(call[1] == 'activate_decision' for call in s['external'])
    return s

def notifications(s, ident):
    return [event for event in s['events'] if event[0] == f'eon_investment_lifecycle.{ident}']

# Native10 read semantics: bare temps share the execution; explicit scope reads
# persistent values. Qualified writes remain an uncalibrated model boundary.
s = unqualified_state()
for scope, probe in ((1, 11), (2, 33), (-101, 22)):
    execute(ast(f'set_temp_variable = {{ scoped_probe = {probe} }}'), s, context(1, scope=scope, previous=(1,)))
assert all(value(s, context(1, scope=scope), 'scoped_probe') == 22 for scope in (1, 2, -101))
assert value(s, context(1, scope=-101, previous=(1,)), 'PREV.scoped_probe') == 0
s['entities'][1]['variables']['scoped_probe'] = 99
assert value(s, context(1, scope=-101, previous=(1,)), 'PREV.scoped_probe') == 99
try:
    execute(ast('set_temp_variable = { PREV.eon_project_build_result = 1 }'), s, context(1, scope=-101, previous=(1,)))
except AssertionError as exc:
    assert 'Uncalibrated qualified temporary write' in str(exc)
else: raise AssertionError('Default adapter silently assumed a qualified result writer')
cases.append('native10 shared bare reads and persistent scoped reads; qualified writer rejected by default')

for outcome in ('success', 'native_failure', 'corruption'):
    s = accepted(amount=1, cost=5.8, duration=1)
    s['entities'][1]['variables']['project'] = 0
    s['entities'][1]['variables']['eon_project_days_remaining^0'] = 0
    s['temp'] = {'eon_project_build_result': 666, 'eon_project_spent_contribution': 888}
    # Poison permanent values to catch accidental PREV.temp reads; bare temps
    # must be initialized from this exact project during execution.
    for scope in (1, 2, -101): s['entities'][scope]['variables']['eon_project_spent_contribution'] = 999
    s['native_build_failure'] = outcome == 'native_failure'
    s['corruption'] = outcome == 'corruption'
    execute(effects['complete_project'], s, context(1))
    invariant(s)
    assert s['temp']['eon_project_build_result'] == {'success': 1, 'native_failure': 0, 'corruption': -1}[outcome]
    if outcome != 'native_failure': assert s.get('unverified_qualified_temp_write_calls')
    close(v(s, 'eon_investment_contribution_spent', 2), 0 if outcome == 'native_failure' else .58)
    close(v(s, 'eon_construction_contributions', 2), .58 if outcome == 'native_failure' else 0)
    close(v(s, 'int_investments'), 5.8 if outcome == 'success' else 0)
    if outcome == 'native_failure': assert v(s, 'active_projects') == 1 and not notifications(s, 4)
    cases.append('shared cofunding arithmetic with explicit unverified writer assumption '+outcome)

# All literal building types and supported quantities, exact fractional residual.
limits = {4: 5, 5: 5, 6: 5, 7: 6, 9: 5, 10: 6, 15: 3}
for kind in range(1, 16):
    for amount in range(1, min(10, limits.get(kind, 10))+1):
        for cost in (0.1, 5.8, 30.001):
            s = accepted(kind=kind, amount=amount, cost=cost, duration=2)
            invariant(s)
            assert len(notifications(s, 1)) == 2
            for unit in range(amount):
                tick(s, 2)
                invariant(s)
                close(v(s, 'int_investments'), cost*(unit+1)/amount)
                close(v(s, 'eon_construction_capital'), cost*(amount-unit-1)/amount)
                close(v(s, 'eon_construction_contributions', 2), cost*.1*(amount-unit-1)/amount)
                close(v(s, 'eon_investment_contribution_spent', 2), cost*.1*(unit+1)/amount)
            assert s['buildings'] == [(-101, BUILDINGS[kind-1])]*amount
            assert v(s, 'active_projects') == 0
            assert s['entities'][1]['arrays']['project_array'][0] == 0
            assert len(notifications(s, 4)) == 2 and not notifications(s, 8)
            before = persistent(s)
            run(s, 'complete_project')
            # Legacy fallback of an empty released slot does not touch money.
            assert money(s) == money(before)
            assert len(s['buildings']) == amount
            cases.append(f'all units kind={kind} amount={amount} cost={cost}')

# Actual GUI cancellation: use full button predicate and full click effect.
window = one(one(load('common/scripted_guis/01_investment_scripted_gui.txt'), 'scripted_gui'), 'AC_allied_construction_window')
enabled = one(one(window, 'triggers'), 'AC_build_button_click_enabled')
click = one(one(window, 'effects'), 'AC_build_button_click')
for completed in (0, 1, 2):
    for occupation in (False, True):
        s = accepted(amount=3, cost=5.8, duration=2)
        tick(s, completed*2)
        if occupation: s['entities'][-101]['controller'] = 3
        c = context(1, scope=-101, previous=(-101,))
        assert condition(enabled, s, c)
        s['temp'] = {}
        execute(click, s, c)
        invariant(s)
        close(v(s, 'int_investments'), 5.8*completed/3)
        close(v(s, 'treasury'), 1000-5.8*completed/3)
        close(v(s, 'treasury', 2), 1000-0.58*completed/3)
        assert v(s, 'treasury', 3) == 1000
        assert v(s, 'active_projects') == 0
        penalties = [x for x in s['external'] if x[1] == 'change_influence_percentage' and x[3].get('percent_change', 0) < 0]
        assert len(penalties) == (0 if occupation else 1)
        if penalties: assert penalties[0][3]['influence_target'] == 2
        assert len(notifications(s, 5)) == 2
        before = money(s)
        run(s, 'end_project'); assert money(s) == before
        cases.append(f'full GUI cancellation after={completed} occupation={occupation}')

# Pause preserves both cash and construction days; repeated days notify once.
for reason in ('war_sender', 'war_recipient', 'owner', 'controller', 'missing_recipient', 'disabled', 'slots'):
    s = accepted(duration=5)
    tick(s, 2)
    remaining = v(s, 'eon_project_days_remaining^0')
    if reason == 'war_sender': s['entities'][1]['wars'].add(2)
    elif reason == 'war_recipient': s['entities'][2]['wars'].add(1)
    elif reason == 'owner': s['entities'][-101]['owner'] = 3
    elif reason == 'controller': s['entities'][-101]['controller'] = 3
    elif reason == 'missing_recipient': s['entities'][2]['exists'] = False
    elif reason == 'disabled': s['entities'][1]['flags'].add('disabled_foreign_investment')
    else: s['entities'][-101]['slots']['industrial_complex'] = 0
    before = money(s)
    tick(s, 12)
    assert money(s) == before and not s['buildings']
    assert v(s, 'eon_project_days_remaining^0') == remaining
    assert v(s, 'eon_project_paused^0') == 1
    assert len(notifications(s, 2)) == (1 if reason == 'missing_recipient' else 2)
    s['entities'][1]['wars'].clear(); s['entities'][2]['wars'].clear()
    s['entities'][-101].update(owner=2, controller=2)
    s['entities'][2]['exists'] = True
    s['entities'][1]['flags'].discard('disabled_foreign_investment')
    s['entities'][-101]['slots']['industrial_complex'] = 10
    tick(s, int(remaining))
    assert len(s['buildings']) == 1
    assert len(notifications(s, 3)) == 2
    invariant(s)
    cases.append('pause and resume '+reason)

# Last-moment control change is validated by complete_project itself, even
# before daily pause sees it. Restoration preserves the elapsed unit boundary.
s = accepted(duration=1)
s['entities'][1]['variables']['eon_project_days_remaining^0'] = 0
s['entities'][-101]['controller'] = 3
run(s, 'complete_project')
assert not s['buildings'] and not notifications(s, 4)
assert v(s, 'int_investments') == 0
s['entities'][-101]['controller'] = 2
tick(s)
assert len(s['buildings']) == 1
invariant(s); cases.append('late occupation at completion')

# A rejected native building command never consumes funds or announces success.
for kind in range(1, 16):
    s = accepted(kind=kind, amount=1, duration=1)
    s['native_build_failure'] = True
    tick(s)
    assert v(s, 'eon_project_paused^0') == 2
    assert not s['buildings'] and not notifications(s, 4)
    close(v(s, 'eon_construction_capital'), 30)
    assert v(s, 'int_investments') == 0
    before = money(s); run(s, 'complete_project'); assert money(s) == before
    tick(s, 6); assert len(notifications(s, 6)) == 2
    s['native_build_failure'] = False
    tick(s)
    assert len(s['buildings']) == 1 and len(notifications(s, 4)) == 2
    invariant(s); cases.append('native failure and retry '+str(kind))

# Early/repeated native callbacks cannot build ahead of the daily clock.
s = accepted(duration=3)
run(s, 'complete_project'); assert not s['buildings']
tick(s, 3); assert len(s['buildings']) == 1
before = money(s); run(s, 'complete_project')
assert money(s) == before and len(s['buildings']) == 1
invariant(s); cases.append('clock and duplicate callback guards')

# Existing corruption outcome is a recorded loss, never an asset or full success.
for amount in (1, 2, 3):
    s = accepted(amount=amount, cost=5.8, duration=1)
    s['corruption'] = True
    tick(s, amount)
    assert not s['buildings'] and not notifications(s, 4)
    assert len(notifications(s, 8)) == 2
    close(v(s, 'eon_investment_construction_losses'), 5.8)
    close(v(s, 'eon_investment_contribution_losses', 2), 0.58)
    invariant(s); cases.append('corruption units '+str(amount))

# Treasury cap preserves a durable claim; the original payer can collect only
# actual headroom. No money goes to a later controller or vanishes on cleanup.
for payer in (1, 2):
    s = accepted(amount=1, cost=30)
    s['entities'][payer]['variables']['treasury'] = 1000000
    s['entities'][-101]['controller'] = 3
    run(s, 'end_project')
    owed = 30 if payer == 1 else 3
    close(v(s, 'eon_investment_refund_claims', payer), owed)
    assert v(s, 'treasury', payer) == 1000000
    s['entities'][payer]['variables']['treasury'] -= 1
    tick(s, donor=payer)
    close(v(s, 'eon_investment_refund_claims', payer), owed-1)
    assert v(s, 'treasury', payer) == 1000000
    s['entities'][payer]['variables']['treasury'] -= 100
    tick(s, donor=payer)
    assert not v(s, 'eon_investment_refund_claims', payer)
    assert v(s, 'treasury', 3) == 1000
    cases.append('treasury ceiling claim payer '+str(payer))

# A vanished cofinancer retains its own claim, settled once on same-tag return.
s = accepted(amount=1)
s['entities'][2]['exists'] = False
run(s, 'end_project')
assert v(s, 'treasury', 2) == 997 and v(s, 'eon_investment_refund_claims', 2) == 3
s['entities'][2]['exists'] = True
tick(s, donor=2); tick(s, donor=2)
assert v(s, 'treasury', 2) == 1000 and not v(s, 'eon_investment_refund_claims', 2)
invariant(s); cases.append('vanished original cofinancer claim')

# Operating portfolio disposal cannot sell an advance under construction.
# Execute the actual bankruptcy.114 pre-debt settlement source, including its
# 70/80 percent sale valuation and int_investments reset. Full debt UI is outside
# this project's model, and intentionally not claimed tested.
econ = {one(node, 'id'): node for key, op, node in load('events/00_Econ_events.txt') if key == 'country_event'}
sale = next(node for key, op, node in econ['bankruptcy.114'] if key == 'option' and one(node, 'name') == 'bankruptcy.114.a')
pre_sale = sale[:next(i for i,node in enumerate(sale) if node[0] == 'set_variable' and node[2] == [('int_investments', '=', '0')])+1]
for partial in (False, True):
    s = accepted(amount=2, cost=30, duration=1)
    if partial: tick(s)
    s['temp'] = {}
    execute(pre_sale, s, context())
    assert v(s, 'int_investments') == 0
    close(v(s, 'eon_construction_capital'), 15 if partial else 30)
    assert v(s, 'active_projects') == 1
    before = v(s, 'treasury')
    run(s, 'end_project')
    close(v(s, 'treasury')-before, 15 if partial else 30)
    assert v(s, 'active_projects') == 0
    cases.append('operating disposal preserves pending capital '+str(partial))

# Two state projects retain independent clocks and metadata, and the real GUI
# resolves the selected state's second slot instead of accidentally cancelling 0.
s = accepted(duration=1)
stage(s, receiver=3, target=-102, amount=1, cost=20, duration=2)
assert send(s); respond(s, receiver=3)
assert v(s, 'eon_project_protocol^1') == 24
s['temp'] = {}
execute(click, s, context(1, scope=-102, previous=(-102,)))
assert s['entities'][1]['arrays']['project_array'] == [-101]+[0]*14
assert v(s, 'active_projects') == 1
assert v(s, 'treasury', 3) == 1000
tick(s, 2)
assert len(s['buildings']) == 2 and all(state_id == -101 for state_id,_ in s['buildings'])
assert v(s, 'active_projects') == 0
cases.append('second-slot actual GUI selection and independent clocks')

# Two live investors remain in one state after an earlier cleanup in the SAME
# effect environment. Removing the later entry must reset the shared break temp.
# Foreign investor's first entry stays untouched.
s = accepted(amount=1, duration=5)
for donor in (3, 4):
    stage(s, donor=donor, amount=1, cost=20, duration=5)
    assert send(s, donor=donor)
    respond(s, donor=donor)
assert s['entities'][-101]['arrays']['projects_in_state'] == [1, 3, 4]
s['temp'] = {}
for donor in (1, 4):
    s['entities'][donor]['variables']['project'] = 0
    execute(effects['end_project'], s, context(donor))
    if donor == 1:
        assert s['entities'][-101]['arrays']['projects_in_state'] == [3, 4]
        assert s['temp']['eon_project_state_break'] == 1
assert s['entities'][-101]['arrays']['projects_in_state'] == [3]
assert s['entities'][-101]['arrays']['project_type_in_state'] == [1]
assert s['entities'][3]['arrays']['project_array'][0] == -101 and v(s, 'active_projects', 3) == 1
assert s['entities'][4]['arrays']['project_array'][0] == 0 and v(s, 'active_projects', 4) == 0
cases.append('same-state later investor cleanup resets state break after earlier cleanup')

# Stale state metadata cannot select and cancel a different live slot.
s = accepted(duration=1)
stage(s, receiver=3, target=-102, amount=1, cost=20, duration=2)
assert send(s); respond(s, receiver=3)
s['entities'][-101]['variables']['project_target_state_@1'] = 1
before = money(s)
execute(click, s, context(1, scope=-101, previous=(-101,)))
assert money(s) == before and v(s, 'active_projects') == 2
assert s['entities'][1]['arrays']['project_array'][:2] == [-101,-102]
cases.append('stale GUI slot cannot cancel another live project')

# Offer requires legal original ownership, not merely control by an occupier.
s = state(); stage(s); s['entities'][-101]['owner'] = 3
assert not send(s) and v(s, 'treasury') == 1000
cases.append('occupation cannot create original consent')

# Hidden old settlement events are not registered for protocol 24. New slots are
# released synchronously; repeated cancellation cannot erase a replacement.
s = accepted(amount=1); run(s, 'end_project')
assert not any(event[0] in ('AC_event.30', 'AC_event.31') for event in s['events'])
stage(s, amount=1, cost=20); assert send(s); respond(s)
assert v(s, 'active_projects') == 1 and v(s, 'eon_project_protocol^0') == 24
run(s, 'complete_project'); assert not s['buildings']
cases.append('no delayed slot reset for new protocol')

# Full selected-state window predicates allow withdrawal under changed policy,
# including investor occupation. The override is keyed to our exact state slot.
show = one(one(load('common/scripted_guis/01_investment_scripted_gui.txt'), 'scripted_gui'), 'AC_show_Investment_window')
for reason in ('investor_control', 'disabled', 'rejecting_controller', 'war'):
    s = accepted(amount=1)
    if reason == 'investor_control': s['entities'][-101]['controller'] = 1
    elif reason == 'disabled': s['entities'][1]['flags'].add('disabled_foreign_investment')
    elif reason == 'rejecting_controller': s['entities'][2]['flags'].add('int_auto_reject_investment_flag')
    else: s['entities'][1]['wars'].add(2)
    c = context(1, scope=-101, previous=(-101,))
    assert condition(one(show, 'visible'), s, c)
    s['entities'][1]['flags'].discard('AC_hide_investment_window')
    assert condition(one(window, 'visible'), s, c)
    assert condition(enabled, s, c)
    execute(click, s, c)
    assert v(s, 'active_projects') == 0
    invariant(s)
    cases.append('full visibility and cancellation '+reason)

for corruption in ('wrong_index', 'wrong_protocol', 'foreign_investor', 'empty_slot'):
    s = accepted(amount=1)
    c = context(1, scope=-101, previous=(-101,))
    if corruption == 'wrong_index': s['entities'][-101]['variables']['project_target_state_@1'] = 5
    elif corruption == 'wrong_protocol': s['entities'][1]['variables']['eon_project_protocol^0'] = 0
    elif corruption == 'foreign_investor': c = context(4, scope=-101, previous=(-101,))
    else: s['entities'][1]['arrays']['project_array'][0] = 0
    assert not condition(triggers['eon_investment_lifecycle_own_state_project'], s, c)
    cases.append('own state override rejects '+corruption)

# Actual annex hook clears a new donor's project synchronously and returns the
# other payer's residual. The disappearing donor retains a non-spendable claim.
on_actions = one(load('common/on_actions/eon_investment_lifecycle_on_actions.txt'), 'on_actions')
for hook in ('on_annex', 'on_subject_annexed'):
    s = accepted(amount=2)
    effect = one(one(on_actions, hook), 'effect')
    execute(effect, s, context(3, 1) if hook == 'on_annex' else context(1, 3))
    assert v(s, 'active_projects') == 0
    assert v(s, 'treasury') == 970 and v(s, 'eon_investment_refund_claims') == 30
    assert v(s, 'treasury', 2) == 1000
    invariant(s)
    before = money(s)
    execute(effect, s, context(3, 1) if hook == 'on_annex' else context(1, 3))
    assert money(s) == before and v(s, 'eon_investment_refund_claims') == 30
    cases.append('actual annex source '+hook)

print(json.dumps({'all_passed': True, 'cases_passed': len(cases), 'cases': cases,
    'proof_scope': 'current-source bounded financial, state-control and callback execution',
    'limits': ['HOI4 engine and real multiplayer not executed',
               'Native building outcome and random outcome are explicit fixtures',
               'Qualified state build-result writers are an explicit routing assumption, not native proof',
               'Daily native scheduling, UI rendering, save/load and annex hook ordering unverified',
               'Legacy source remains explicit and is not migrated',
               'Bankruptcy test executes only actual pre-debt sale branch, not debt settlement UI']}, indent=2))
