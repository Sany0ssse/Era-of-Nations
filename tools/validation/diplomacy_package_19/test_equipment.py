"""Observe current-source equipment dispatch calls; not native shipment completion."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import json
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'd17ccfb5c86ecb9f9ad9fff96894ffcf32e19ff0'
groups = Counter()
adapter_cases = Counter()
PACKETS = {'medium_tank_amphibious_chassis': 250, 'medium_tank_flame_chassis': 250,
           'util_vehicle_equipment': 250, 'AA_Equipment': 250, 'L_AT_Equipment': 250,
           'Inf_equipment': 1000, 'small_plane_suicide_airframe': 100,
           'guided_missile_equipment': 100, 'ballistic_missile_equipment': 100}
SUFFIXES = dict(zip(PACKETS, ('apc', 'ifv', 'utility', 'manpads', 'atgm', 'small_arms', 'drone', 'cruise', 'ballistic')))

# Definitions only: all older suites remain independently counted.
executor_path = ROOT / 'tools/validation/diplomacy_package_18/test_foreign_cash.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'equipment_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
read, option, effect, check, one = (source[name] for name in ('read', 'option', 'effect', 'check', 'one'))
source_trigger, source_execute, source_state = source['trigger'], source['execute'], source['state']

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'has_equipment':
            assert isinstance(val, list) and len(val) == 1, ('Unsupported stock query shape', val)
            archetype, comparison, wanted = val[0]
            assert archetype in PACKETS, ('Unmodeled equipment stock query', archetype)
            # A native stored-count classification is supplied as a fixture.
            # Variant selection and native aggregation remain outside the model.
            stored = result['countries'][ctx['scope']]['equipment_stock'][archetype]
            assert isinstance(stored, int) and not isinstance(stored, bool) and stored >= 0, ('Stock fixture must be a nonnegative integer', archetype, stored)
            passed = model['compare'](stored, comparison, model['value'](result, ctx, wanted))
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
        if key == 'send_equipment':
            assert {name for name, op, value in val} == {'equipment', 'amount', 'target'}, val
            archetype, amount = one(val, 'equipment'), float(one(val, 'amount'))
            assert archetype in PACKETS and amount == PACKETS[archetype], ('Unexpected native equipment dispatch', archetype, amount)
            target = model['country_ref'](result, ctx, one(val, 'target'))
            result.setdefault('native_equipment_calls', []).append({
                'root': ctx['root'], 'from': ctx['from'], 'source': ctx['scope'], 'target': target,
                'equipment': archetype, 'amount': amount, 'parameters': deepcopy(val),
                'fixture_source_stock': result['countries'][ctx['scope']]['equipment_stock'][archetype]})
            # Observe the actual effect call. Do not simulate a native debit,
            # recipient credit, transit queue, transport loss or completion.
        elif key == 'custom_effect_tooltip':
            result.setdefault('observed_tooltips', []).append((ctx['scope'], val))
        else: source_execute(grouped, result, ctx)

for namespace in (source, source['source'], source['source']['source'], source['source']['source']['source'],
                  source['source']['source']['source']['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute
for registry, path in (('effects', 'common/scripted_effects/eon_foreign_equipment_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_foreign_equipment_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, op, body in model['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Equipment helpers overwrite earlier definitions'
        model[registry].update(additions)

def state(stock_multiplier=3):
    result = source_state()
    for country in result['countries'].values():
        country['equipment_stock'] = {equipment: count * stock_multiplier for equipment, count in PACKETS.items()}
    return result

def equipment_option():
    return option(model['get_event_map'](read('events/00_War_events.txt')), 'AB_mobilization.4', 'AB_mobilization.4.b')

def old_callback(result): effect(result, equipment_option(), actor='A', from_='B')
def calls(result): return result.get('native_equipment_calls', [])

def focus(name):
    if name == 'dispatch_without_consent':
        result = state(); old_callback(result)
        assert not calls(result), ('No native equipment dispatch may be invoked before recipient consent', calls(result))
        groups['no_native_dispatch_call_before_recipient_consent'] += 1
    elif name == 'replay':
        result = state(); old_callback(result); first = deepcopy(calls(result)); old_callback(result)
        assert calls(result) == first, ('Repeated unsigned equipment callback must not issue another native bundle', len(first), len(calls(result)))
        groups['unsigned_equipment_callback_does_not_repeat_native_dispatch_calls'] += 1
    elif name == 'unavailable_type_with_no_stocks':
        result = state(stock_multiplier=0); old_callback(result)
        assert not calls(result), ('No full original packet is available in the explicit stock fixtures', calls(result))
        groups['zero_stored_count_fixture_does_not_issue_unavailable_native_equipment_calls'] += 1
    else: raise AssertionError(('Unknown focus', name))

def flags(result, actor='A'): return result['countries'][actor]['flags']
def vars_(result, actor='A'): return result['countries'][actor]['variables']
def pending(result, actor='A'): return 'eon_foreign_equipment_pending' in flags(result, actor)
def consented(result, actor='A'): return 'eon_foreign_equipment_consented' in flags(result, actor)
def packet_flag(equipment): return 'eon_foreign_equipment_packet_' + SUFFIXES[equipment]
def manifest(result, actor='A'): return [equipment for equipment in PACKETS if packet_flag(equipment) in flags(result, actor)]
def stocks(result): return {actor: deepcopy(country['equipment_stock']) for actor, country in result['countries'].items()}
def cash(result): return source['cash'](result)
def snapshot(result): return {key: deepcopy(val) for key, val in result.items() if key not in ('temp', 'scope_temps', 'observed_tooltips')}

def send(result, provider='A', receiver='B', force=False):
    body = equipment_option()
    ready = check(result, one(body, 'trigger'), actor=provider, from_=receiver)
    if ready or force: effect(result, body, actor=provider, from_=receiver)
    return ready

def reply(result, provider='A', receiver='B', accepted=True, force=False):
    events = model['get_event_map'](read('events/eon_foreign_equipment_events.txt'))
    body = option(events, 'eon_foreign_equipment.1', 'eon_foreign_equipment.1.' + ('a' if accepted else 'b'))
    ready = check(result, one(body, 'trigger'), actor=receiver, from_=provider)
    if ready or force: effect(result, body, actor=receiver, from_=provider)
    return ready

def commit(result, provider='A', receiver='B'):
    events = model['get_event_map'](read('events/eon_foreign_equipment_events.txt'))
    effect(result, one(events['eon_foreign_equipment.2'], 'immediate'), actor=provider, from_=receiver)

def action(result, actor='A', partner='B', force=False):
    actions = one(model['ast'](read('common/scripted_diplomatic_actions/eon_foreign_equipment_actions.txt')), 'scripted_diplomatic_actions')
    body = one(actions, 'eon_foreign_equipment_withdraw_offer')
    ready = all(check(result, one(body, key), actor=actor, from_=None, scope=partner)
                for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), actor=actor, from_=None, scope=partner)
    return ready

def native_hook(result, name, actor='A', from_='B'):
    hooks = one(model['ast'](read('common/on_actions/eon_foreign_equipment_on_actions.txt')), 'on_actions')
    effect(result, one(one(hooks, name), 'effect'), actor=actor, from_=from_)

def daily(result):
    for actor, country in result['countries'].items():
        if country['exists']: native_hook(result, 'on_daily', actor, None)

def queued(result, identity): return [item for item in result['events'] if item['id'] == identity]

def unrelated(result):
    return {actor: {key: deepcopy(val) for key, val in country.items() if key not in ('variables', 'flags', 'flag_values')}
        | {'variables': {key: deepcopy(val) for key, val in country['variables'].items() if not key.startswith('eon_foreign_equipment_')},
           'flags': {flag for flag in country['flags'] if not flag.startswith('eon_foreign_equipment_')},
           'flag_values': {flag: val for flag, val in country['flag_values'].items() if not flag.startswith('eon_foreign_equipment_')}}
        for actor, country in result['countries'].items()}

def alteration(result, name):
    provider, receiver = result['countries']['A'], result['countries']['B']
    if name == 'donor_rank': provider['ideas'] -= {'large_power', 'great_power', 'superpower'}
    elif name == 'receiver_rank': receiver['ideas'] -= {'non_power', 'minor_power', 'regional_power'}
    elif name == 'defensive_war_lost': receiver['defensive_war'] = False
    elif name == 'request_timer_lost': provider['flags'].discard('aid_request_cd_@B')
    elif name == 'opinion_lost': provider['opinions']['B'] = 49
    elif name == 'direct_war': provider['wars'].add('B'); receiver['wars'].add('A')
    elif name == 'donor_annexed': provider['exists'] = False
    elif name == 'receiver_annexed': receiver['exists'] = False
    elif name == 'live_expired': provider['flags'].discard('eon_foreign_equipment_live')
    elif name == 'cancelled': provider['flags'].add('eon_foreign_equipment_cancelled')
    else: raise AssertionError(('Unknown alteration', name))

def scenarios():
    for name in ('dispatch_without_consent', 'replay', 'unavailable_type_with_no_stocks'): focus(name)
    equipment = list(PACKETS)
    for mask in range(1, 512):
        selected = [kind for index, kind in enumerate(equipment) if mask & (1 << index)]
        result = state(stock_multiplier=0)
        for kind in selected: result['countries']['A']['equipment_stock'][kind] = PACKETS[kind]
        before = unrelated(result); assert send(result)
        assert pending(result) and not consented(result) and manifest(result) == selected
        assert vars_(result)['eon_foreign_equipment_partner'] == 'B'
        assert not calls(result) and not result.get('political_macro_calls') and unrelated(result) == before
        assert queued(result, 'eon_foreign_equipment.1') == [{'target': 'B', 'id': 'eon_foreign_equipment.1', 'from': 'A'}]
        assert ('A', 'eon_foreign_equipment_live', 30) in result['timer_declarations']
        # Acquiring another type after the offer must never expand its frozen manifest.
        for kind in equipment:
            if kind not in selected: result['countries']['A']['equipment_stock'][kind] = PACKETS[kind] * 3
        untouched = unrelated(result); before_stocks = stocks(result); before_cash = cash(result)
        result['observed_tooltips'] = []
        assert reply(result)
        assert result['observed_tooltips'] == [('B', 'eon_foreign_equipment_manifest_header_tt')] + [
            ('A', 'eon_foreign_equipment_manifest_' + SUFFIXES[kind] + '_tt') for kind in selected] + [('B', 'eon_foreign_equipment_accept_tt')]
        assert pending(result) and consented(result) and manifest(result) == selected and not calls(result)
        assert not result.get('political_macro_calls') and unrelated(result) == untouched
        assert queued(result, 'eon_foreign_equipment.2') == [{'target': 'A', 'id': 'eon_foreign_equipment.2', 'from': 'B'}]
        waiting = snapshot(result)
        assert not reply(result, force=True) and not reply(result, accepted=False, force=True) and not action(result, force=True)
        assert snapshot(result) == waiting and len(queued(result, 'eon_foreign_equipment.2')) == 1
        commit(result)
        assert [(item['equipment'], item['amount']) for item in calls(result)] == [(kind, PACKETS[kind]) for kind in selected]
        assert all(item['source'] == item['root'] == 'A' and item['target'] == item['from'] == 'B' for item in calls(result))
        assert all(item['fixture_source_stock'] >= item['amount'] for item in calls(result))
        assert not pending(result) and not consented(result) and not manifest(result) and not vars_(result).get('eon_foreign_equipment_partner')
        assert stocks(result) == before_stocks and cash(result) == before_cash and unrelated(result) == untouched
        political = result.get('political_macro_calls', [])
        assert len(political) == 1 and political[0][0:2] == ('A', 'change_influence_percentage')
        assert political[0][3]['percent_change'] == 3 and political[0][3]['tag_index'] == 'A' and political[0][3]['influence_target'] == 'B'
        assert result['foreign_cash_political_contexts'] == [{'root': 'A', 'from': 'B', 'scope': 'A'}]
        assert not queued(result, 'AB_mobilization.6')
        settled = snapshot(result); commit(result); reply(result, force=True); reply(result, accepted=False, force=True)
        assert snapshot(result) == settled
        groups['all511_nonempty_frozen_subsets_exact_full_native_call_order_amounts_targets_after_one_consent_commit_without_unselected_additions'] += 1

    for kind in equipment:
        for stage in ('response', 'commit'):
            result = state(); assert send(result)
            if stage == 'commit': assert reply(result)
            result['countries']['A']['equipment_stock'][kind] = PACKETS[kind] - 1
            other = unrelated(result)
            if stage == 'response': reply(result, force=True)
            else: commit(result)
            assert not calls(result) and not result.get('political_macro_calls') and unrelated(result) == other
            assert not pending(result) and not consented(result) and not manifest(result)
            groups['any_one_of_nine_frozen_full_packets_lost_before_' + stage + '_aborts_all_native_calls_without_shrinking'] += 1
    invalid = ('donor_rank', 'receiver_rank', 'defensive_war_lost', 'request_timer_lost', 'opinion_lost',
               'direct_war', 'donor_annexed', 'receiver_annexed')
    for name in invalid:
        result = state(); alteration(result, name); before = snapshot(result)
        assert not send(result, force=True) and snapshot(result) == before
        groups['fresh_invalid_offer_does_not_freeze_manifest_or_dispatch'] += 1
    for stage in ('response', 'commit'):
        for name in invalid + ('live_expired', 'cancelled'):
            result = state(); assert send(result)
            if stage == 'commit': assert reply(result)
            alteration(result, name); other = unrelated(result)
            if stage == 'response': reply(result, force=True)
            else: commit(result)
            assert not calls(result) and not result.get('political_macro_calls') and unrelated(result) == other
            assert not pending(result) and not consented(result) and not manifest(result)
            groups['fresh_policy_expiry_or_cancellation_at_' + stage + '_closes_without_native_calls'] += 1
    result = state(); assert send(result); before = snapshot(result)
    send(result, force=True); send(result, receiver='D', force=True)
    assert snapshot(result) == before
    groups['repeated_same_or_other_partner_send_preserves_owned_manifest_and_pair'] += 1
    for stage in ('response', 'commit'):
        for provider, receiver in (('C', 'B'), ('A', 'D'), ('A', 'A')):
            result = state(); assert send(result)
            if stage == 'commit': assert reply(result)
            before = snapshot(result)
            if stage == 'response': reply(result, provider=provider, receiver=receiver, force=True); reply(result, provider=provider, receiver=receiver, accepted=False, force=True)
            else: commit(result, provider=provider, receiver=receiver)
            assert snapshot(result) == before
            groups['wrong_partner_provider_or_self_' + stage + '_callback_is_inert'] += 1
    result = state(); assert send(result); before = snapshot(result); commit(result)
    assert snapshot(result) == before
    groups['hidden_provider_commit_without_consent_is_inert'] += 1
    result = state(); assert send(result); assert reply(result, accepted=False)
    assert not pending(result) and not manifest(result) and not calls(result)
    assert send(result, receiver='D'); before = snapshot(result)
    reply(result, force=True); reply(result, accepted=False, force=True); commit(result)
    assert snapshot(result) == before
    groups['decline_and_old_consumed_other_partner_callbacks_preserve_later_offer'] += 1
    result = state(); assert send(result); assert action(result)
    assert pending(result) and manifest(result) == equipment and 'eon_foreign_equipment_cancelled' in flags(result)
    assert not action(result, force=True) and not reply(result, force=True)
    assert not pending(result) and not manifest(result) and not calls(result)
    groups['free_native_withdraw_preserves_manifest_until_old_reply_closes_unpaid_undispatched'] += 1
    for actor, partner in (('C', 'B'), ('A', 'D'), ('B', 'A')):
        result = state(); assert send(result); before = snapshot(result)
        assert not action(result, actor=actor, partner=partner, force=True) and snapshot(result) == before
        groups['wrong_native_withdraw_actor_or_target_is_inert'] += 1

    for hook in ('on_annex', 'on_subject_annexed'):
        for winner, victim in (('C', 'A'), ('C', 'B'), ('A', 'B'), ('B', 'A')):
            for consent in (False, True):
                for disappeared in (False, True):
                    result = state(); assert send(result)
                    if consent: assert reply(result)
                    if disappeared: result['countries'][victim]['exists'] = False
                    other = unrelated(result)
                    native_hook(result, hook, winner if hook == 'on_annex' else victim, victim if hook == 'on_annex' else winner)
                    assert not pending(result) and not consented(result) and not manifest(result) and not calls(result) and unrelated(result) == other
                    closed = snapshot(result); reply(result, force=True); commit(result)
                    assert snapshot(result) == closed
                    groups['both_annex_frames_clear_offer_or_consent_and_manifest_before_or_after_fixture_disappears_without_dispatch'] += 1
    for consent in (False, True):
        for name in ('live_expired', 'receiver_annexed'):
            result = state(); assert send(result)
            if consent: assert reply(result)
            alteration(result, name); other = unrelated(result); daily(result)
            assert not pending(result) and not consented(result) and not manifest(result) and not calls(result) and unrelated(result) == other
            assert 'eon_foreign_equipment_retired_pair@B' in flags(result)
            closed = snapshot(result); send(result, force=True); reply(result, force=True); commit(result)
            assert snapshot(result) == closed and send(result, receiver='D')
            groups['daily_expired_or_dead_known_pair_retired_and_another_partner_still_available'] += 1
    for malformed in ('live', 'cancelled', 'consented', 'partner', 'pending_without_partner', 'pending_self', 'pending_unknown') + tuple('packet_' + suffix for suffix in SUFFIXES.values()):
        result = state()
        if malformed in ('live', 'cancelled', 'consented') or malformed.startswith('packet_'): flags(result).add('eon_foreign_equipment_' + malformed)
        elif malformed == 'partner': vars_(result)['eon_foreign_equipment_partner'] = 'B'
        else:
            flags(result).add('eon_foreign_equipment_pending')
            if malformed == 'pending_self': vars_(result)['eon_foreign_equipment_partner'] = 'A'
            elif malformed == 'pending_unknown': vars_(result)['eon_foreign_equipment_partner'] = 999
        other = unrelated(result); daily(result)
        assert 'eon_foreign_equipment_quarantined' in flags(result) and not pending(result) and not manifest(result) and not calls(result) and unrelated(result) == other
        closed = snapshot(result); send(result, receiver='D', force=True); reply(result, force=True); commit(result)
        assert snapshot(result) == closed
        groups['sixteen_orphan_or_malformed_pair_manifest_records_quarantine_only_equipment_channel'] += 1
    result = state(); source['effect'](result, [('eon_foreign_cash_send_offer', '=', 'yes')], actor='A', from_='B')
    other = unrelated(result); assert send(result); assert reply(result); commit(result)
    assert unrelated(result) == other and 'eon_foreign_cash_pending' in flags(result) and vars_(result)['eon_foreign_cash_partner'] == 'B'
    groups['existing_pending_cash_grant_remains_exact_while_equipment_offer_executes_independently'] += 1

    result = state(); assert send(result)
    for kind in equipment: flags(result).discard(packet_flag(kind))
    before = snapshot(result); result['observed_tooltips'] = []
    effect(result, [('eon_foreign_equipment_show_manifest', '=', 'yes')], actor='B', from_='A')
    assert snapshot(result) == before and result['observed_tooltips'] == [('B', 'eon_foreign_equipment_manifest_header_tt')]
    other = unrelated(result); daily(result)
    assert not pending(result) and not manifest(result) and not calls(result) and unrelated(result) == other
    assert 'eon_foreign_equipment_retired_pair@B' in flags(result)
    groups['known_pending_pair_with_empty_manifest_retires_without_native_calls'] += 1
    for phase in ('offered', 'cancelled', 'consented'):
        result = state(stock_multiplier=0)
        selected = ['Inf_equipment', 'guided_missile_equipment']
        for kind in selected: result['countries']['A']['equipment_stock'][kind] = PACKETS[kind]
        assert send(result)
        if phase == 'cancelled': assert action(result)
        elif phase == 'consented': assert reply(result)
        before = snapshot(result); result['observed_tooltips'] = []
        effect(result, [('eon_foreign_equipment_show_manifest', '=', 'yes')], actor='B', from_='A')
        assert snapshot(result) == before and result['observed_tooltips'] == [('B', 'eon_foreign_equipment_manifest_header_tt')] + [
            ('A', 'eon_foreign_equipment_manifest_' + SUFFIXES[kind] + '_tt') for kind in selected]
        result['observed_tooltips'] = []; effect(result, [('eon_foreign_equipment_show_manifest', '=', 'yes')], actor='D', from_='A')
        assert not result['observed_tooltips'] and snapshot(result) == before
        groups['offered_cancelled_and_consented_manifest_tooltips_use_owned_pair_and_no_mutable_UI_effect'] += 1
    for identity in ('missing_record', 'unidentified_partner'):
        result = state()
        if identity == 'unidentified_partner':
            assert send(result); vars_(result)['eon_foreign_equipment_partner'] = 999
        before = snapshot(result); result['observed_tooltips'] = []
        effect(result, [('eon_foreign_equipment_show_manifest', '=', 'yes')], actor='B', from_='A')
        assert snapshot(result) == before and not result['observed_tooltips']
        groups['missing_or_unidentified_pair_manifest_helper_has_no_tooltip_or_mutable_state_effect'] += 1

    # These are explicit query/observer semantics, separately counted from scenarios.
    for kind, count in PACKETS.items():
        for stored in (0, count - 1, count, count + 1):
            result = state(stock_multiplier=0); result['countries']['A']['equipment_stock'][kind] = stored
            assert check(result, [('has_equipment', '=', [(kind, '>', str(count - 1))])], actor='A') == (stored >= count)
            adapter_cases['nine_archetype_count_fixture_boundaries_using_native_strict_comparison'] += 1
    result = state(); before = stocks(result)
    effect(result, [('send_equipment', '=', [('equipment', '=', 'Inf_equipment'), ('amount', '=', '1000'), ('target', '=', 'FROM')])], actor='A', from_='B')
    assert len(calls(result)) == 1 and stocks(result) == before
    adapter_cases['native_dispatch_observer_neither_debits_sender_nor_credits_receiver_fixture_stock'] += 1

def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--focus': focus(sys.argv[2])
    else:
        assert len(sys.argv) == 1, 'Unknown arguments'
        scenarios()
    paths = ['events/00_War_events.txt', 'common/scripted_effects/eon_foreign_equipment_effects.txt',
             'common/scripted_triggers/eon_foreign_equipment_triggers.txt', 'common/scripted_diplomatic_actions/eon_foreign_equipment_actions.txt',
             'common/on_actions/eon_foreign_equipment_on_actions.txt', 'events/eon_foreign_equipment_events.txt',
             'localisation/english/eon_foreign_equipment_l_english.yml', 'localisation/russian/eon_foreign_equipment_l_russian.yml']
    print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'groups': dict(groups),
        'adapter_semantics_cases': sum(adapter_cases.values()), 'adapter_groups': dict(adapter_cases),
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths if (ROOT / path).exists()},
        'native_stock_mutation_simulated': False, 'native_delivery_completion_proven': False,
        'proof_scope': 'ordered current-source frozen equipment manifest and native dispatch calls; not HOI4 shipment completion'}, indent=2))

if __name__ == '__main__': main()
