"""Ordered existing Iran/USA reconciliation route; no native mission or campaign simulation."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'f56ec8b3cd35a0f34ecad9627cbb77991963fca0'
FOCUS_PATH = 'common/national_focus/Iran_Focus_Tree.txt'
EVENT_PATH = 'events/Iran.txt'
POLICY_PATH = 'common/scripted_triggers/00_political_triggers.txt'
FOCUS_ID = 'PER_talks_with_the_americans'
PREFIX = 'eon_per_usa_normalization_'
RECEIPT = 'eon_per_usa_relations_'
SOURCE_PATHS = sorted({FOCUS_PATH, EVENT_PATH} | {f'localisation/{language}/MD_focus_PER_l_{language}.yml' for language in ('english', 'russian')} |
    {'common/scripted_effects/eon_per_usa_normalization_effects.txt', 'common/scripted_triggers/eon_per_usa_normalization_triggers.txt',
     'common/scripted_diplomatic_actions/eon_per_usa_normalization_actions.txt', 'common/on_actions/eon_per_usa_normalization_on_actions.txt',
     'events/eon_per_usa_normalization_events.txt'} | {f'localisation/{language}/eon_per_usa_normalization_l_{language}.yml' for language in ('english', 'russian')})
FOCUSES = ('unowned_accept', 'replay_accept', 'late_war_accept', 'grievances_preserved', 'replay_focus_queue', 'withdrawal_requires_issued_unrestored_pair')
groups = Counter()
adapter_cases = Counter()

# Execute definitions only. Earlier behavioral suites are counted by their own runner.
executor_path = ROOT/'tools/validation/diplomacy_package_22/test_request.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'relations_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
read, option, effect, check, one = (source[name] for name in ('read', 'option', 'effect', 'check', 'one'))
source_trigger, source_execute, source_state = source['trigger'], source['execute'], source['state']
source_compare = model['compare']
NAMESPACES = (source, *source['NAMESPACES'])
parser_path = 'tools/validation/diplomacy_package_22/test_source.py'
parser_text = subprocess.check_output(['git', 'show', BASELINE+':'+parser_path], cwd=ROOT).decode('utf-8')
parser = {'__file__': str(ROOT/parser_path), '__name__': 'relations_byte_parser'}
exec(compile(parser_text.split('def package22_original_bytes(', 1)[0], str(ROOT/parser_path), 'exec'), parser)
COUNTRY_IDS = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'USA': 5, 'PER': 6}

def compare(left, operator, right):
    # Positive ordinals prove country identity in this fixture, not a native save ID.
    if operator not in ('=', '==', '!='):
        if isinstance(left, str) and left in COUNTRY_IDS: left = COUNTRY_IDS[left]
        if isinstance(right, str) and right in COUNTRY_IDS: right = COUNTRY_IDS[right]
    return source_compare(left, operator, right)

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'country_exists':
            target = model['country_ref'](result, ctx, val)
            ready = target in result['countries'] and result['countries'][target]['exists']
        elif key == 'is_in_array' and isinstance(val, list) and len(val) == 1:
            array, comparison, wanted = val[0]
            assert array == 'ruling_party' and comparison == '=', ('Unsupported native array shorthand', val)
            ready = model['value'](result, ctx, wanted) in result['countries'][ctx['scope']]['arrays'].get(array, [])
        else: ready = source_trigger(grouped, result, ctx)
        if not ready: return False
    return True

def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'newline':
            assert val == 'yes', ('Unsupported presentation command', val)
            continue
        if key == 'change_influence_percentage':
            result.setdefault('relations_influence_calls', []).append({
                'root': ctx['root'], 'from': ctx['from'], 'scope': ctx['scope'],
                'temporaries': deepcopy(result.setdefault('scope_temps', {}).get(ctx['scope'], {})),
                'pending_at_call': {actor: PREFIX+'pending' in result['countries'][actor]['flags'] for actor in ('PER', 'USA')},
                'partner_at_call': {actor: result['countries'][actor]['variables'].get(PREFIX+'partner', 0) for actor in ('PER', 'USA')}})
        source_execute(grouped, result, ctx)

for namespace in NAMESPACES:
    namespace['trigger'] = trigger; namespace['execute'] = execute; namespace['compare'] = compare
policies = dict((key, body) for key, operator, body in model['ast'](read(POLICY_PATH)))
for key in ('emerging_hardline_shiite_are_in_power', 'emerging_moderate_shiite_are_in_power'):
    assert key not in model['capacity_triggers'], ('Political helper registry collision', key)
    model['capacity_triggers'][key] = policies[key]
for registry, path in (('effects', 'common/scripted_effects/eon_per_usa_normalization_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_per_usa_normalization_triggers.txt')):
    if (ROOT/path).exists():
        additions = {key: body for key, operator, body in model['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Normalization helpers overwrite earlier IDs'
        model[registry].update(additions)

def focus_field(name):
    data = (ROOT/FOCUS_PATH).read_bytes()
    candidates = [block for block in parser['blocks'](data) if block['key'] == 'focus' and
                  re.search(rb'\bid\s*=\s*'+FOCUS_ID.encode()+rb'\b', data[block['start']:block['end']])]
    assert len(candidates) == 1, ('Expected one actual Iran focus', len(candidates))
    selected = data[candidates[0]['start']:candidates[0]['end']]
    fields = [block for block in parser['blocks'](selected, 1) if block['key'] == name]
    assert len(fields) == 1, ('Expected one actual focus field', name, len(fields))
    return one(model['ast'](selected[fields[0]['start']:fields[0]['end']].decode('utf-8-sig')), name)

def state():
    result = source_state()
    result['countries']['USA'] = deepcopy(result['countries']['A'])
    result['countries']['PER'] = deepcopy(result['countries']['B'])
    for actor, country in result['countries'].items():
        country['original_tag'] = actor
        country['wars'] = set(); country['civil_war'] = False
        country['arrays']['ruling_party'] = [5]
        country['opinions'] = {peer: 20 for peer in result['countries']}
        country['opinion_modifiers'] = set()
    result['countries']['USA']['opinion_modifiers'].update({('PER', 'no_diplomatic_ties'), ('PER', 'beirut_bombing'), ('PER', 'iran_hostage_crisis')})
    result['countries']['PER']['opinion_modifiers'].update({('USA', 'no_diplomatic_ties'), ('USA', 'cia_coup_mossadeq'),
        ('USA', 'operation_praying_mantis'), ('USA', 'helped_iraqi_chemical_weapons'), ('USA', 'uss_vincennes')})
    return result

def completion(result, actor='PER'):
    effect(result, focus_field('completion_reward'), actor=actor, from_=None)

def response(result, suffix='a', actor='USA', requester='PER'):
    events = model['get_event_map'](read(EVENT_PATH))
    effect(result, option(events, 'iranian_focus.64', 'iranian_focus.64.'+suffix), actor=actor, from_=requester)

def queued(result, identity): return [item for item in result['events'] if item['id'] == identity]
def influence(result): return result.get('relations_influence_calls', [])
def grievances(result):
    return {actor: {item for item in result['countries'][actor]['opinion_modifiers'] if item[1] != 'no_diplomatic_ties'}
            for actor in ('USA', 'PER')}

def fields(result, actor):
    country = result['countries'][actor]
    return {'flags': {flag for flag in country['flags'] if flag.startswith(PREFIX)},
            'partner': country['variables'].get(PREFIX+'partner', 0)}

def pending(result, actor): return PREFIX+'pending' in result['countries'][actor]['flags']

def assert_pending(result):
    for actor, peer in (('USA', 'PER'), ('PER', 'USA')):
        assert pending(result, actor) and fields(result, actor)['partner'] == peer
        assert PREFIX+'request_issued' in result['countries'][actor]['flags']

def assert_closed(result):
    for actor in ('USA', 'PER'):
        assert not pending(result, actor) and not fields(result, actor)['partner']
        assert not ({PREFIX+'live', PREFIX+'cancelled'} & fields(result, actor)['flags'])

def assert_issued(result):
    assert all(PREFIX+'request_issued' in result['countries'][actor]['flags'] for actor in ('USA', 'PER'))

def assert_restored(result):
    for actor, peer in (('USA', 'PER'), ('PER', 'USA')):
        assert RECEIPT+'restored' in result['countries'][actor]['flags']
        assert result['countries'][actor]['variables'][RECEIPT+'partner'] == peer
        assert (peer, 'no_diplomatic_ties') not in result['countries'][actor]['opinion_modifiers']

def resources(result):
    return {actor: {key: deepcopy(country[key]) for key in ('equipment_stock', 'available_manpower', 'templates', 'native_unit_inventory')} |
        {'cash': {key: country['variables'][key] for key in ('treasury', 'political_power')}} for actor, country in result['countries'].items()}

def foreign_channels(result):
    return {actor: {'flags': {flag for flag in country['flags'] if not flag.startswith((PREFIX, RECEIPT)) and flag != 'USA_iranian_friendship'},
        'variables': {key: deepcopy(value) for key, value in country['variables'].items() if not key.startswith((PREFIX, RECEIPT))},
        'arrays': deepcopy(country['arrays']), 'ideas': deepcopy(country['ideas'])} for actor, country in result['countries'].items()}

def seed_foreign_channels(result):
    for actor, country in result['countries'].items():
        country['flags'].update({'eon_services_pending', 'eon_foreign_cash_pending', 'eon_foreign_equipment_pending',
            'eon_defence_formation_pending', 'eon_advisers_outgoing_owned', 'eon_advisers_incoming_owned', 'eon_support_request_pending'})
        for stem in ('eon_services', 'eon_foreign_cash', 'eon_foreign_equipment', 'eon_defence_formation', 'eon_support_request'):
            country['variables'][stem+'_partner'] = 'C'
        country['variables'].update(eon_advisers_outgoing_partner='C', eon_advisers_incoming_partner='D')
        country['ideas'].add('eon_advisers_mission_idea')

def menu_trigger(result, suffix='a', actor='USA', requester='PER'):
    events = model['get_event_map'](read(EVENT_PATH))
    choice = option(events, 'iranian_focus.64', 'iranian_focus.64.'+suffix)
    triggers = [body for key, operator, body in choice if key == 'trigger']
    assert len(triggers) <= 1
    return not triggers or check(result, triggers[0], actor=actor, from_=requester)

def native_action():
    return one(one(model['ast'](read('common/scripted_diplomatic_actions/eon_per_usa_normalization_actions.txt')), 'scripted_diplomatic_actions'), PREFIX+'withdraw_request')

def withdraw(result, requester='PER', receiver='USA'):
    effect(result, one(native_action(), 'complete_effect'), actor=requester, from_=receiver, scope=receiver)

def native_hook(result, identity, actor, from_=None):
    nodes = one(model['ast'](read('common/on_actions/eon_per_usa_normalization_on_actions.txt')), 'on_actions')
    effect(result, one(one(nodes, identity), 'effect'), actor=actor, from_=from_)

def daily(result):
    for actor in tuple(result['countries']): native_hook(result, 'on_daily', actor)

def mutate(result, name):
    if name == 'usa_dead': result['countries']['USA']['exists'] = False
    elif name == 'per_dead': result['countries']['PER']['exists'] = False
    elif name == 'war':
        result['countries']['USA']['wars'].add('PER'); result['countries']['PER']['wars'].add('USA')
    elif name == 'usa_only_war': result['countries']['USA']['wars'].add('PER')
    elif name == 'per_only_war': result['countries']['PER']['wars'].add('USA')
    elif name in ('moderate', 'hardline'): result['countries']['PER']['arrays']['ruling_party'] = [8 if name == 'moderate' else 9]
    elif name in ('usa_ties_restored_elsewhere', 'per_ties_restored_elsewhere'):
        actor, peer = ('USA', 'PER') if name.startswith('usa') else ('PER', 'USA')
        result['countries'][actor]['opinion_modifiers'].discard((peer, 'no_diplomatic_ties'))
    elif name == 'expired': result['countries']['USA']['flags'].discard(PREFIX+'live')
    elif name == 'cancelled': result['countries']['USA']['flags'].add(PREFIX+'cancelled')
    else: raise AssertionError(('Unknown fixture mutation', name))

def focus(name):
    if name == 'unowned_accept':
        result = state(); before = grievances(result); response(result)
        assert not influence(result) and 'USA_iranian_friendship' not in result['countries']['USA']['flags'], (
            'An unowned USA acceptance grants friendship or influence', influence(result), result['countries']['USA']['flags'])
        assert grievances(result) == before
        groups['unowned_acceptance_cannot_restore_relations_or_grant_benefits'] += 1
    elif name == 'replay_accept':
        result = state(); completion(result); response(result); first = deepcopy(influence(result))
        assert len(first) == 1, ('One genuine consent must retain one existing influence call', first)
        response(result)
        assert influence(result) == first, ('Consumed consent repeats the existing influence benefit', influence(result))
        groups['owned_acceptance_commits_original_benefit_only_once'] += 1
    elif name == 'late_war_accept':
        result = state(); completion(result)
        result['countries']['USA']['wars'].add('PER'); result['countries']['PER']['wars'].add('USA')
        response(result)
        assert not influence(result) and ('PER', 'no_diplomatic_ties') in result['countries']['USA']['opinion_modifiers'] and (
            'USA', 'no_diplomatic_ties') in result['countries']['PER']['opinion_modifiers'], (
            'Late direct war still permits relation restoration', influence(result), result['countries']['USA']['opinion_modifiers'])
        groups['fresh_direct_war_condition_blocks_late_acceptance'] += 1
    elif name == 'grievances_preserved':
        result = state(); before = grievances(result); completion(result); response(result)
        assert grievances(result) == before, ('Restoring relations erases unrelated historical grievances', before, grievances(result))
        assert ('PER', 'no_diplomatic_ties') not in result['countries']['USA']['opinion_modifiers']
        assert ('USA', 'no_diplomatic_ties') not in result['countries']['PER']['opinion_modifiers']
        groups['consent_restores_both_directed_no_ties_without_erasing_history'] += 1
    elif name == 'replay_focus_queue':
        result = state(); completion(result); first = deepcopy(queued(result, 'iranian_focus.64'))
        assert len(first) == 1, ('Fresh national focus must queue exactly one USA response', first)
        completion(result)
        assert queued(result, 'iranian_focus.64') == first, ('Replayed focus completion queues a duplicate response', result['events'])
        groups['one_use_national_focus_cannot_issue_duplicate_response_windows'] += 1
    elif name == 'withdrawal_requires_issued_unrestored_pair':
        for actor in ('USA', 'PER'):
            for malformed in ('missing_issued', 'restored_receipt'):
                result = state(); completion(result)
                if malformed == 'missing_issued': result['countries'][actor]['flags'].discard(PREFIX+'request_issued')
                else: result['countries'][actor]['flags'].add(RECEIPT+'restored')
                before = {peer: deepcopy(fields(result, peer)) for peer in ('USA', 'PER')}; events = deepcopy(result['events'])
                withdraw(result)
                assert result['events'] == events and {peer: fields(result, peer) for peer in before} == before, (
                    'Withdrawal adopts an unissued or already restored pair', actor, malformed, result['events'], fields(result, 'USA'), fields(result, 'PER'))
                assert not check(result, one(native_action(), 'can_be_sent'), actor='PER', from_='USA', scope='USA')
                groups['withdrawal_requires_both_original_issuance_markers_and_no_existing_restoration_receipt'] += 1
    else: raise AssertionError(('Unknown focus', name))

def main():
    for name in FOCUSES: focus(name)
    result = state(); before = resources(result); seed_foreign_channels(result); protected = foreign_channels(result)
    assert check(result, focus_field('available'), actor='PER', from_=None)
    completion(result); assert_pending(result)
    assert queued(result, 'iranian_focus.64') == [{'target': 'USA', 'id': 'iranian_focus.64', 'from': 'PER'}]
    assert ('USA', PREFIX+'live', 30.0) in result['timer_declarations']
    assert PREFIX+'live' not in fields(result, 'PER')['flags']
    assert menu_trigger(result) and menu_trigger(result, 'b')
    assert resources(result) == before and foreign_channels(result) == protected
    assert not influence(result) and not any(flag.startswith(RECEIPT) for actor in ('PER', 'USA') for flag in result['countries'][actor]['flags'])
    groups['actual_focus_issues_reciprocal_one_use_record_without_resources_or_restoration'] += 1
    old_history = grievances(result); response(result); assert_closed(result); assert_restored(result); assert_issued(result)
    assert resources(result) == before and foreign_channels(result) == protected and grievances(result) == old_history
    calls = influence(result); assert len(calls) == 1
    call = calls[0]; assert (call['root'], call['from'], call['scope']) == ('USA', 'PER', 'USA')
    assert call['temporaries']['percent_change'] == 2 and call['temporaries']['tag_index'] == 'USA' and call['temporaries']['influence_target'] == 'PER'
    assert not any(call['pending_at_call'].values()) and not any(call['partner_at_call'].values())
    assert 'USA_iranian_friendship' in result['countries']['USA']['flags']
    assert result['opinion_calls'] == [('PER', 'remove_opinion_modifier', ('USA', 'no_diplomatic_ties')),
        ('USA', 'remove_opinion_modifier', ('PER', 'no_diplomatic_ties'))]
    assert queued(result, 'iranian_focus.65') == [{'target': 'PER', 'id': 'iranian_focus.65', 'from': 'USA'}]
    groups['consent_consumes_pair_before_exact_existing_national_package_and_two_directed_removals'] += 1
    for callback in ('a', 'b'):
        previous = deepcopy(result['events']); response(result, callback); completion(result)
        assert len(influence(result)) == 1 and result['events'] == previous and resources(result) == before
        groups['consumed_accept_or_decline_and_focus_callbacks_cannot_repeat_or_reissue'] += 1

    for name in ('usa_dead', 'per_dead', 'war', 'usa_only_war', 'per_only_war', 'moderate', 'hardline',
                 'usa_ties_restored_elsewhere', 'per_ties_restored_elsewhere'):
        result = state(); mutate(result, name); completion(result)
        assert not queued(result, 'iranian_focus.64') and not pending(result, 'USA') and not pending(result, 'PER') and not influence(result)
        groups['fresh_national_policy_and_both_directed_no_ties_gate_focus_completion'] += 1
    for actor in ('USA', 'PER'):
        for field in ('request_issued', 'pending', 'live', 'cancelled', 'restored', 'partner'):
            result = state(); country = result['countries'][actor]
            if field == 'restored': country['flags'].add(RECEIPT+'restored')
            elif field == 'partner': country['variables'][PREFIX+'partner'] = 'C'
            else: country['flags'].add(PREFIX+field)
            completion(result)
            assert not queued(result, 'iranian_focus.64') and not influence(result)
            groups['issued_receipt_or_dirty_local_slot_blocks_preparation_on_either_country'] += 1
    for actor in ('USA', 'C', 'D'):
        result = state(); completion(result, actor)
        assert not queued(result, 'iranian_focus.64') and not influence(result)
        groups['actual_named_focus_callback_requires_current_PER_actor'] += 1

    invalid = ('usa_dead', 'per_dead', 'war', 'usa_only_war', 'per_only_war', 'moderate', 'hardline',
        'usa_ties_restored_elsewhere', 'per_ties_restored_elsewhere', 'expired', 'cancelled')
    for name in invalid:
        result = state(); completion(result); mutate(result, name); before = grievances(result)
        assert not menu_trigger(result) and menu_trigger(result, 'b')
        response(result)
        assert not influence(result) and grievances(result) == before and not queued(result, 'iranian_focus.65')
        assert 'USA_iranian_friendship' not in result['countries']['USA']['flags']
        groups['acceptance_rechecks_fresh_policy_liveness_expiry_cancellation_and_both_directed_markers'] += 1
        response(result, 'b'); assert_closed(result); assert_issued(result)
        assert not queued(result, 'iranian_focus.66')
        groups['always_visible_decline_closes_owned_invalid_reply_without_false_refusal'] += 1

    for actor in ('USA', 'PER'):
        for invalid_field in ('missing_pending', 'missing_issued', 'zero', 'negative', 'state_id', 'third_country', 'self'):
            result = state(); completion(result); country = result['countries'][actor]
            if invalid_field.startswith('missing_'): country['flags'].discard(PREFIX+('request_issued' if invalid_field == 'missing_issued' else 'pending'))
            else: country['variables'][PREFIX+'partner'] = {'zero': 0, 'negative': -1, 'state_id': 101, 'third_country': 'C', 'self': actor}[invalid_field]
            response(result); response(result, 'b')
            assert not influence(result) and not queued(result, 'iranian_focus.65') and not queued(result, 'iranian_focus.66'), (actor, invalid_field, influence(result), result['events'], fields(result, 'USA'), fields(result, 'PER'))
            groups['missing_one_side_marker_or_nonpositive_noncountry_wrong_peer_ID_cannot_authorize_consent'] += 1
    for actor, requester in (('C', 'PER'), ('USA', 'C'), ('PER', 'USA'), ('D', 'D')):
        result = state(); completion(result); owned = {peer: deepcopy(fields(result, peer)) for peer in ('USA', 'PER')}
        for suffix in ('a', 'b'): response(result, suffix, actor, requester)
        assert {peer: fields(result, peer) for peer in owned} == owned and not influence(result)
        groups['wrong_ROOT_or_FROM_callbacks_leave_valid_owned_request_inert'] += 1

    result = state(); completion(result); response(result, 'b'); assert_closed(result); assert_issued(result)
    assert queued(result, 'iranian_focus.66') == [{'target': 'PER', 'id': 'iranian_focus.66', 'from': 'USA'}]
    first = deepcopy(result['events']); response(result, 'b'); response(result); completion(result)
    assert result['events'] == first and not influence(result)
    groups['valid_owned_decline_notifies_once_and_never_resets_national_issuance'] += 1
    for suffix in ('a', 'b'):
        result = state(); response(result, suffix); response(result, suffix)
        assert not result['events'] and not influence(result)
        groups['unowned_pre_upgrade_reply_is_safe_when_no_new_owned_pair_exists'] += 1

    result = state(); completion(result); before = resources(result)
    assert check(result, one(native_action(), 'can_be_sent'), actor='PER', from_='USA', scope='USA')
    withdraw(result); assert_pending(result); assert PREFIX+'cancelled' in fields(result, 'USA')['flags']
    assert not check(result, one(native_action(), 'can_be_sent'), actor='PER', from_='USA', scope='USA')
    withdraw(result); assert len(queued(result, 'eon_per_usa_normalization.1')) == 1
    response(result); response(result, 'b'); assert_closed(result); assert_issued(result)
    assert not influence(result) and not queued(result, 'iranian_focus.66') and resources(result) == before
    groups['native_free_withdrawal_retains_pair_until_matching_close_and_cannot_repeat'] += 1
    for name in ('expired', 'cancelled', 'usa_dead', 'per_dead'):
        result = state(); completion(result); mutate(result, name); before = deepcopy(result['events'])
        withdraw(result); assert result['events'] == before
        groups['expired_cancelled_or_dead_pair_cannot_emit_a_new_withdrawal_notice'] += 1
    for requester, receiver in (('C', 'USA'), ('PER', 'C'), ('USA', 'PER')):
        result = state(); completion(result); before = {actor: deepcopy(fields(result, actor)) for actor in ('PER', 'USA')}
        withdraw(result, requester, receiver)
        assert {actor: fields(result, actor) for actor in before} == before
        groups['withdrawal_requires_native_PER_initiator_USA_receiver_frame'] += 1
    result = state(); completion(result); result['countries']['PER']['ai'] = True; withdraw(result)
    assert not queued(result, 'eon_per_usa_normalization.1')
    groups['human_only_withdrawal_does_not_invent_AI_cancellation'] += 1
    for name in ('war', 'moderate', 'hardline', 'usa_ties_restored_elsewhere', 'per_ties_restored_elsewhere'):
        result = state(); completion(result); mutate(result, name)
        assert not menu_trigger(result)
        withdraw(result); assert_pending(result)
        assert len(queued(result, 'eon_per_usa_normalization.1')) == 1 and PREFIX+'cancelled' in fields(result, 'USA')['flags']
        groups['authenticated_live_request_can_be_withdrawn_after_policy_loss_before_cleanup'] += 1

    for name in invalid:
        for actor in ('USA', 'PER'):
            result = state(); seed_foreign_channels(result); protected = foreign_channels(result); before = resources(result)
            completion(result); mutate(result, name); history = grievances(result); protected = foreign_channels(result)
            native_hook(result, 'on_daily', actor); assert_closed(result); assert_issued(result)
            first = deepcopy(result['events']); daily(result)
            assert result['events'] == first and not influence(result) and grievances(result) == history
            assert foreign_channels(result) == protected and resources(result) == before
            groups['daily_closes_only_initial_exact_pair_from_either_country_without_repeated_notifications'] += 1
    for actor in ('USA', 'PER'):
        peer = 'PER' if actor == 'USA' else 'USA'
        for garbage in ('zero', 'negative', 'state_id', 'third_country', 'no_local_pending', 'no_peer_pending', 'peer_wrong_id'):
            result = state(); completion(result)
            country = result['countries'][actor]; counterparty = result['countries'][peer]
            if garbage == 'no_local_pending': country['flags'].discard(PREFIX+'pending')
            elif garbage == 'no_peer_pending': counterparty['flags'].discard(PREFIX+'pending')
            elif garbage == 'peer_wrong_id': counterparty['variables'][PREFIX+'partner'] = 'C'
            else: country['variables'][PREFIX+'partner'] = {'zero': 0, 'negative': -1, 'state_id': 101, 'third_country': 'C'}[garbage]
            peer_before = deepcopy(fields(result, peer)); third_before = deepcopy(result['countries']['C'])
            native_hook(result, 'on_daily', actor)
            assert not pending(result, actor) and not fields(result, actor)['partner']
            assert fields(result, peer) == peer_before and result['countries']['C'] == third_before
            assert not queued(result, 'eon_per_usa_normalization.2')
            native_hook(result, 'on_daily', peer); assert_closed(result); assert_issued(result)
            groups['malformed_fixed_country_clears_locally_without_adopting_or_erasing_foreign_ownership'] += 1
    result = state(); completion(result)
    result['countries']['C']['flags'].update({PREFIX+'pending', PREFIX+'live'}); result['countries']['C']['variables'][PREFIX+'partner'] = 'USA'
    third_before = deepcopy(result['countries']['C']); native_hook(result, 'on_daily', 'C')
    assert result['countries']['C'] == third_before and pending(result, 'USA') and pending(result, 'PER')
    groups['third_country_namespace_garbage_is_not_a_diplomatic_state_or_owned_pair'] += 1

    for hook in ('on_annex', 'on_subject_annexed'):
        for victim in ('PER', 'USA', 'C'):
            result = state(); completion(result); seed_foreign_channels(result); protected = foreign_channels(result)
            before = resources(result); result['countries'][victim]['exists'] = False
            actor, sender = ('D', victim) if hook == 'on_annex' else (victim, 'D')
            native_hook(result, hook, actor, sender)
            if victim in ('PER', 'USA'): assert_closed(result); assert_issued(result)
            else: assert_pending(result)
            assert resources(result) == before and foreign_channels(result) == protected and not influence(result)
            groups['both_native_annex_frames_clear_only_actual_national_request_pair'] += 1
    for name in ('war', 'moderate', 'hardline', 'usa_dead', 'per_dead'):
        result = state(); completion(result); response(result); before = resources(result); history = grievances(result)
        mutate(result, name); daily(result); assert_closed(result); assert_issued(result); assert_restored(result)
        assert 'USA_iranian_friendship' in result['countries']['USA']['flags'] and len(influence(result)) == 1
        assert resources(result) == before and grievances(result) == history
        groups['historical_normalization_receipt_and_national_friendship_survive_later_policy_or_war_change'] += 1
    for hook in ('on_annex', 'on_subject_annexed'):
        for victim in ('PER', 'USA'):
            result = state(); completion(result); response(result); result['countries'][victim]['exists'] = False
            actor, sender = ('D', victim) if hook == 'on_annex' else (victim, 'D')
            native_hook(result, hook, actor, sender); assert_restored(result); assert_issued(result)
            assert len(influence(result)) == 1
            groups['annex_request_cleanup_does_not_rewrite_permanent_historical_receipt'] += 1

    for actor in ('PER', 'USA'):
        result = state(); assert check(result, [('country_exists', '=', actor)], actor='C', from_=None)
        result['countries'][actor]['exists'] = False; assert not check(result, [('country_exists', '=', actor)], actor='C', from_=None)
        adapter_cases['country_exists_is_explicit_country_fixture_not_inferred_presence'] += 1
        assert compare(actor, '>', 0) and not compare(actor, '=', 'C')
        adapter_cases['positive_symbolic_ID_retains_exact_country_identity'] += 1
    for ruling, hardline, moderate in ((5, False, False), (8, False, True), (9, True, False)):
        result = state(); result['countries']['PER']['arrays']['ruling_party'] = [ruling]
        for key, expected in (('emerging_hardline_shiite_are_in_power', hardline), ('emerging_moderate_shiite_are_in_power', moderate)):
            assert check(result, [(key, '=', 'yes')], actor='PER', from_=None) == expected
            adapter_cases['actual_existing_political_helpers_execute_native_array_shorthand'] += 1
    result = state()
    try: check(result, [('is_in_array', '=', [('unknown_array', '=', '9')])], actor='PER', from_=None)
    except AssertionError: pass
    else: raise AssertionError('Unknown array shorthand silently accepted')
    adapter_cases['unknown_array_shorthand_fails_closed'] += 1
    completion(result)
    assert PREFIX+'live' in fields(result, 'USA')['flags'] and ('USA', PREFIX+'live', 30.0) in result['timer_declarations']
    mutate(result, 'expired'); assert PREFIX+'live' not in fields(result, 'USA')['flags']
    adapter_cases['timed_flag_records_declaration_and_expiry_is_explicit_fixture_input'] += 1
    events = model['get_event_map'](read(EVENT_PATH))
    accept = option(events, 'iranian_focus.64', 'iranian_focus.64.a'); decline = option(events, 'iranian_focus.64', 'iranian_focus.64.b')
    assert float(one(one(accept, 'ai_chance'), 'base')) > 0 and float(one(one(decline, 'ai_chance'), 'base')) > 0
    mutate(result, 'cancelled'); assert not menu_trigger(result) and menu_trigger(result, 'b')
    groups['invalid_only_decline_is_visible_and_retains_original_positive_AI_weight'] += 1

def report():
    return {'all_passed': True, 'baseline': BASELINE, 'actual_source_scenarios': sum(groups.values()),
        'scenario_groups': dict(groups), 'adapter_semantics_cases': sum(adapter_cases.values()), 'adapter_groups': dict(adapter_cases),
        'source_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_PATHS if (ROOT/path).exists()},
        'protected_dependencies_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in (POLICY_PATH, 'tools/validation/diplomacy_package_22/test_request.py')},
        'prior_scope': 'unchanged_children_with_historical_AB4_caller_view', 'new_historical_caller_projection': False,
        'native_runtime': False, 'native_physical_mission_presence_proven': False, 'native_resource_mutation_simulated': False,
        'immutable_event_generation_proven': False,
        'proof_scope': 'actual one-use PER focus, USA response, bilateral initial record and historical normalization receipt; engine scheduling, save/load, embassy presence and callback generations unverified'}

if __name__ == '__main__':
    if len(sys.argv) > 1:
        assert len(sys.argv) == 3 and sys.argv[1] == '--focus' and sys.argv[2] in FOCUSES, sys.argv[1:]
        focus(sys.argv[2])
    else: main()
    print(json.dumps(report(), indent=2))
