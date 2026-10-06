"""Ordered actual-source antiterror cooperation; not a native campaign test."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '45dedfc85e7aece235f8fa1ab536326e6dce6923'
groups = Counter()

# Load definitions only. Prior suites execute and count separately in the runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_08/test_mediation.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# Native targeted selection is free until its fresh complete_effect sends the'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'antiterror_ordered_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch = (source[name] for name in ('ast', 'one', 'context', 'switch'))
source_trigger, source_execute = source['trigger'], source['execute']

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = result['countries'][ctx['scope']]
        if key == 'has_dynamic_modifier':
            modifier = one(val, 'modifier') if isinstance(val, list) else val
            passed = modifier in country['dynamic_modifiers']
        elif key == 'command_power':
            passed = model['compare'](country['variables']['command_power'], operator, float(val))
        elif key == 'is_in_faction': passed = (country['faction'] is not None) == (val == 'yes')
        elif key == 'any_allied_country':
            passed = any(trigger(val, result, switch(ctx, actor)) for actor in country['allies'])
        elif key in ('any_country', 'any_other_country'):
            passed = any(data['exists'] and (key != 'any_other_country' or actor != ctx['scope'])
                         and trigger(val, result, switch(ctx, actor)) for actor, data in result['countries'].items())
        elif key == 'has_faction_goal': passed = val in country['faction_goals']
        elif key == 'gives_military_access_to': passed = model['country_ref'](result, ctx, val) in country['military_access']
        elif key == 'has_volunteers_amount_from':
            actor = model['country_ref'](result, ctx, one(val, 'tag'))
            op, wanted = next((o, v) for k, o, v in val if k == 'count')
            passed = model['compare'](country['volunteers_from'].get(actor, 0), op, float(wanted))
        elif key == 'hidden_trigger': passed = trigger(val, result, ctx)
        elif key == 'is_in_array' and len(val) == 1:
            array, op, wanted = val[0]
            assert op == '=', ('Unsupported native array comparator', op)
            passed = model['value'](result, ctx, wanted) in country['arrays'].get(array, [])
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
        country = result['countries'][ctx['scope']]
        if key == 'add_dynamic_modifier':
            country['dynamic_modifiers'].add(one(val, 'modifier'))
            result.setdefault('dynamic_modifier_calls', []).append((ctx['scope'], one(val, 'modifier')))
        elif key == 'for_each_loop' and one(val, 'array') == 'global.countries':
            variable = one(val, 'value')
            for actor in result['countries']:
                result['temp'][variable] = actor
                execute([node for node in val if node[0] not in ('array', 'value')], result, ctx)
        elif key in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier'):
            target = model['country_ref'](result, ctx, one(val, 'target'))
            item = (target, one(val, 'modifier'))
            if key == 'add_opinion_modifier': country['opinion_modifiers'].add(item)
            elif key == 'remove_opinion_modifier': country['opinion_modifiers'].discard(item)
            elif target in result['countries']:
                result['countries'][target]['opinion_modifiers'].add((ctx['scope'], item[1]))
            result.setdefault('opinion_calls', []).append((ctx['scope'], key, item))
        else: source_execute(grouped, result, ctx)

for namespace in (source, source['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute

actions = one(ast(read('common/scripted_diplomatic_actions/MDC_terrorism.txt')), 'scripted_diplomatic_actions')
ct_action_path = ROOT / 'common/scripted_diplomatic_actions/eon_ct_actions.txt'
if ct_action_path.exists():
    additions = one(ast(ct_action_path.read_text(encoding='utf-8-sig')), 'scripted_diplomatic_actions')
    assert not {key for key, operator, val in actions} & {key for key, operator, val in additions}
    actions += additions
for registry, path in (('effects', 'common/scripted_effects/eon_ct_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_ct_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, operator, body in ast(read(path))}
        assert not additions.keys() & model[registry].keys(), 'Antiterror helpers overwrite a prior helper'
        model[registry].update(additions)
government_triggers = ast(read('common/scripted_triggers/99_GCC_scripted_triggers.txt'))
for name in ('jihadist_government', 'no_jihadist_government'):
    model['capacity_triggers'][name] = one(government_triggers, name)

def state():
    result = source['loader']['state']()
    for country in result['countries'].values():
        country.update(dynamic_modifiers=set(), opinion_modifiers=set(), overlord=None, co_war_partners=set(),
                       allies=set(), faction_goals=set(), military_access=set(), volunteers_from={})
        country['variables'].update(ct_effectiveness_add=0, ct_command_debuff=0, costil_command_buff=0, command_power=100,
                                    pending_antiterror_country=0, political_power=300)
        country['arrays'].update(ruling_party=[0], gov_coalition_array=[])
        country['opinions'].update(A=50, B=50, C=50, D=50)
    return result

def effect(result, nodes, actor='A', partner='B'):
    result['temp'] = {}
    execute(nodes, result, context(actor, scope=partner))

def check(result, nodes, actor='A', partner='B'):
    result['temp'] = {}
    return trigger(nodes, result, context(actor, scope=partner))

def body_optional(body, key):
    matches = [value for name, operator, value in body if name == key]
    assert len(matches) <= 1, (key, len(matches))
    return matches[0] if matches else None

def native_send(result, actor='A', partner='B'):
    body = one(actions, 'declare_anti_terror_agreement')
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'selectable', 'can_be_sent')]
    native_cost = float(one(body, 'cost'))
    ready = all(check(result, guard, actor, partner) for guard in guards)
    ready = ready and result['countries'][actor]['variables']['political_power'] >= native_cost
    if ready:
        # Explicit engine fixture: a native action debits its declared cost at send.
        # This is separate from the actual scripted on_sent effect; no refund implied.
        result['countries'][actor]['variables']['political_power'] -= native_cost
        result.setdefault('native_cost_fixture', []).append((actor, 'declare_anti_terror_agreement', native_cost))
        effect(result, one(body, 'on_sent_effect'), actor, partner)
    return ready

def native_response(result, accepted=True, actor='A', partner='B', force=False):
    body = one(actions, 'declare_anti_terror_agreement')
    guard = body_optional(body, 'can_be_accepted')
    ready = not accepted or guard is None or check(result, guard, actor, partner)
    if ready or force:
        effect(result, one(body, 'complete_effect' if accepted else 'reject_effect'), actor, partner)
    return ready

def direct_helper(result, name, actor='A', partner=None, temporary=None):
    result['temp'] = dict(temporary or {})
    execute([('eon_ct_' + name, '=', 'yes')], result, context(actor, partner))

def snapshot_external(result):
    return {actor: {key: deepcopy(value) for key, value in data.items() if key not in ('variables', 'flags', 'dynamic_modifiers', 'opinion_modifiers')}
            | {'variables': {key: deepcopy(value) for key, value in data['variables'].items()
                             if not key.startswith('eon_ct_') and key not in ('pending_antiterror_country', 'ct_effectiveness_add', 'ct_command_debuff', 'costil_command_buff')},
               'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_ct_', 'anti_terror_agreement'))}}
            for actor, data in result['countries'].items()}

def ct_values(result, actor):
    variables = result['countries'][actor]['variables']
    return tuple(variables.get(key, 0) for key in ('ct_effectiveness_add', 'ct_command_debuff', 'costil_command_buff'))

def assert_ct_values(result, actor, expected):
    assert all(model['compare'](left, '=', right) for left, right in zip(ct_values(result, actor), expected)), (actor, ct_values(result, actor), expected)

def assert_pending(result, sender='A', recipient='B'):
    for actor, partner, role in ((sender, recipient, 'outgoing'), (recipient, sender, 'incoming')):
        country = result['countries'][actor]
        assert country['variables'].get('eon_ct_partner') == partner
        assert 'eon_ct_' + role in country['flags'] and 'eon_ct_pending_window' in country['flags']
        assert country['variables'].get('pending_antiterror_country', 0) == (partner if role == 'outgoing' else 0)

def assert_pending_clear(result, *actors):
    for actor in actors or ('A', 'B'):
        country = result['countries'][actor]
        assert not country['flags'] & {'eon_ct_outgoing', 'eon_ct_incoming', 'eon_ct_cancelled', 'eon_ct_pending_window'}
        assert country['variables'].get('eon_ct_partner', 0) == 0

def assert_active(result, actor='A', partner='B'):
    for owner, peer in ((actor, partner), (partner, actor)):
        flags = result['countries'][owner]['flags']
        assert {'anti_terror_agreement@' + peer, 'eon_ct_contribution@' + peer} <= flags

def clear_cooldowns(result):
    for country in result['countries'].values():
        country['flags'] = {flag for flag in country['flags'] if not flag.startswith('anti_terror_agreement_cooldown')}

def native_immediate_action(result, identity, actor='A', partner='B', force=False):
    body = one(actions, identity)
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'selectable', 'can_be_sent')]
    ready = all(check(result, guard, actor, partner) for guard in guards)
    native_cost = float(one(body, 'cost'))
    ready = ready and result['countries'][actor]['variables']['political_power'] >= native_cost
    if ready:
        result['countries'][actor]['variables']['political_power'] -= native_cost
        result.setdefault('native_cost_fixture', []).append((actor, identity, native_cost))
    if ready or force: effect(result, one(body, 'complete_effect'), actor, partner)
    return ready

def native_hook(result, name, victim='B', subject=False, old_first=True):
    current = one(ast(read('common/on_actions/eon_ct_on_actions.txt')), 'on_actions')
    old = one(ast(read('common/on_actions/00_terrorist_on_actions.txt')), 'on_actions')
    ctx = context(victim, 'D') if subject else context('D', victim)
    for source_hooks in ((old, current) if old_first else (current, old)):
        result['temp'] = {}
        execute(one(one(source_hooks, name), 'effect'), result, ctx)

def ai_score(result, key, actor='A', partner='B'):
    body = one(one(actions, 'declare_anti_terror_agreement'), key)
    ctx = context(actor, scope=partner)
    result['temp'] = {}
    if key == 'ai_acceptance':
        score = 0
        for name, operator, component in body:
            contribution = float(one(component, 'base'))
            for modifier, op, conditions in component:
                if modifier == 'modifier' and trigger([node for node in conditions if node[0] not in ('add', 'factor')], result, ctx):
                    for operation, _, operand in conditions:
                        if operation == 'add': contribution += model['value'](result, ctx, operand)
                        elif operation == 'factor': contribution *= model['value'](result, ctx, operand)
            score += contribution
        return score
    score = float(one(body, 'base'))
    for key, operator, modifier in body:
        if key == 'modifier' and trigger([node for node in modifier if node[0] not in ('factor', 'add')], result, ctx):
            for operation, op, operand in modifier:
                if operation == 'factor': score *= model['value'](result, ctx, operand)
                elif operation == 'add': score += model['value'](result, ctx, operand)
    return score

# The actual native declaration callback must contribute once to both countries.
# This initial regression is intentionally RED on the unchanged upstream action.
declare = one(actions, 'declare_anti_terror_agreement')
cancel = one(actions, 'cancel_anti_terror_agreement')
focus = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == '--focus' else None
assert focus in (None, 'complete', 'cancel', 'annex', 'withdraw', 'incoming_withdraw', 'orphan_cancel'), ('Unknown focused proof', sys.argv[1:])

if focus in (None, 'orphan_cancel'):
    for actor in ('A', 'B'):
        result = state()
        result['countries'][actor]['flags'].update({'eon_ct_cancelled', 'eon_ct_pending_window'})
        result['countries'][actor]['variables']['eon_ct_partner'] = 'D'
        assert native_send(result)
        ready = native_response(result, force=True)
        assert ready and all(ct_values(result, member) == (.05, -5, 5) for member in ('A', 'B')), (
            'RED: an unreserved orphan cancellation poisons a fresh antiterror proposal', actor, ready,
            {member: ct_values(result, member) for member in ('A', 'B')})
        groups['fresh_owned_record_clears_orphan_cancelled_state'] += 1

if focus in (None, 'withdraw', 'incoming_withdraw'):
    result = state(); assert native_send(result)
    before = deepcopy(result['countries'])
    ready = native_immediate_action(result, 'eon_withdraw_antiterror_proposal', actor='B', partner='A', force=True)
    assert not ready and result['countries'] == before, (
        'RED: the recipient can withdraw somebody else\'s pending proposal', ready,
        {actor: result['countries'][actor]['flags'] for actor in ('A', 'B')})
    groups['only_original_sender_can_withdraw_pending_proposal'] += 1

if focus in (None, 'complete'):
    result = state()
    effect(result, one(declare, 'on_sent_effect'))
    effect(result, one(declare, 'complete_effect'))
    assert all(ct_values(result, actor) == (.05, -5, 5) for actor in ('A', 'B'))
    effect(result, one(declare, 'complete_effect'))
    assert all(ct_values(result, actor) == (.05, -5, 5) for actor in ('A', 'B')), (
        'RED: repeated native completion duplicates the antiterror contribution',
        {actor: ct_values(result, actor) for actor in ('A', 'B')})
    groups['repeated_native_completion_contributes_once'] += 1

if focus in (None, 'cancel'):
    result = state()
    effect(result, one(declare, 'on_sent_effect')); effect(result, one(declare, 'complete_effect'))
    effect(result, one(cancel, 'complete_effect'))
    assert all(ct_values(result, actor) == (0, 0, 0) for actor in ('A', 'B'))
    effect(result, one(cancel, 'complete_effect'))
    assert all(ct_values(result, actor) == (0, 0, 0) for actor in ('A', 'B')), (
        'RED: repeated native cancellation subtracts an absent contribution',
        {actor: ct_values(result, actor) for actor in ('A', 'B')})
    groups['repeated_native_cancellation_releases_once'] += 1

if focus in (None, 'annex'):
    hooks = one(ast(read('common/on_actions/00_terrorist_on_actions.txt')), 'on_actions')
    result = state()
    effect(result, one(declare, 'on_sent_effect')); effect(result, one(declare, 'complete_effect'))
    result['countries']['B']['exists'] = False
    result['temp'] = {}
    execute(one(one(hooks, 'on_annex'), 'effect'), result, context('C', 'B'))
    assert 'anti_terror_agreement@B' not in result['countries']['A']['flags']
    assert ct_values(result, 'A') == (0, 0, 0), (
        'RED: old annex removes the flag but leaves the surviving antiterror contribution', ct_values(result, 'A'))
    groups['native_annex_releases_survivor_contribution'] += 1

if focus is None:
    # Both native participant roles retain one paid send and exactly one contribution.
    for sender, recipient, ai in (('A', 'B', False), ('B', 'A', True)):
        result = state(); result['countries'][recipient]['ai'] = ai
        before = snapshot_external(result)
        assert native_send(result, sender, recipient); assert_pending(result, sender, recipient)
        assert result['countries'][sender]['variables']['political_power'] == 225
        assert_ct_values(result, sender, (0, 0, 0)); assert_ct_values(result, recipient, (0, 0, 0))
        timers = {name: days for owner, name, days in result['timer_declarations']}
        assert timers['eon_ct_pending_window'] == 30
        assert timers['anti_terror_agreement_cooldown@' + recipient] == 120
        assert timers['anti_terror_agreement_cooldown@' + sender] == 120
        assert timers['anti_terror_agreement_cooldown_global'] == 120
        assert native_response(result, actor=sender, partner=recipient)
        assert_pending_clear(result, sender, recipient); assert_active(result, sender, recipient)
        calls = deepcopy(result['opinion_calls']); modifiers = deepcopy(result['dynamic_modifier_calls'])
        native_response(result, actor=sender, partner=recipient, force=True)
        assert result['opinion_calls'] == calls and result['dynamic_modifier_calls'] == modifiers
        assert 'ct_effectiveness' in result['countries'][recipient]['dynamic_modifiers']
        assert ('costilb_modifier' in result['countries'][recipient]['dynamic_modifiers']) == ai
        expected = deepcopy(before); expected[sender]['variables']['political_power'] = 225
        assert snapshot_external(result) == expected
        groups['native_cost_mirrored_roles_timers_and_single_bilateral_rewards'] += 1

    for sender, recipient in (('A', 'B'), ('B', 'A')):
        result = state(); assert native_send(result, sender, recipient)
        assert native_response(result, accepted=False, actor=sender, partner=recipient)
        assert_pending_clear(result, sender, recipient)
        for actor, peer in ((sender, recipient), (recipient, sender)):
            assert_ct_values(result, actor, (0, 0, 0))
            assert (peer, 'counter_terror_cooperation_reject') in result['countries'][actor]['opinion_modifiers']
        calls = deepcopy(result['opinion_calls']); countries = deepcopy(result['countries'])
        native_response(result, accepted=False, actor=sender, partner=recipient, force=True)
        assert result['countries'] == countries and result['opinion_calls'] == calls
        assert result['countries'][sender]['variables']['political_power'] == 225
        groups['valid_native_refusal_once_without_native_cost_refund'] += 1

    for sender, recipient in (('A', 'B'), ('B', 'A')):
        result = state(); assert native_send(result, sender, recipient)
        before_pp = {actor: data['variables']['political_power'] for actor, data in result['countries'].items()}
        assert native_immediate_action(result, 'eon_withdraw_antiterror_proposal', sender, recipient)
        assert_pending(result, sender, recipient)
        assert all('eon_ct_cancelled' in result['countries'][actor]['flags'] for actor in (sender, recipient))
        assert not native_send(result, sender, 'C')
        frozen = deepcopy(result['countries'])
        assert not native_immediate_action(result, 'eon_withdraw_antiterror_proposal', sender, recipient, force=True)
        assert result['countries'] == frozen
        assert not native_response(result, actor=sender, partner=recipient, force=True)
        assert_pending_clear(result, sender, recipient)
        assert not result.get('opinion_calls')
        assert {actor: data['variables']['political_power'] for actor, data in result['countries'].items()} == before_pp
        clear_cooldowns(result); assert native_send(result, sender, recipient)
        groups['sender_free_withdraw_retains_original_popup_lock_until_consumed'] += 1

    hard_cases = ('self', 'sender absent', 'receiver absent', 'direct war', 'opinion9', 'allied war',
                  'sender pending role', 'receiver pending role', 'sender legacy pointer', 'receiver legacy pointer',
                  'sender active', 'receiver active', 'sender contribution', 'receiver contribution',
                  'sender retired', 'receiver retired', 'sender pair cooldown', 'receiver pair cooldown',
                  'sender global cooldown', 'insufficient75')
    for alteration in hard_cases:
        result = state(); actor = 'A'; recipient = 'B'
        a, b = result['countries']['A'], result['countries']['B']
        if alteration == 'self': recipient = 'A'
        elif alteration == 'sender absent': a['exists'] = False
        elif alteration == 'receiver absent': b['exists'] = False
        elif alteration == 'direct war': a['wars'].add('B'); b['wars'].add('A')
        elif alteration == 'opinion9': b['opinions']['A'] = 9
        elif alteration == 'allied war':
            b['faction'] = 'shared'; b['allies'].add('C'); result['countries']['C']['wars'].add('A')
        elif alteration == 'sender pending role': a['flags'].add('eon_ct_incoming')
        elif alteration == 'receiver pending role': b['flags'].add('eon_ct_outgoing')
        elif alteration == 'sender legacy pointer': a['variables']['pending_antiterror_country'] = 'C'
        elif alteration == 'receiver legacy pointer': b['variables']['pending_antiterror_country'] = 'C'
        elif alteration.startswith('sender '):
            flag = {'active':'anti_terror_agreement@B', 'contribution':'eon_ct_contribution@B',
                    'retired':'eon_ct_retired_pair@B', 'pair cooldown':'anti_terror_agreement_cooldown@B',
                    'global cooldown':'anti_terror_agreement_cooldown_global'}[alteration[7:]]
            a['flags'].add(flag)
        elif alteration.startswith('receiver '):
            flag = {'active':'anti_terror_agreement@A', 'contribution':'eon_ct_contribution@A',
                    'retired':'eon_ct_retired_pair@A', 'pair cooldown':'anti_terror_agreement_cooldown@A'}[alteration[9:]]
            b['flags'].add(flag)
        elif alteration == 'insufficient75': a['variables']['political_power'] = 74.99
        before = deepcopy(result['countries'])
        assert not native_send(result, actor, recipient), ('Hard native send gate bypassed', alteration)
        effect(result, one(declare, 'on_sent_effect'), actor, recipient)
        if alteration != 'insufficient75': assert result['countries'] == before, ('Cached send did not recheck', alteration)
        else:
            # on_sent follows a charged native admission and intentionally excludes
            # a second PP guard; normal selectable/can_be_sent already failed above.
            assert_pending(result)
        groups['fresh_native_hard_pair_and_existing_cooldown_gates'] += 1

    for alteration in ('opinion10', 'receiver global cooldown', 'sender third war', 'receiver third war',
                       'sender jihadist', 'receiver jihadist', 'low receiver command power', 'no great-power rank'):
        result = state(); a, b = result['countries']['A'], result['countries']['B']
        if alteration == 'opinion10': b['opinions']['A'] = 10
        elif alteration == 'receiver global cooldown': b['flags'].add('anti_terror_agreement_cooldown_global')
        elif alteration == 'sender third war': a['wars'].add('C'); result['countries']['C']['wars'].add('A')
        elif alteration == 'receiver third war': b['wars'].add('C'); result['countries']['C']['wars'].add('B')
        elif alteration == 'sender jihadist': a['arrays']['gov_coalition_array'] = [11]
        elif alteration == 'receiver jihadist': b['arrays']['ruling_party'] = [11]
        elif alteration == 'low receiver command power': b['variables']['command_power'] = 99.99
        assert native_send(result), ('A weighted AI consideration became a human hard gate', alteration)
        assert native_response(result); assert_active(result)
        groups['human_eligibility_retains_weighted_ai_politics_and_no_rank_gate'] += 1

    result = state(); result['countries']['A']['variables']['political_power'] = 75
    assert native_send(result); assert result['countries']['A']['variables']['political_power'] == 0
    assert_pending(result); assert native_response(result)
    assert result['countries']['A']['variables']['political_power'] == 0
    groups['paid_send_accepts_exact75_without_requiring_cost_twice'] += 1

    result = state(); assert native_send(result); assert_pending(result)
    before = deepcopy(result['countries'])
    for sender, recipient in (('A', 'C'), ('C', 'B'), ('B', 'A')):
        assert not native_send(result, sender, recipient)
        effect(result, one(declare, 'on_sent_effect'), sender, recipient)
        assert result['countries'] == before
    groups['cached_and_overlapping_native_sends_cannot_replace_pending_pair'] += 1

    for alteration in ('opinion now9', 'new allied war', 'sender window absent', 'receiver window absent'):
        result = state(); assert native_send(result)
        if alteration == 'opinion now9': result['countries']['B']['opinions']['A'] = 9
        elif alteration == 'new allied war':
            result['countries']['B']['faction'] = 'shared'; result['countries']['B']['allies'].add('C')
            result['countries']['C']['wars'].add('A')
        elif alteration == 'sender window absent': result['countries']['A']['flags'].discard('eon_ct_pending_window')
        elif alteration == 'receiver window absent': result['countries']['B']['flags'].discard('eon_ct_pending_window')
        assert not native_response(result, force=True), ('Late consent ignored fresh validity', alteration)
        assert_pending_clear(result)
        assert not result.get('opinion_calls')
        for actor in ('A', 'B'):
            assert_ct_values(result, actor, (0, 0, 0))
            assert not any(flag.startswith('eon_ct_retired_pair@') for flag in result['countries'][actor]['flags'])
        assert result['countries']['A']['variables']['political_power'] == 225
        groups['consumed_original_callback_rechecks_fresh_policy_and_both_windows'] += 1

    result = state(); assert native_send(result)
    result['countries']['B']['opinions']['A'] = 9
    direct_helper(result, 'daily_cleanup'); assert_pending(result)
    assert not native_response(result, force=True); assert_pending_clear(result)
    result['countries']['B']['opinions']['A'] = 50
    clear_cooldowns(result); assert native_send(result)
    groups['low_opinion_blocks_acceptance_without_forced_pair_retirement'] += 1

    for sender, recipient in (('C', 'B'), ('A', 'C'), ('B', 'A')):
        result = state(); assert native_send(result)
        frozen = deepcopy(result['countries'])
        native_response(result, actor=sender, partner=recipient, force=True)
        native_response(result, accepted=False, actor=sender, partner=recipient, force=True)
        assert result['countries'] == frozen and not result.get('opinion_calls')
        assert_pending(result)
        groups['wrong_native_sender_receiver_and_role_callbacks_are_inert'] += 1

    for owner, expiry in (('A', 'A'), ('A', 'B'), ('B', 'A'), ('B', 'B')):
        result = state(); assert native_send(result)
        result['countries'][expiry]['flags'].discard('eon_ct_pending_window')
        direct_helper(result, 'daily_cleanup', actor=owner)
        assert_pending_clear(result)
        assert 'eon_ct_retired_pair@B' in result['countries']['A']['flags']
        assert 'eon_ct_retired_pair@A' in result['countries']['B']['flags']
        clear_cooldowns(result); assert not native_send(result)
        assert native_send(result, 'A', 'C'); assert native_send(result, 'B', 'D')
        frozen = deepcopy(result['countries'])
        native_response(result, force=True); native_response(result, accepted=False, force=True)
        assert result['countries'] == frozen
        groups['forced_either_window_expiry_from_either_owner_retires_pair_before_release'] += 1

    for victim in ('A', 'B'):
        result = state(); assert native_send(result)
        result['countries'][victim]['exists'] = False
        direct_helper(result, 'daily_cleanup', actor='B' if victim == 'A' else 'A')
        assert_pending_clear(result)
        result['countries'][victim]['exists'] = True; clear_cooldowns(result)
        assert not native_send(result)
        assert native_send(result, 'A', 'C'); assert native_send(result, 'B', 'D')
        frozen = deepcopy(result['countries']); native_response(result, force=True)
        assert result['countries'] == frozen
        groups['missing_sender_or_receiver_cannot_revive_into_an_unconsumed_old_popup'] += 1

    result = state(); assert native_send(result)
    result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
    direct_helper(result, 'daily_cleanup')
    assert_pending_clear(result)
    assert 'eon_ct_retired_pair@B' in result['countries']['A']['flags']
    assert not result.get('opinion_calls')
    groups['direct_war_forces_pending_cleanup_without_treating_third_war_as_same'] += 1

    for hook, subject in (('on_annex', False), ('on_subject_annexed', True)):
        for victim in ('A', 'B'):
            for old_first in (False, True):
                result = state(); assert native_send(result)
                result['countries'][victim]['exists'] = False
                native_hook(result, hook, victim, subject, old_first)
                assert_pending_clear(result)
                assert 'eon_ct_retired_pair@B' in result['countries']['A']['flags']
                assert 'eon_ct_retired_pair@A' in result['countries']['B']['flags']
                result['countries'][victim]['exists'] = True; clear_cooldowns(result)
                assert not native_send(result)
                assert native_send(result, 'A', 'C'); assert native_send(result, 'B', 'D')
                frozen = deepcopy(result['countries']); native_response(result, force=True)
                assert result['countries'] == frozen
                groups['pending_native_annex_both_roles_hooks_and_order_preserve_old_callback_identity'] += 1

    for alteration in ('outgoing compatibility mismatch', 'incoming compatibility nonzero', 'both roles',
                       'peer no role', 'peer points elsewhere'):
        result = state(); assert native_send(result)
        if alteration == 'outgoing compatibility mismatch': result['countries']['A']['variables']['pending_antiterror_country'] = 'D'
        elif alteration == 'incoming compatibility nonzero': result['countries']['B']['variables']['pending_antiterror_country'] = 'D'
        elif alteration == 'both roles': result['countries']['A']['flags'].add('eon_ct_incoming')
        elif alteration == 'peer no role': result['countries']['B']['flags'].discard('eon_ct_incoming')
        elif alteration == 'peer points elsewhere': result['countries']['B']['variables']['eon_ct_partner'] = 'D'
        native_response(result, force=True)
        assert_ct_values(result, 'A', (0, 0, 0)); assert_ct_values(result, 'B', (0, 0, 0))
        assert not result.get('opinion_calls')
        direct_helper(result, 'daily_cleanup')
        if alteration == 'outgoing compatibility mismatch':
            assert result['countries']['A']['variables']['pending_antiterror_country'] == 'D'
            clear_cooldowns(result); assert not native_send(result, 'A', 'C')
        elif alteration == 'incoming compatibility nonzero':
            assert result['countries']['B']['variables']['pending_antiterror_country'] == 'D'
        elif alteration == 'peer points elsewhere':
            assert result['countries']['B']['variables']['eon_ct_partner'] == 'D'
            assert 'eon_ct_incoming' in result['countries']['B']['flags']
        groups['malformed_pending_records_do_not_create_bonus_or_erase_unknown_legacy_pointer'] += 1

    result = state(); result['countries']['A']['variables']['pending_antiterror_country'] = 'D'
    before = deepcopy(result['countries'])
    direct_helper(result, 'daily_cleanup')
    native_response(result, force=True); native_response(result, accepted=False, force=True)
    assert result['countries'] == before and not native_send(result)
    groups['unmanaged_legacy_pending_pointer_is_not_guessed_or_cleared'] += 1

    for actor, peer in (('A', 'B'), ('B', 'A')):
        result = state(); assert native_send(result); assert native_response(result)
        assert native_immediate_action(result, 'cancel_anti_terror_agreement', actor, peer)
        assert_ct_values(result, 'A', (0, 0, 0)); assert_ct_values(result, 'B', (0, 0, 0))
        frozen = deepcopy(result['countries']); calls = deepcopy(result['opinion_calls'])
        assert not native_immediate_action(result, 'cancel_anti_terror_agreement', actor, peer, force=True)
        assert result['countries'] == frozen and result['opinion_calls'] == calls
        expected_pp = 150 if actor == 'A' else 225
        assert result['countries'][actor]['variables']['political_power'] == expected_pp
        assert 'ct_effectiveness' in result['countries']['A']['dynamic_modifiers']
        groups['either_active_partner_pays_native_cancel75_and_releases_component_once'] += 1

    # Shared totals contain a known legacy A-C component and unrelated baseline.
    result = state()
    result['countries']['A']['variables'].update(ct_effectiveness_add=.22, ct_command_debuff=-18, costil_command_buff=14)
    result['countries']['C']['variables'].update(ct_effectiveness_add=.05, ct_command_debuff=-5, costil_command_buff=5)
    result['countries']['A']['flags'].add('anti_terror_agreement@C')
    result['countries']['C']['flags'].add('anti_terror_agreement@A')
    direct_helper(result, 'daily_cleanup')
    assert_active(result, 'A', 'C'); assert_ct_values(result, 'A', (.22, -18, 14))
    assert native_send(result); assert native_response(result)
    assert_ct_values(result, 'A', (.27, -23, 19))
    assert native_immediate_action(result, 'cancel_anti_terror_agreement')
    assert_ct_values(result, 'A', (.22, -18, 14)); assert_active(result, 'A', 'C')
    assert native_immediate_action(result, 'cancel_anti_terror_agreement', 'A', 'C')
    assert_ct_values(result, 'A', (.17, -13, 9)); assert_ct_values(result, 'C', (0, 0, 0))
    groups['legacy_adoption_and_stacked_contract_subtractions_preserve_unrelated_shared_totals'] += 1

    for alteration in ('direct war', 'dead sender', 'dead receiver', 'sender flag missing', 'receiver flag missing',
                       'both flags missing markers remain'):
        result = state(); assert native_send(result); assert native_response(result)
        if alteration == 'direct war': result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
        elif alteration == 'dead sender': result['countries']['A']['exists'] = False
        elif alteration == 'dead receiver': result['countries']['B']['exists'] = False
        elif alteration == 'sender flag missing': result['countries']['A']['flags'].discard('anti_terror_agreement@B')
        elif alteration == 'receiver flag missing': result['countries']['B']['flags'].discard('anti_terror_agreement@A')
        elif alteration == 'both flags missing markers remain':
            result['countries']['A']['flags'].discard('anti_terror_agreement@B'); result['countries']['B']['flags'].discard('anti_terror_agreement@A')
        direct_helper(result, 'daily_cleanup', actor='B' if alteration == 'dead sender' else 'A')
        for actor, peer in (('A', 'B'), ('B', 'A')):
            assert_ct_values(result, actor, (0, 0, 0))
            assert not result['countries'][actor]['flags'] & {'anti_terror_agreement@' + peer, 'eon_ct_contribution@' + peer}
        frozen = deepcopy(result['countries']); direct_helper(result, 'daily_cleanup')
        assert result['countries'] == frozen
        groups['active_daily_war_death_and_missing_flags_release_identifiable_components_once'] += 1

    for alteration in ('low opinion', 'third country war'):
        result = state(); assert native_send(result); assert native_response(result)
        if alteration == 'low opinion': result['countries']['B']['opinions']['A'] = -100
        else: result['countries']['A']['wars'].add('C'); result['countries']['C']['wars'].add('A')
        direct_helper(result, 'daily_cleanup'); assert_active(result)
        assert_ct_values(result, 'A', (.05, -5, 5)); assert_ct_values(result, 'B', (.05, -5, 5))
        groups['active_agreement_is_not_ended_by_low_opinion_or_unrelated_war'] += 1

    for hook, subject in (('on_annex', False), ('on_subject_annexed', True)):
        for victim in ('A', 'B'):
            for old_first in (False, True):
                result = state(); assert native_send(result); assert native_response(result)
                clear_cooldowns(result); assert native_send(result, 'A', 'C'); assert native_response(result, actor='A', partner='C')
                result['countries'][victim]['exists'] = False
                native_hook(result, hook, victim, subject, old_first)
                assert_ct_values(result, 'B', (0, 0, 0))
                assert_ct_values(result, 'A', (0, 0, 0) if victim == 'A' else (.05, -5, 5))
                assert_ct_values(result, 'C', (0, 0, 0) if victim == 'A' else (.05, -5, 5))
                if victim == 'B': assert_active(result, 'A', 'C')
                frozen = deepcopy(result['countries']); native_hook(result, hook, victim, subject, not old_first)
                assert result['countries'] == frozen
                groups['active_native_annex_both_roles_hooks_orders_preserve_other_live_contract'] += 1

    for marker in ('legacy one-sided flag', 'owned marker only', 'unknown totals without flags'):
        result = state()
        result['countries']['A']['variables'].update(ct_effectiveness_add=.05, ct_command_debuff=-5, costil_command_buff=5)
        if marker == 'legacy one-sided flag': result['countries']['A']['flags'].add('anti_terror_agreement@B')
        elif marker == 'owned marker only': result['countries']['A']['flags'].add('eon_ct_contribution@B')
        direct_helper(result, 'daily_cleanup')
        assert_ct_values(result, 'A', (.05, -5, 5) if marker == 'unknown totals without flags' else (0, 0, 0))
        assert_ct_values(result, 'B', (0, 0, 0))
        groups['known_legacy_or_marker_only_component_is_reversed_unknown_totals_are_preserved'] += 1

    for state_kind in ('pending', 'active'):
        result = state(); assert native_send(result)
        if state_kind == 'active': assert native_response(result)
        frozen = {actor: deepcopy(result['countries'][actor]) for actor in ('A', 'B')}
        result['countries']['D']['variables']['eon_ct_partner'] = 'B'
        result['countries']['D']['flags'].add('eon_ct_outgoing')
        result['countries']['D']['variables']['pending_antiterror_country'] = 'B'
        direct_helper(result, 'daily_cleanup', actor='D')
        actual = {actor: deepcopy(result['countries'][actor]) for actor in ('A', 'B')}
        # D's declared stale D-B request conservatively retires its own known
        # response edge; the live A-B identity and contribution remain untouched.
        actual['B']['flags'].discard('eon_ct_retired_pair@D')
        assert actual == frozen
        assert 'eon_ct_retired_pair@A' not in result['countries']['B']['flags']
        groups['stray_nonreciprocal_record_cannot_clear_another_owned_pair'] += 1

    for alteration, expected in (('ordinary', 25), ('cp99.99', -975), ('cp100', 25), ('jihadist coalition', -975),
                                 ('third war', -975), ('same faction goal', 525), ('low cp with same goal', -475),
                                 ('all weighted negatives', -2975)):
        result = state(); a, b = result['countries']['A'], result['countries']['B']
        if alteration in ('cp99.99', 'low cp with same goal', 'all weighted negatives'): b['variables']['command_power'] = 99.99
        if alteration in ('jihadist coalition', 'all weighted negatives'): b['arrays']['gov_coalition_array'] = [11]
        if alteration in ('third war', 'all weighted negatives'): b['wars'].add('C'); result['countries']['C']['wars'].add('B')
        if alteration in ('same faction goal', 'low cp with same goal'):
            a['faction'] = b['faction'] = 'shared'; b['faction_goals'].add('faction_goal_antiterror_cooperation')
        assert ai_score(result, 'ai_acceptance') == expected, ('Changed native acceptance weight', alteration)
        assert native_send(result), ('Weighted AI refusal incorrectly became a universal hard gate', alteration)
        groups['actual_ai_acceptance_politics_cp100_war_and_goal_weights'] += 1

    for alteration, expected in (('ordinary', 0), ('original opinion and threat', 25), ('access', 50),
                                 ('same goal', 500), ('all positive', 575), ('pending with positive weights', 575),
                                 ('cooldown with positive weights', 575), ('third war with positive weights', 575)):
        result = state(); a, b = result['countries']['A'], result['countries']['B']
        if alteration not in ('ordinary', 'access', 'same goal'):
            a['opinions']['A'] = 76; b['opinions']['A'] = 76
            a['variables']['terrorism_mana'] = b['variables']['terrorism_mana'] = 6
        if alteration in ('access', 'all positive', 'pending with positive weights', 'cooldown with positive weights', 'third war with positive weights'):
            b['military_access'].add('A')
        if alteration in ('same goal', 'all positive', 'pending with positive weights', 'cooldown with positive weights', 'third war with positive weights'):
            a['faction'] = b['faction'] = 'shared'; b['faction_goals'].add('faction_goal_antiterror_cooperation')
        if alteration == 'pending with positive weights': a['variables']['pending_antiterror_country'] = 'C'
        if alteration == 'cooldown with positive weights': a['flags'].add('anti_terror_agreement_cooldown_global')
        if alteration == 'third war with positive weights': a['wars'].add('C'); result['countries']['C']['wars'].add('A')
        assert ai_score(result, 'ai_desire') == expected, ('Existing ordered native desire arithmetic changed', alteration)
        if alteration in ('pending with positive weights', 'cooldown with positive weights'):
            assert not native_send(result), ('Positive preserved AI weights bypassed fresh source admission', alteration)
        groups['actual_ordered_ai_desire_weights_do_not_bypass_hard_native_admission'] += 1

    result = state()
    for actor, peer in (('A', 'D'), ('D', 'A')):
        result['countries'][actor]['flags'].update({'eon_consultation_reserved', 'eon_consultation_active', 'eon_consultation_active_window'})
        result['countries'][actor]['variables'].update(eon_consultation_partner=peer, eon_consultation_topic=3)
    result['countries']['A']['variables'].update(eon_aid_partner='D', eon_aid_amount=15, eon_aid_escrow=15,
                                               eon_support_refund_due=11, pending_assume_debt_offer='B',
                                               assuming_debt_value=40, assuming_debt_repayment_value=10)
    result['countries']['A']['flags'].update({'eon_aid_reserved', 'eon_aid_outgoing', 'trade_agreement@D', 'mutual_investment_treaty_@D'})
    result['countries']['D']['variables'].update(eon_aid_partner='A', eon_aid_amount=15)
    result['countries']['D']['flags'].update({'eon_aid_reserved', 'eon_aid_incoming'})
    before = snapshot_external(result)
    assert native_send(result); assert native_response(result)
    assert native_immediate_action(result, 'cancel_anti_terror_agreement')
    expected = deepcopy(before); expected['A']['variables']['political_power'] -= 150
    assert snapshot_external(result) == expected
    groups['source_send_accept_end_preserves_aid_debt_energy_treaties_and_consultation'] += 1

source_paths = ['common/scripted_diplomatic_actions/MDC_terrorism.txt', 'common/on_actions/00_terrorist_on_actions.txt',
                'common/scripted_effects/eon_ct_effects.txt', 'common/scripted_triggers/eon_ct_triggers.txt',
                'common/scripted_diplomatic_actions/eon_ct_actions.txt', 'common/on_actions/eon_ct_on_actions.txt',
                'localisation/english/eon_ct_l_english.yml', 'localisation/russian/eon_ct_l_russian.yml']

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()),
                  'adapter_semantics_cases': 0, 'total_cases': sum(groups.values()),
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'groups': groups, 'baseline': BASELINE,
                  'proof_scope': 'ordered actual-source antiterror lifecycle with explicit native facts and native cost fixture',
                  'not_proven': ['native costs and callback order', 'elapsed timers', 'GUI', 'save/load', 'campaign']}, indent=2))
