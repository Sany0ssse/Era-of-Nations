"""Ordered actual-source Send_ammo lifecycle; not a HOI4 runtime test."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '0e70f281145041d9e707089623ef5ecb610b744f'
groups = Counter()
adapter_cases = Counter()

# Definitions only: prior behavior suites are counted independently by the runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_08/test_mediation.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\n# Native targeted selection is free until its fresh complete_effect sends the'
assert executor_text.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'ammo_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch = (source[name] for name in ('ast', 'one', 'context', 'switch'))
source_trigger, source_execute, source_value = source['trigger'], source['execute'], model['value']

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

ACTION_PATH = 'common/scripted_diplomatic_actions/MDC_send_ammo.txt'
native = ast(read(ACTION_PATH))
QUANTITY = float(one(native, '@Ammo_send_qty'))
assert QUANTITY == 100000
actions = one(native, 'scripted_diplomatic_actions')
ammo = one(actions, 'Send_ammo')

def value(result, ctx, token):
    if token == '@Ammo_send_qty': return QUANTITY
    return source_value(result, ctx, token)

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = result['countries'][ctx['scope']]
        if key == 'is_ally_with':
            passed = model['country_ref'](result, ctx, val) in country['allies']
        elif key in ('any_allied_country', 'any_subject_country'):
            peers = country['allies'] if key == 'any_allied_country' else country['subjects']
            passed = any(result['countries'][actor]['exists'] and trigger(val, result, switch(ctx, actor)) for actor in peers)
        elif key in ('any_country', 'any_other_country'):
            passed = any(data['exists'] and (key == 'any_country' or actor != ctx['scope'])
                         and trigger(val, result, switch(ctx, actor)) for actor, data in result['countries'].items())
        elif key == 'has_same_ideology': passed = (country['government'] == result['countries'][ctx['root']]['government']) == (val == 'yes')
        elif key == 'is_guaranteed_by': passed = model['country_ref'](result, ctx, val) in country['guarantors']
        elif key == 'threat': passed = model['compare'](result['threat'], operator, value(result, ctx, val))
        elif key in ('clamp_temp_variable', 'round_temp_variable'):
            # Both primitive commands are valid in the native trigger context.
            execute(grouped, result, ctx); passed = True
        elif key == 'has_country_flag' and isinstance(val, list):
            name = model['flag_name'](result, ctx, one(val, 'flag'))
            op, expected = next((o, v) for k, o, v in val if k == 'value')
            passed = name in country['flags'] and model['compare'](country['flag_values'].get(name, 0), op, value(result, ctx, expected))
        elif key == 'has_opinion_modifier':
            if isinstance(val, list):
                target = model['country_ref'](result, ctx, one(val, 'target'))
                passed = (target, one(val, 'modifier')) in country['opinion_modifiers']
            else: passed = any(modifier == val for target, modifier in country['opinion_modifiers'])
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
        if key in ('add_opinion_modifier', 'remove_opinion_modifier'):
            target = model['country_ref'](result, ctx, one(val, 'target'))
            item = (target, one(val, 'modifier'))
            if key == 'add_opinion_modifier': country['opinion_modifiers'].add(item)
            else: country['opinion_modifiers'].discard(item)
            result.setdefault('opinion_calls', []).append((ctx['scope'], key, item))
        elif key == 'modify_country_flag':
            name = model['flag_name'](result, ctx, one(val, 'flag'))
            assert name in country['flags'], ('Fixture flag modification requires a present native flag', name)
            country['flag_values'][name] = country['flag_values'].get(name, 0) + value(result, ctx, one(val, 'value'))
            result.setdefault('timer_declarations', []).append((ctx['scope'], name, value(result, ctx, one(val, 'days'))))
        else:
            if key == 'set_country_flag' and isinstance(val, list):
                name = model['flag_name'](result, ctx, one(val, 'flag'))
                values = [v for k, o, v in val if k == 'value']
                country['flag_values'][name] = value(result, ctx, values[0]) if values else 1
            source_execute(grouped, result, ctx)

for namespace in (source, source['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute; namespace['value'] = value

for registry, path in (('effects', 'common/scripted_effects/eon_ammo_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_ammo_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, operator, body in ast(read(path))}
        assert not additions.keys() & model[registry].keys(), 'Ammo helpers overwrite an earlier helper'
        model[registry].update(additions)

def state(stock=300000, receiver=0):
    result = source['loader']['state']()
    result['threat'] = 1
    for country in result['countries'].values():
        country.update(allies=set(), subjects=set(), guarantors=set(), government='democratic',
                       overlord=None, co_war_partners=set(), flag_values={}, opinion_modifiers=set())
        country['variables'].update(ammo_stock=0, max_ammo_limit=1010000, num_of_supply_nodes=10,
            political_power=300, ammo_production_rating=0, ammo_stock_days=20, ammo_stock_months=2,
            ammo_stock_years=2, maximum_ammo_consumption=1000)
        country['variables']['modifier@lend_lease_tension'] = .5
    result['countries']['A']['variables']['ammo_stock'] = stock
    result['countries']['B']['variables']['ammo_stock'] = receiver
    result['countries']['B']['wars'].add('C')
    return result

def effect(result, nodes, actor='A', partner='B', temporary=None):
    result['temp'] = dict(temporary or {})
    execute(nodes, result, context(actor, scope=partner))

def stocks(result): return {actor: country['variables']['ammo_stock'] for actor, country in result['countries'].items()}

def send(result, actor='A', partner='B', force=False):
    ctx = context(actor, scope=partner); result['temp'] = {}
    ready = trigger(one(ammo, 'selectable'), result, ctx) and trigger(one(ammo, 'can_be_sent'), result, ctx)
    if ready or force: effect(result, one(ammo, 'on_sent_effect'), actor, partner)
    return ready

def reply(result, accepted=True, actor='A', partner='B'):
    effect(result, one(ammo, 'complete_effect' if accepted else 'reject_effect'), actor, partner)

def vars_(result, actor): return result['countries'][actor]['variables']
def flags(result, actor): return result['countries'][actor]['flags']
def pending(result, actor='A'): return 'eon_ammo_pending' in flags(result, actor)
def held(result, actor='A'): return vars_(result, actor).get('eon_ammo_escrow', 0) + vars_(result, actor).get('eon_ammo_refund_claim', 0)
def assets(result): return sum(vars_(result, actor)['ammo_stock'] + held(result, actor) for actor, data in result['countries'].items() if data['exists'])
def snapshot(result): return {key: deepcopy(val) for key, val in result.items() if key != 'temp'}

def check(result, nodes, actor='A', partner='B'):
    result['temp'] = {}; return trigger(nodes, result, context(actor, scope=partner))

def donor_helper(result, name, actor='A', temporary=None):
    effect(result, [('eon_ammo_' + name, '=', 'yes')], actor, actor, temporary)

def withdraw(result, actor='A', partner='B', force=False):
    body = one(one(ast(read('common/scripted_diplomatic_actions/eon_ammo_actions.txt')), 'scripted_diplomatic_actions'), 'eon_ammo_withdraw_offer')
    ready = all(check(result, one(body, key), actor, partner) for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), actor, partner)
    return ready

def native_hook(result, name, actor='A', from_='B'):
    hooks = one(ast(read('common/on_actions/eon_ammo_on_actions.txt')), 'on_actions')
    result['temp'] = {}; execute(one(one(hooks, name), 'effect'), result, context(actor, from_))

def ai_weight(result, nodes, actor='A', partner='B'):
    result['temp'] = {}; ctx = context(actor, scope=partner)
    if not any(key == 'base' for key, op, val in nodes):
        return sum(ai_weight(result, body, actor, partner) for key, op, body in nodes)
    weight = float(one(nodes, 'base'))
    for key, op, body in nodes:
        if key != 'modifier': continue
        conditions = [row for row in body if row[0] not in ('add', 'factor')]
        if trigger(conditions, result, ctx):
            for field, operator, operand in body:
                if field == 'add': weight += value(result, ctx, operand)
                elif field == 'factor': weight *= value(result, ctx, operand)
    return weight

def unrelated(result):
    return {actor: {'variables': {key: deepcopy(val) for key, val in data['variables'].items()
                                if not key.startswith('eon_ammo_') and key not in ('ammo_stock', 'max_ammo_limit')},
                    'arrays': deepcopy(data['arrays']), 'wars': deepcopy(data['wars']), 'ideas': deepcopy(data['ideas']),
                    'faction': data['faction'], 'opinions': deepcopy(data['opinions']),
                    'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_ammo_', 'Ammo_diplo_'))}}
            for actor, data in result['countries'].items()}

def focus(name):
    result = state(); assert send(result)
    if name == 'send':
        send(result, force=True)
        assert stocks(result)['A'] == 200000, ('Repeated native on_sent must reserve/debit only once', stocks(result))
        groups['actual_native_repeated_send_debit_once'] += 1
    elif name == 'accept':
        reply(result); reply(result)
        assert stocks(result)['B'] == 100000, ('Repeated native acceptance must deliver only once', stocks(result))
        groups['actual_native_repeated_acceptance_delivery_once'] += 1
    elif name == 'reject':
        reply(result, False); reply(result, False)
        assert stocks(result)['A'] == 300000, ('Repeated native rejection must refund only once', stocks(result))
        groups['actual_native_repeated_rejection_refund_once'] += 1
    elif name == 'unknown_partner':
        result['countries']['A']['variables']['eon_ammo_partner'] = 999
        effect(result, [('eon_ammo_daily_cleanup', '=', 'yes')], actor='A', partner='A')
        assert 'eon_ammo_pending' not in result['countries']['A']['flags'], ('Malformed positive noncountry partner cannot retain a native reservation forever', result['countries']['A'])
        assert 'eon_ammo_quarantined' in result['countries']['A']['flags'], ('Unknown native response identity requires donor quarantine', result['countries']['A'])
        assert stocks(result)['A'] == 300000
        groups['malformed_positive_noncountrypartner_refund_and_donor_quarantine'] += 1
    elif name == 'legacy_debounce':
        result = state(); result['countries']['A']['flags'].add('Ammo_diplo_AI_debounce')
        assert not send(result), ('Unidentified legacy pending AI channel cannot be overwritten', result['countries']['A'])
        assert stocks(result)['A'] == 300000
        groups['legacy_AI_debounce_channel_remains_locked_without_inferred_ownership'] += 1
    elif name in ('orphan_escrow', 'orphan_daily', 'orphan_annex'):
        flags(result, 'A').discard('eon_ammo_pending')
        if name == 'orphan_escrow':
            assert not send(result), ('An orphan held escrow cannot be overwritten by a new debit', result['countries']['A'])
            assert stocks(result)['A'] == 200000 and held(result) == 100000
        elif name == 'orphan_daily':
            donor_helper(result, 'daily_cleanup')
            assert stocks(result)['A'] == 300000 and held(result) == 0, ('Daily repair must retain/refund actual orphan escrow once', result['countries']['A'])
            assert 'eon_ammo_quarantined' in flags(result, 'A')
        else:
            result['countries']['A']['exists'] = False
            donor_helper(result, 'transfer_annexed_assets', temporary={'eon_ammo_successor': 'C'})
            assert vars_(result, 'C').get('eon_ammo_refund_claim', 0) == 100000, ('Annex cleanup must preserve orphan held ownership', result['countries'])
            assert stocks(result)['A'] == 200000 and stocks(result)['C'] == 0
        groups['actual_' + name + '_held_ownership_is_not_erased_or_overwritten'] += 1
    else: raise AssertionError(('Unknown focus', name))

# ROOT must observe these actual-source REDs before production is changed.
arguments = sys.argv[1:]
if arguments:
    assert len(arguments) == 2 and arguments[0] == '--focus', arguments
    focus(arguments[1])
else:
    for name in ('send', 'accept', 'reject', 'unknown_partner', 'legacy_debounce', 'orphan_escrow', 'orphan_daily', 'orphan_annex'): focus(name)

    # Exact fixed quantity and fresh physical storage, independently of stale cache.
    for stock in (99999, 99999.99, 100000, 100001):
        result = state(stock); ready = stock >= 100000
        assert send(result) == ready
        assert stocks(result)['A'] == stock - (100000 if ready else 0)
        assert held(result) == (100000 if ready else 0)
        if ready:
            assert check(result, one(ammo, 'selectable'))  # Its own modal remains reachable after the debit.
            reply(result); assert stocks(result)['B'] == 100000 and not pending(result)
        groups['fixed_donor_stock_boundary_and_own_pending_modal_reachable_after_debit'] += 1
    for receiver in (909999.99, 910000, 910000.01, 1010000):
        result = state(receiver=receiver); vars_(result, 'B')['max_ammo_limit'] = 999999999
        before = assets(result); ready = receiver + 100000 <= 1010000
        assert send(result) == ready
        if ready: reply(result); assert vars_(result, 'B')['max_ammo_limit'] == 1010000
        else: send(result, force=True)
        assert assets(result) == before
        assert stocks(result)['B'] == receiver + (100000 if ready else 0)
        groups['fresh_supply_node_capacity_exact_room_and_stale_cache_cannot_bypass'] += 1
    for nodes, receiver, wanted, capacity in ((0, 0, False, 10000), (1, 0, True, 110000),
                                            (1, 10000, True, 110000), (1, 10000.01, False, 110000),
                                            (20000, 999900000, True, 1000000000)):
        result = state(receiver=receiver); vars_(result, 'B')['num_of_supply_nodes'] = nodes
        assert send(result) == wanted
        assert result['temp']['eon_ammo_capacity'] == capacity
        if wanted: reply(result); assert vars_(result, 'B')['max_ammo_limit'] == capacity
        groups['native_physical_capacity_base_supply_nodes_and_billion_maximum'] += 1

    for change in ('peace', 'enemy', 'donor dead', 'recipient dead', 'same country', 'tension equal', 'tension low', 'ally tension low'):
        result = state(); actor, peer = 'A', 'B'; wanted = False
        if change == 'peace': result['countries']['B']['wars'].clear()
        elif change == 'enemy': result['countries']['B']['wars'].add('A')
        elif change == 'donor dead': result['countries']['A']['exists'] = False
        elif change == 'recipient dead': result['countries']['B']['exists'] = False
        elif change == 'same country': peer = 'A'; result['countries']['A']['wars'].add('C')
        elif change == 'tension equal': result['threat'] = .5
        elif change == 'tension low': result['threat'] = .49999
        else: result['countries']['B']['allies'].add('A'); result['threat'] = 0; wanted = True
        before = stocks(result); assert send(result, actor, peer) == wanted
        if not wanted:
            send(result, actor, peer, True); assert stocks(result) == before and not pending(result)
        groups['fresh_original_war_ally_tension_existence_and_distinct_country_policy'] += 1
    for maximum, tension, wanted in ((-1, 0, False), (-1, .01, True), (2, 1, False)):
        result = state(); result['threat'] = tension; vars_(result, 'A')['modifier@lend_lease_tension'] = maximum
        assert send(result) == wanted
        groups['native_lend_lease_modifier_clamps_zero_to_one_with_strict_tension_comparison'] += 1

    result = state(); assert send(result); before = snapshot(result)
    assert not send(result, 'A', 'C'); send(result, 'A', 'C', True)
    assert snapshot(result) == before
    for accepted in (True, False):
        reply(result, accepted, 'A', 'C'); assert snapshot(result) == before
        groups['different_partner_response_and_forced_sender_replay_preserve_original_record'] += 1
    vars_(result, 'D')['ammo_stock'] = 300000
    assert send(result, 'D', 'B') and pending(result, 'D') and pending(result, 'A')
    reply(result, actor='D'); assert stocks(result)['B'] == 100000 and pending(result, 'A')
    reply(result); assert stocks(result)['B'] == 200000 and not pending(result, 'A')
    groups['independent_donors_can_supply_one_receiver_without_shared_recipient_reservation'] += 1
    result = state(); result['countries']['D']['wars'].add('C'); vars_(result, 'B')['ammo_stock'] = 300000
    assert send(result) and send(result, 'B', 'D')
    reply(result); reply(result, actor='B', partner='D')
    assert stocks(result)['A'] == 200000 and stocks(result)['B'] == 300000 and stocks(result)['D'] == 100000
    groups['receiving_a_proposal_does_not_block_own_independent_outgoing_donation'] += 1

    for changed in ('war ends', 'becomes enemy', 'donor dead', 'recipient dead', 'tension falls', 'capacity lost', 'stock filled', 'expired', 'escrow changed'):
        for accepted in (True, False):
            result = state(); assert send(result)
            if changed == 'war ends': result['countries']['B']['wars'].clear()
            elif changed == 'becomes enemy': result['countries']['B']['wars'].add('A')
            elif changed == 'donor dead': result['countries']['A']['exists'] = False
            elif changed == 'recipient dead': result['countries']['B']['exists'] = False
            elif changed == 'tension falls': result['threat'] = .5
            elif changed == 'capacity lost': vars_(result, 'B')['num_of_supply_nodes'] = 0
            elif changed == 'stock filled': vars_(result, 'B')['ammo_stock'] = 1010000
            elif changed == 'expired': flags(result, 'A').discard('eon_ammo_live')
            else: vars_(result, 'A')['eon_ammo_escrow'] = 90000
            assert check(result, one(ammo, 'selectable'))  # Own response remains resolvable.
            assert not check(result, one(ammo, 'can_be_accepted'))
            before_stock = stocks(result)['B']; owned = held(result)
            reply(result, accepted)
            assert stocks(result)['B'] == before_stock and not pending(result)
            assert not result['countries']['B']['opinion_modifiers']
            assert 'Ammo_diplo_rejections' not in flags(result, 'B')
            if changed == 'donor dead': assert held(result) == owned and stocks(result)['A'] == 200000
            else: assert held(result) == 0 and stocks(result)['A'] == 200000 + owned
            assert 'eon_ammo_retired_pair@B' not in flags(result, 'A')
            before = snapshot(result); reply(result, accepted); assert snapshot(result) == before
            groups['matching_consumed_invalid_reply_refunds_only_actual_held_ammo_without_refusal_reward'] += 1

    for callback in (True, False):
        result = state(); assert send(result); assert withdraw(result)
        assert stocks(result)['A'] == 300000 and held(result) == 0 and pending(result)
        assert 'eon_ammo_cancelled' in flags(result, 'A') and check(result, one(ammo, 'selectable'))
        assert not check(result, one(ammo, 'can_be_accepted'))
        before = snapshot(result); assert not withdraw(result); withdraw(result, force=True)
        assert snapshot(result) == before
        assert not send(result, 'A', 'C')
        reply(result, callback)
        assert not pending(result) and stocks(result)['B'] == 0
        assert 'Ammo_diplo_rejections' not in flags(result, 'B')
        assert not any(flag.startswith('eon_ammo_retired_pair@') for flag in flags(result, 'A'))
        assert send(result)
        groups['free_sender_withdrawal_retains_identity_until_original_response_then_allows_new_round'] += 1
    result = state(); assert send(result); before = snapshot(result)
    assert not withdraw(result, 'B', 'A'); withdraw(result, 'B', 'A', True); assert snapshot(result) == before
    assert not withdraw(result, 'A', 'C'); withdraw(result, 'A', 'C', True); assert snapshot(result) == before
    groups['recipient_and_wrong_peer_cannot_withdraw_another_donors_record'] += 1

    for change in ('expiry', 'recipient absent'):
        result = state(); assert send(result)
        if change == 'expiry': flags(result, 'A').discard('eon_ammo_live')
        else: result['countries']['B']['exists'] = False
        native_hook(result, 'on_daily', 'A')
        assert not pending(result) and stocks(result)['A'] == 300000
        assert 'eon_ammo_retired_pair@B' in flags(result, 'A') and 'eon_ammo_quarantined' not in flags(result, 'A')
        result['countries']['B']['exists'] = True
        assert not send(result)
        result['countries']['C']['wars'].add('D'); assert send(result, 'A', 'C')
        before = snapshot(result); reply(result, actor='A', partner='B'); reply(result, False, 'A', 'B')
        assert snapshot(result) == before
        groups['forced_expiry_or_absence_retires_only_known_directed_pair_and_old_callback_is_inert'] += 1
    for partner in (0, 999):
        result = state(); assert send(result); vars_(result, 'A')['eon_ammo_partner'] = partner
        native_hook(result, 'on_daily', 'A')
        assert stocks(result)['A'] == 300000 and not pending(result)
        assert 'eon_ammo_quarantined' in flags(result, 'A')
        result['countries']['C']['wars'].add('D'); assert not send(result, 'A', 'C')
        donor_helper(result, 'daily_cleanup'); assert stocks(result)['A'] == 300000
        groups['unidentified_partner_refunds_actual_escrow_once_and_blocks_donor_channel_fail_closed'] += 1

    for current, nodes, credit, claim in ((1000000, 10, 10000, 90000), (1010000, 10, 0, 100000),
                                        (1500000, 0, 0, 100000), (910000, 10, 100000, 0)):
        result = state(); assert send(result); vars_(result, 'A')['ammo_stock'] = current
        vars_(result, 'A')['num_of_supply_nodes'] = nodes
        reply(result, False)
        assert stocks(result)['A'] == current + credit
        assert vars_(result, 'A').get('eon_ammo_refund_claim', 0) == claim
        assert stocks(result)['A'] + held(result) == current + 100000
        before = snapshot(result); reply(result, False); assert snapshot(result) == before
        if claim:
            vars_(result, 'A')['num_of_supply_nodes'] = 20
            donor_helper(result, 'release_refund')
            assert stocks(result)['A'] == current + 100000 and held(result) == 0
        groups['capped_partial_full_or_overcapacity_refund_keeps_uncredited_claim_without_trimming_ordinary_stock'] += 1
    result = state(); assert send(result); result['countries']['A']['exists'] = False
    reply(result, False); assert stocks(result)['A'] == 200000 and held(result) == 100000
    result['countries']['A']['exists'] = True; native_hook(result, 'on_daily', 'A')
    assert stocks(result)['A'] == 300000 and held(result) == 0
    groups['dead_donor_known_refund_claim_waits_for_existence_and_pays_on_revival'] += 1

    # Annex callbacks queue claims only; actual ordinary native subject inheritance
    # executes independently before/after them, exactly once in each fixture.
    ordinary = one(one(ast(read('common/on_actions/00_ammo_on_actions.txt')), 'on_actions'), 'on_subject_annexed')
    for victim in ('A', 'B'):
        for hook in ('on_annex', 'on_subject_annexed'):
            for before_native in (False, True):
                result = state(); assert send(result)
                successor = 'D' if victim == 'A' else 'A'
                if victim == 'B': vars_(result, 'B')['ammo_stock'] = 900000
                if victim == 'A': vars_(result, 'A')['eon_ammo_refund_claim'] = 25000
                result['countries'][victim]['exists'] = False
                def ordinary_transfer():
                    result['temp'] = {}; execute(one(ordinary, 'effect'), result, context(victim, successor))
                def new_hook():
                    actor, from_ = (successor, victim) if hook == 'on_annex' else (victim, successor)
                    native_hook(result, hook, actor, from_)
                if before_native: ordinary_transfer()
                new_hook()
                if not before_native: ordinary_transfer()
                expected_claim = 125000 if victim == 'A' else 100000
                assert vars_(result, successor).get('eon_ammo_refund_claim', 0) == expected_claim
                assert not pending(result) and held(result, victim) == 0
                assert 'eon_ammo_retired_pair@B' in flags(result, 'A')
                physical = stocks(result)[successor]; before = snapshot(result); new_hook(); assert snapshot(result) == before
                assert stocks(result)[successor] == physical
                if victim == 'B': assert physical == 1010000  # Ordinary inherited ammo receives native storage priority.
                else: assert physical == 200000
                native_hook(result, 'on_daily', successor)
                if victim == 'B': assert vars_(result, successor)['eon_ammo_refund_claim'] == 100000
                else: assert stocks(result)[successor] == 325000 and held(result, successor) == 0
                result['countries'][victim]['exists'] = True
                assert not send(result)
                groups['both_native_annex_roles_and_hook_orders_preserve_ordinary_inheritance_and_transfer_held_ownership_once'] += 1

    for ai in (False, True):
        result = state(); result['countries']['A']['ai'] = True; result['countries']['B']['ai'] = ai
        assert send(result)
        assert ('Ammo_diplo_AI_debounce' in flags(result, 'A')) == (not ai)
        reply(result, False); assert 'Ammo_diplo_AI_debounce' not in flags(result, 'A')
        assert ('Ammo_diplo_rejections' in flags(result, 'B')) == (not ai)
        if not ai:
            assert result['countries']['B']['flag_values']['Ammo_diplo_rejections'] == 1
            assert ('B', 'Ammo_diplo_rejections', 90) in result['timer_declarations']
        groups['original_AI_to_human_debounce_and_current_human_refusal_counter_once'] += 1
    result = state(); flags(result, 'B').add('Ammo_diplo_rejections'); result['countries']['B']['flag_values']['Ammo_diplo_rejections'] = 4
    assert send(result); reply(result, False); reply(result, False)
    assert result['countries']['B']['flag_values']['Ammo_diplo_rejections'] == 5
    groups['current_refusal_increments_existing_native_90_day_value_once_without_replay'] += 1
    for accepted in (False, True):
        result = state(); flags(result, 'A').add('Ammo_diplo_AI_debounce'); before = snapshot(result)
        reply(result, accepted)
        assert snapshot(result) == before
        groups['legacy_unsigned_callbacks_do_not_infer_delivery_refund_or_clear_unowned_AI_flag'] += 1

    for rating, days, expected in ((0, 20, 110), (1, 7, -100), (1, 8, 110), (-1, 1, 110)):
        result = state(); vars_(result, 'B').update(ammo_production_rating=rating, ammo_stock_days=days)
        assert ai_weight(result, one(ammo, 'ai_acceptance')) == expected
        groups['actual_native_acceptance_unchanged_ordered_production_days_weights'] += 1
    for counter, rating, months, expected in ((4, 1, 2, -1), (5, 1, 2, -20001), (5, 0, 1, -1)):
        result = state(); flags(result, 'B').add('Ammo_diplo_rejections'); result['countries']['B']['flag_values']['Ammo_diplo_rejections'] = counter
        vars_(result, 'B').update(ammo_production_rating=rating, ammo_stock_months=months)
        assert ai_weight(result, one(ammo, 'ai_desire')) == expected
        groups['actual_native_AI_repeated_human_refusal_value_is_soft_weight_only'] += 1
    result = state(); flags(result, 'A').add('Ammo_diplo_AI_debounce')
    desire = one(ammo, 'ai_desire')
    technical_guard = ('modifier', '=', [('add', '=', '-20000'), ('NOT', '=', [('eon_ammo_gui_ready', '=', 'yes')])])
    assert desire.count(technical_guard) == 1
    assert ai_weight(result, [row for row in desire if row != technical_guard]) == -20001
    assert ai_weight(result, desire) == -40001
    groups['actual_native_AI_donor_debounce_weight_preserved_plus_explicit_technical_admission_guard'] += 1

    events = model['get_event_map'](read('events/eon_ammo_events.txt'))
    for identity, body in events.items():
        result = state(); assert send(result); before = snapshot(result)
        choices = [val for key, op, val in body if key == 'option']; assert len(choices) == 1
        effect(result, choices[0]); assert snapshot(result) == before
        groups['all_static_ammunition_ACKs_are_inert_during_another_current_proposal'] += 1
    result = state(); before = unrelated(result); assert send(result); reply(result)
    assert unrelated(result) == before and stocks(result)['A'] == 200000 and stocks(result)['B'] == 100000
    assert result['countries']['B']['opinion_modifiers'] == {('A', 'Sent_ammo')}
    assert sum(key == 'add_opinion_modifier' for actor, key, item in result['opinion_calls']) == 1
    assert ('A', 'eon_ammo_live', 30) in result['timer_declarations']
    groups['one_success_preserves_economy_wars_other_diplomatic_arrays_and_declares_exact_30_day_window'] += 1

    # A trigger can invoke the same documented rounding primitive as an effect;
    # explicit non-tie values avoid any undocumented half-way tie assumption.
    result = state(); before = deepcopy(result['countries'])
    for initial, expected in ((2.25, 2), (-2.25, -2)):
        result['temp'] = {'fixture_round': initial}
        assert trigger([('round_temp_variable', '=', 'fixture_round')], result, context('A'))
        assert result['temp']['fixture_round'] == expected
    assert result['countries'] == before
    adapter_cases['documented_round_temp_variable_in_trigger_context_non_tie_values'] += 1

print(json.dumps({'all_passed': True, 'baseline': BASELINE,
    'actual_source_scenarios': sum(groups.values()), 'adapter_semantics_cases': sum(adapter_cases.values()),
    'total_cases': sum(groups.values()) + sum(adapter_cases.values()), 'groups': dict(groups),
    'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (ACTION_PATH,
        'common/scripted_effects/eon_ammo_effects.txt', 'common/scripted_triggers/eon_ammo_triggers.txt',
        'common/scripted_diplomatic_actions/eon_ammo_actions.txt', 'common/on_actions/eon_ammo_on_actions.txt',
        'events/eon_ammo_events.txt', 'localisation/english/MDC_ammo_l_english.yml',
        'localisation/russian/MDC_ammo_l_russian.yml', 'localisation/english/eon_ammo_l_english.yml',
        'localisation/russian/eon_ammo_l_russian.yml')},
    'proof_scope': 'bounded ordered actual-source ammunition transfer; not HOI4 runtime'}, indent=2))
