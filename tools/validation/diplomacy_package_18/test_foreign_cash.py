"""Ordered actual-source foreign cash consent; not native HOI4 runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '0a8063bf3bc732fbc7ab453b116ddf61e5c090d4'
groups = Counter()
adapter_cases = Counter()

# Load definitions only; every preceding suite remains separately counted.
executor_path = ROOT / 'tools/validation/diplomacy_package_17/test_services.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'foreign_cash_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
read, option, effect, cash, check, context, switch, one = (source[name] for name in ('read', 'option', 'effect', 'cash', 'check', 'context', 'switch', 'one'))
source_trigger, source_execute, source_state = source['trigger'], source['execute'], source['state']

def trigger(nodes, result, ctx):
    # Defensive-war classification is an explicit fixture, not inferred from a
    # generic war set or claimed as native engine classification.
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'has_defensive_war': passed = result['countries'][ctx['scope']]['defensive_war'] == (val == 'yes')
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
        if key == 'change_influence_percentage':
            result.setdefault('foreign_cash_political_contexts', []).append(
                {'root': ctx['root'], 'from': ctx['from'], 'scope': ctx['scope']})
        source_execute(grouped, result, ctx)

for namespace in (source, source['source'], source['source']['source'], source['source']['source']['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute
for registry, path in (('effects', 'common/scripted_effects/eon_foreign_cash_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_foreign_cash_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, op, body in source['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Foreign cash overwrites an earlier helper'
        model[registry].update(additions)

def state(payer=100, provider=100):
    result = source_state(payer=payer, provider=provider)
    for country in result['countries'].values():
        country['defensive_war'] = True
        country['opinions'] = {actor: 60 for actor in result['countries']}
        country['ideas'].update({'large_power', 'minor_power'})
        country['flags'].update('aid_request_cd_@' + actor for actor in result['countries'])
    return result

def cash_option():
    return option(model['get_event_map'](read('events/00_War_events.txt')), 'AB_mobilization.4', 'AB_mobilization.4.c')

def old_callback(result):
    effect(result, cash_option(), actor='A', from_='B')

def focus(name):
    if name == 'legacy_insufficient':
        result = state(payer=0, provider=1); before = cash(result)
        old_callback(result)
        assert cash(result) == before, ('An insolvent donor must not debit or credit unsigned cash aid', before, cash(result))
        groups['unsigned_insolvent_donor_no_transfer'] += 1
    elif name == 'legacy_replay':
        result = state(payer=0, provider=100)
        old_callback(result); first = cash(result)
        old_callback(result)
        assert cash(result) == first, ('Replayed cash option must not transfer a second gift', first, cash(result))
        groups['unsigned_cash_callback_replay_does_not_repeat_transfer'] += 1
    elif name == 'legacy_credit_loss':
        result = state(payer=999999, provider=100); before = cash(result)
        old_callback(result)
        assert sum(cash(result).values()) == sum(before.values()), ('Recipient cap must not destroy part of the gift', before, cash(result))
        groups['recipient_credit_capacity_preserves_entire_gift'] += 1
    else: raise AssertionError(('Unknown focus', name))

def flags(result, actor='A'): return result['countries'][actor]['flags']
def vars_(result, actor='A'): return result['countries'][actor]['variables']
def pending(result, actor='A'): return 'eon_foreign_cash_pending' in flags(result, actor)
def consented(result, actor='A'): return 'eon_foreign_cash_consented' in flags(result, actor)
def snapshot(result): return {key: deepcopy(val) for key, val in result.items() if key not in ('temp', 'scope_temps')}

def send(result, provider='A', receiver='B', force=False):
    body = cash_option()
    ready = check(result, one(body, 'trigger'), actor=provider, from_=receiver)
    if ready or force: effect(result, body, actor=provider, from_=receiver)
    return ready

def reply(result, provider='A', receiver='B', accepted=True, force=False):
    events = model['get_event_map'](read('events/eon_foreign_cash_events.txt'))
    body = option(events, 'eon_foreign_cash.1', 'eon_foreign_cash.1.' + ('a' if accepted else 'b'))
    guards = [value for key, operator, value in body if key == 'trigger']
    ready = not guards or check(result, guards[0], actor=receiver, from_=provider)
    if ready or force: effect(result, body, actor=receiver, from_=provider)
    return ready

def commit(result, provider='A', receiver='B'):
    events = model['get_event_map'](read('events/eon_foreign_cash_events.txt'))
    effect(result, one(events['eon_foreign_cash.2'], 'immediate'), actor=provider, from_=receiver)

def queued(result, identity): return [item for item in result['events'] if item['id'] == identity]

def action(result, actor='A', partner='B', force=False):
    actions = one(source['ast'](read('common/scripted_diplomatic_actions/eon_foreign_cash_actions.txt')), 'scripted_diplomatic_actions')
    body = one(actions, 'eon_foreign_cash_withdraw_offer')
    ready = all(check(result, one(body, key), actor=actor, from_=None, scope=partner)
                for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), actor=actor, from_=None, scope=partner)
    return ready

def native_hook(result, name, actor='A', from_='B'):
    hooks = one(source['ast'](read('common/on_actions/eon_foreign_cash_on_actions.txt')), 'on_actions')
    effect(result, one(one(hooks, name), 'effect'), actor=actor, from_=from_)

def daily(result):
    for actor, country in result['countries'].items():
        if country['exists']: native_hook(result, 'on_daily', actor, None)

def unrelated(result):
    return {actor: {key: deepcopy(val) for key, val in country.items() if key not in ('variables', 'flags', 'flag_values')}
            | {'variables': {key: deepcopy(val) for key, val in country['variables'].items()
                             if key != 'treasury' and not key.startswith('eon_foreign_cash_')},
               'flags': {flag for flag in country['flags'] if not flag.startswith('eon_foreign_cash_')},
               'flag_values': {flag: val for flag, val in country['flag_values'].items() if not flag.startswith('eon_foreign_cash_')}}
            for actor, country in result['countries'].items()}

def alteration(result, name):
    provider, receiver = result['countries']['A'], result['countries']['B']
    if name == 'donor_insolvent': provider['variables']['treasury'] = 6.999
    elif name == 'donor_above_cap': provider['variables']['treasury'] = 1000000.001
    elif name == 'receiver_above_cap': receiver['variables']['treasury'] = 999993.001
    elif name == 'receiver_below_floor': receiver['variables']['treasury'] = -1000000.001
    elif name == 'donor_rank': provider['ideas'] -= {'large_power', 'great_power', 'superpower'}
    elif name == 'receiver_rank': receiver['ideas'] -= {'non_power', 'minor_power', 'regional_power'}
    elif name == 'defensive_war_lost': receiver['defensive_war'] = False
    elif name == 'request_timer_lost': provider['flags'].discard('aid_request_cd_@B')
    elif name == 'opinion_lost': provider['opinions']['B'] = 49
    elif name == 'direct_war': provider['wars'].add('B'); receiver['wars'].add('A')
    elif name == 'donor_annexed': provider['exists'] = False
    elif name == 'receiver_annexed': receiver['exists'] = False
    elif name == 'live_expired': provider['flags'].discard('eon_foreign_cash_live')
    elif name == 'cancelled': provider['flags'].add('eon_foreign_cash_cancelled')
    else: raise AssertionError(('Unknown alteration', name))

def scenarios():
    for name in ('legacy_insufficient', 'legacy_replay', 'legacy_credit_loss'): focus(name)
    for provider_cash, receiver_cash in ((7, 0), (100, 999993), (1000000, -1000000), (100, -25)):
        result = state(payer=receiver_cash, provider=provider_cash)
        before = cash(result); other = unrelated(result)
        assert send(result)
        assert cash(result) == before and unrelated(result) == other and pending(result) and not consented(result)
        assert vars_(result)['eon_foreign_cash_partner'] == 'B'
        assert queued(result, 'eon_foreign_cash.1') == [{'target': 'B', 'id': 'eon_foreign_cash.1', 'from': 'A'}]
        assert ('A', 'eon_foreign_cash_live', 30) in result['timer_declarations']
        assert reply(result)
        assert cash(result) == before and unrelated(result) == other and pending(result) and consented(result)
        assert not result.get('political_macro_calls')
        assert queued(result, 'eon_foreign_cash.2') == [{'target': 'A', 'id': 'eon_foreign_cash.2', 'from': 'B'}]
        groups['four_boundary_valid_offers_and_explicit_consent_are_unfunded_until_provider_commit'] += 1
        waiting = snapshot(result)
        assert not reply(result, force=True) and not reply(result, accepted=False, force=True)
        assert not action(result, force=True) and snapshot(result) == waiting
        assert len(queued(result, 'eon_foreign_cash.2')) == 1
        groups['consented_pair_accept_decline_and_withdraw_callbacks_cannot_queue_again_or_cancel_commit'] += 1
        commit(result)
        assert cash(result)['A'] == provider_cash - 7 and cash(result)['B'] == receiver_cash + 7
        assert sum(cash(result).values()) == sum(before.values()) and unrelated(result) == other
        assert not pending(result) and not consented(result) and not vars_(result).get('eon_foreign_cash_partner')
        calls = [call for call in result.get('political_macro_calls', []) if call[1] == 'change_influence_percentage']
        assert len(calls) == 1 and calls[0][0] == 'A'
        assert calls[0][3]['percent_change'] == 3 and calls[0][3]['tag_index'] == 'A' and calls[0][3]['influence_target'] == 'B'
        assert result['foreign_cash_political_contexts'] == [{'root': 'A', 'from': 'B', 'scope': 'A'}]
        assert {'target': 'B', 'id': 'AB_mobilization.7', 'from': 'A'} in result['events']
        groups['four_exact_seven_unit_gifts_original_plus_three_macro_scope_and_AB7_only_after_commit'] += 1
        settled = snapshot(result); commit(result); reply(result, force=True); reply(result, accepted=False, force=True)
        assert snapshot(result) == settled
        groups['both_reply_and_provider_commit_replay_inert_after_consumption'] += 1

    invalid = ('donor_insolvent', 'donor_above_cap', 'receiver_above_cap', 'receiver_below_floor',
               'donor_rank', 'receiver_rank', 'defensive_war_lost', 'request_timer_lost', 'opinion_lost',
               'direct_war', 'donor_annexed', 'receiver_annexed')
    for name in invalid:
        result = state(); alteration(result, name); before = snapshot(result)
        assert not send(result, force=True) and snapshot(result) == before
        groups['fresh_invalid_offer_does_not_reserve_pay_or_create_political_effects'] += 1
    for stage in ('response', 'commit'):
        for name in invalid + ('live_expired', 'cancelled'):
            result = state(); assert send(result)
            if stage == 'commit': assert reply(result)
            alteration(result, name); before = cash(result); other = unrelated(result)
            if stage == 'response': reply(result, force=True)
            else: commit(result)
            assert cash(result) == before and unrelated(result) == other and not result.get('political_macro_calls')
            assert not pending(result) and not consented(result)
            groups['fresh_policy_and_full_money_rechecked_at_' + stage + '_invalid_pair_closes_unpaid'] += 1

    result = state(); assert send(result); before = snapshot(result)
    send(result, force=True); send(result, receiver='D', force=True)
    assert snapshot(result) == before and pending(result) and vars_(result)['eon_foreign_cash_partner'] == 'B'
    groups['forced_same_or_other_recipient_send_preserves_one_frozen_provider_pair'] += 1
    for stage in ('response', 'commit'):
        for provider, receiver in (('C', 'B'), ('A', 'D'), ('A', 'A')):
            result = state(); assert send(result)
            if stage == 'commit': assert reply(result)
            before = snapshot(result)
            if stage == 'response': reply(result, provider=provider, receiver=receiver, force=True); reply(result, provider=provider, receiver=receiver, accepted=False, force=True)
            else: commit(result, provider=provider, receiver=receiver)
            assert snapshot(result) == before
            groups['wrong_pair_' + stage + '_callbacks_cannot_touch_frozen_pending_money_or_consent'] += 1
    result = state(); assert send(result); before = snapshot(result); commit(result)
    assert snapshot(result) == before
    groups['hidden_commit_without_explicit_recipient_consent_is_inert'] += 1
    result = state(); assert send(result); before = cash(result); assert reply(result, accepted=False)
    assert not pending(result) and not consented(result) and cash(result) == before and not result.get('political_macro_calls')
    settled = snapshot(result); reply(result, force=True); reply(result, accepted=False, force=True); commit(result)
    assert snapshot(result) == settled
    groups['recipient_decline_consumes_unpaid_record_and_all_replays_are_inert'] += 1
    result = state(); assert send(result); assert reply(result, accepted=False); assert send(result, receiver='D')
    before = snapshot(result); reply(result, force=True); reply(result, accepted=False, force=True); commit(result)
    assert snapshot(result) == before and pending(result) and vars_(result)['eon_foreign_cash_partner'] == 'D'
    groups['consumed_old_partner_accept_decline_commit_preserve_later_other_partner_offer'] += 1
    result = state(); assert send(result); before = cash(result); assert action(result)
    assert pending(result) and 'eon_foreign_cash_cancelled' in flags(result) and cash(result) == before
    assert not action(result, force=True) and not reply(result, force=True)
    assert not pending(result) and not consented(result) and cash(result) == before
    groups['free_native_withdraw_keeps_identity_until_old_recipient_reply_closes_without_payment'] += 1
    for actor, partner in (('C', 'B'), ('A', 'D'), ('B', 'A')):
        result = state(); assert send(result); before = snapshot(result)
        assert not action(result, actor=actor, partner=partner, force=True) and snapshot(result) == before
        groups['wrong_actor_or_target_native_withdraw_is_inert'] += 1

    for consent in (False, True):
        for name in ('live_expired', 'receiver_annexed'):
            result = state(); assert send(result)
            if consent: assert reply(result)
            alteration(result, name); before = cash(result); other = unrelated(result)
            daily(result)
            assert not pending(result) and not consented(result) and cash(result) == before and unrelated(result) == other
            settled = snapshot(result); reply(result, force=True); commit(result)
            assert snapshot(result) == settled
            groups['daily_known_invalid_' + ('consented' if consent else 'offered') + '_pair_retires_unpaid_and_stale_callbacks_inert'] += 1

    for hook in ('on_annex', 'on_subject_annexed'):
        for winner, victim in (('C', 'A'), ('C', 'B'), ('A', 'B'), ('B', 'A')):
            for consent in (False, True):
                for disappeared in (False, True):
                    result = state(); assert send(result)
                    if consent: assert reply(result)
                    if disappeared: result['countries'][victim]['exists'] = False
                    before = cash(result); other = unrelated(result)
                    native_hook(result, hook, winner if hook == 'on_annex' else victim,
                                victim if hook == 'on_annex' else winner)
                    assert not pending(result) and not consented(result) and cash(result) == before and unrelated(result) == other
                    closed = snapshot(result); reply(result, force=True); commit(result)
                    assert snapshot(result) == closed
                    groups['both_annex_hooks_clear_known_offered_or_consented_provider_and_receiver_before_or_after_fixture_disappears'] += 1

    for consent in (False, True):
        for name in ('donor_insolvent', 'receiver_above_cap', 'direct_war', 'defensive_war_lost'):
            result = state(); assert send(result)
            if consent: assert reply(result)
            alteration(result, name); before = snapshot(result); daily(result)
            assert snapshot(result) == before and pending(result) and consented(result) == consent
            if consent: commit(result)
            else: reply(result, force=True)
            assert not pending(result) and not consented(result) and cash(result) == {actor: country['variables']['treasury'] for actor, country in before['countries'].items()}
            groups['daily_transient_policy_or_funds_change_preserves_identity_until_fresh_unpaid_close'] += 1

    result = state(); assert send(result); flags(result).discard('eon_foreign_cash_live'); daily(result)
    assert 'eon_foreign_cash_retired_pair@B' in flags(result) and not pending(result)
    before = snapshot(result); assert not send(result, force=True) and snapshot(result) == before
    assert send(result, receiver='D')
    groups['expired_known_pair_permanently_retired_without_blocking_another_partner'] += 1
    result = state(); assert send(result); vars_(result)['eon_foreign_cash_partner'] = 999
    before = cash(result); daily(result)
    assert 'eon_foreign_cash_quarantined' in flags(result) and not pending(result) and not consented(result) and cash(result) == before
    before = snapshot(result); assert not send(result, receiver='D', force=True) and snapshot(result) == before
    groups['unknown_partner_quarantines_only_provider_cash_channel_without_guessing_identity'] += 1

    for malformed in ('live', 'cancelled', 'consented', 'partner', 'pending_without_partner', 'pending_self', 'pending_unknown'):
        result = state()
        if malformed in ('live', 'cancelled', 'consented'): flags(result).add('eon_foreign_cash_' + malformed)
        elif malformed == 'partner': vars_(result)['eon_foreign_cash_partner'] = 'B'
        else:
            flags(result).add('eon_foreign_cash_pending')
            if malformed == 'pending_self': vars_(result)['eon_foreign_cash_partner'] = 'A'
            elif malformed == 'pending_unknown': vars_(result)['eon_foreign_cash_partner'] = 999
        before = cash(result); other = unrelated(result); daily(result)
        assert 'eon_foreign_cash_quarantined' in flags(result) and not pending(result) and not consented(result)
        assert not vars_(result).get('eon_foreign_cash_partner') and cash(result) == before and unrelated(result) == other
        before = snapshot(result); send(result, force=True); reply(result, force=True); commit(result)
        assert snapshot(result) == before
        groups['seven_unowned_or_malformed_records_quarantine_cash_channel_without_resource_or_other_policy_mutations'] += 1

    # The native declaration says defensive war, not simply any current war.
    # These fixture facts are separate adapter checks, not gameplay scenarios.
    for defensive in (False, True):
        for at_war in (False, True):
            result = state(); result['countries']['B']['defensive_war'] = defensive
            result['countries']['B']['wars'] = {'C'} if at_war else set()
            assert check(result, [('has_defensive_war', '=', 'yes')], actor='B') == defensive
            adapter_cases['explicit_defensive_war_fixture_independent_of_generic_war_set'] += 1

def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--focus': focus(sys.argv[2])
    else:
        assert len(sys.argv) == 1, 'Unknown arguments'
        scenarios()
    paths = ['events/00_War_events.txt', 'common/scripted_effects/eon_foreign_cash_effects.txt',
             'common/scripted_triggers/eon_foreign_cash_triggers.txt', 'common/scripted_diplomatic_actions/eon_foreign_cash_actions.txt',
             'common/on_actions/eon_foreign_cash_on_actions.txt', 'events/eon_foreign_cash_events.txt',
             'localisation/english/eon_foreign_cash_l_english.yml', 'localisation/russian/eon_foreign_cash_l_russian.yml']
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths if (ROOT / path).exists()}
    print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'groups': dict(groups),
                      'adapter_semantics_cases': sum(adapter_cases.values()), 'adapter_groups': dict(adapter_cases),
                      'source_sha256': hashes, 'native_runtime': False,
                      'proof_scope': 'ordered current-source cash consent, provider commit and bounded lifecycle; not HOI4 runtime'}, indent=2))

if __name__ == '__main__':
    main()
