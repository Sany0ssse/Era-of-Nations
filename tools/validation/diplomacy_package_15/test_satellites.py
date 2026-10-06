"""Ordered actual-source immediate COM graph and typed cooldown proof."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '3f044a30711e7dba015969a9a5bd2b0229703a3c'
groups = Counter()
adapter_cases = Counter()
executor_path = ROOT / 'tools/validation/diplomacy_package_14/test_satellites.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# Focused actual-source regressions: ROOT must observe RED before game edits.'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'com_network_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch, read = (source[name] for name in ('ast', 'one', 'context', 'switch', 'read'))
trigger, execute = source['trigger'], source['execute']
civilian, extended = source['civilian'], source['source']
actions = extended['actions']
missile_effects = ast(read('common/scripted_effects/00_missiles_scripted_effects.txt'))
for name in ('update_COM_system_stats', 'calculate_COM_mil_gui_vars', 'calculate_COM_civ_gui_vars', 'COM_mil_button_update', 'COM_civ_button_update'):
    model['effects'][name] = one(missile_effects, name)

FACTORS = {'civ': civilian['FACTORS']['COM'], 'mil': extended['FAMILIES']['com_mil'][3]}
SOURCE_PATHS = (
    'common/scripted_effects/00_missiles_scripted_effects.txt',
    'common/scripted_effects/eon_satellite_effects.txt',
    'common/scripted_effects/eon_satellite_extended_effects.txt',
    'common/scripted_triggers/eon_satellite_triggers.txt',
    'common/scripted_triggers/eon_satellite_extended_triggers.txt',
    'common/scripted_triggers/MD_missile_scripted_triggers.txt',
    'common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt',
    'localisation/english/eon_satellite_l_english.yml',
    'localisation/russian/eon_satellite_l_russian.yml',
    'localisation/english/eon_satellite_extended_l_english.yml',
    'localisation/russian/eon_satellite_extended_l_russian.yml',
)

def physical(result, actor):
    result['temp'] = {}
    execute([(name, '=', 'yes') for name in ('update_COM_system_stats', 'calculate_COM_mil_gui_vars', 'calculate_COM_civ_gui_vars')], result, context(actor))

def aggregate(result, actor):
    result['temp'] = {}
    execute([('eon_sat_refresh_com', '=', 'yes'), ('eon_sat_refresh_com_mil', '=', 'yes')], result, context(actor))

def state():
    result = source['state']()
    declarations = one(ast(read('common/scripted_effects/00_missiles_models.txt')), 'set_sat_system_max')
    result['global']['arrays']['COM_sat_system_max_array'] = [float(nodes[0][2]) for key, op, nodes in declarations
        if key == 'add_to_array' and len(nodes) == 1 and nodes[0][0] == 'global.COM_sat_system_max_array']
    assert len(result['global']['arrays']['COM_sat_system_max_array']) == 8
    for actor, country in result['countries'].items():
        country['variables'].update(var_COM_mil_system_idx=0, var_COM_civ_system_idx=0,
            var_COM_mil_sat_system_max=10, var_COM_civ_sat_system_max=10,
            num_battalions=100, num_ships=0, num_deployed_planes=0, num_controlled_states=1)
        country['arrays']['COM_satellite_array'] = [0, 0, 0, 10, 0, 0, 0, 0]
        # Explicit receiver-technology fixture, not an inferred native default.
        country['arrays']['COM_sat_receiver_tech_array'] = [100] * 8
    return result

def seed(result, service, recipient, provider):
    prefix = 'COM_' + service
    result['countries'][recipient]['arrays'][prefix + '_access_array'].append(provider)
    result['countries'][recipient]['arrays'][prefix + '_access_system_idx_array'].append(result['countries'][provider]['variables']['var_' + prefix + '_system_idx'])
    result['countries'][provider]['arrays'][prefix + '_treaty_array'].append(recipient)

def network(service, kind='request', existing=True):
    result = state(); provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
    for role in ('mil', 'civ'):
        result['countries'][provider]['variables']['var_COM_' + role + '_system_idx'] = 3
    result['countries'][recipient]['variables'].update(num_battalions=1500, num_controlled_states=15)
    if existing: seed(result, service, 'C', provider)
    for actor in result['countries']: physical(result, actor)
    for actor in result['countries']: aggregate(result, actor)
    return result, provider, recipient

def send(result, service, kind='request', actor='A', peer='B', force=False):
    if service == 'civ': return civilian['send'](result, 'com', kind, actor, peer, force)
    return extended['send'](result, 'com_mil', kind, actor, peer, force)

def response(result, service, kind='request', actor='A', peer='B', accepted=True):
    if service == 'civ': return civilian['response'](result, 'com', kind, accepted, actor, peer)
    return extended['response'](result, 'com_mil', kind, accepted, actor, peer)

def revoke(result, service, provider='B', recipient='A'):
    if service == 'civ': civilian['effect'](result, 'revoke_civ_com_access', actor=provider, partner=recipient)
    else: extended['effect'](result, 'com_mil', 'revoke', actor=provider, peer=recipient)

def variables(result, actor): return result['countries'][actor]['variables']

def assert_num(actual, expected, message):
    assert model['compare'](actual, '=', expected), (message, actual, expected)

def all_fields(result, service, actor='A', base=False):
    return {factor: variables(result, actor)['var_COM_' + service + '_' + factor + ('_base' if base else '')] for factor in FACTORS[service]}

def expected_fields(result, service, actor, bonus, borrowed=()):
    idx = variables(result, actor)['var_COM_' + service + '_system_idx']
    expected = {}
    for factor in FACTORS[service]:
        nominal = result['global']['arrays']['COM_' + service + '_' + factor + '_max_array']
        minimum = result['global']['arrays']['COM_' + service + '_' + factor + '_min_array']
        base = max(nominal[idx] * bonus, minimum[idx])
        total = base + sum(value for provider_idx, provider_bonus in borrowed for value in (max(nominal[provider_idx] * provider_bonus, minimum[provider_idx]),))
        highest = max((provider_idx for provider_idx, provider_bonus in borrowed), default=-1)
        expected[factor] = min(total, nominal[highest]) if highest >= 0 else total
    return expected

def assert_fields(result, service, actor, expected, base=False):
    actual = all_fields(result, service, actor, base)
    for factor, value in expected.items(): assert_num(actual[factor], value, (service, actor, factor))

def assert_fresh_provider(result, service, provider, receivers, bonus):
    v = variables(result, provider)
    assert_num(v['var_COM_' + service + '_receiver_num'], receivers, 'COM provider retained stale receiver load')
    assert_num(v['var_sat_network_traffic_' + service], receivers / 1000, 'COM provider traffic not refreshed')
    assert_num(v['var_COM_' + service + '_sat_system_bonus'], bonus, 'COM provider coverage/load bonus not refreshed')
    assert_fields(result, service, provider, expected_fields(result, service, provider, bonus), True)

def projected(result, service, provider='B', recipient='A'):
    result['temp'] = {}
    return trigger([('NOT_share_COM_' + service + '_satellites_above_network_traffic_limit', '=', 'yes')], result, context(provider, scope=recipient))

def cooldown_modifier(service):
    body = one(actions, 'revoke_' + service + '_com_access')
    matches = [val for name, op, val in one(body, 'ai_desire') if name == 'modifier' and any(k == 'add' and float(v) == -1000 for k, o, v in val)]
    assert len(matches) == 1
    return matches[0]

def cooldown_score(result, service, provider='B', recipient='A'):
    result['temp'] = {}
    body = cooldown_modifier(service)
    return -1000 if trigger([row for row in body if row[0] != 'add'], result, context(provider, scope=recipient)) else 0

def network_refresh(result, actor='A', root=None, temporary=None):
    result['temp'] = dict(temporary or {})
    ctx = context(actor) if root is None else context(root, scope=actor)
    execute([('eon_sat_com_network_refresh', '=', 'yes')], result, ctx)

def inactive_world(result):
    return {actor: {'variables': {key: deepcopy(value) for key, value in data['variables'].items()
                                if not key.startswith(('var_COM_', 'var_treaty_COM_', 'var_sat_network_traffic_', 'temp_COM_', 'eon_sat_com_'))},
                    'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_sat_com_', 'recently_accepted_mil_com_', 'recently_revoke_', 'recently_offer_'))},
                    'wars': deepcopy(data['wars'])}
            for actor, data in result['countries'].items()}

# Focused actual-source regressions: ROOT must observe RED before game edits.
focus = family_filter = None
if len(sys.argv) in (3, 5):
    assert sys.argv[1] == '--focus'; focus = sys.argv[2]
    if len(sys.argv) == 5: assert sys.argv[3] == '--family'; family_filter = sys.argv[4]
assert focus in (None, 'accepted', 'revoke', 'daily', 'war_load', 'typed_flags', 'typed_read', 'projected_gap', 'projected_existing', 'projected_zero', 'zero_cap', 'congested', 'native_prev')
assert family_filter in (None, 'mil', 'civ')

if focus in (None, 'native_prev'):
    result = state(); ctx = context('D', scope='C', previous=('B', 'A', 'D'))
    result['countries']['A']['arrays']['fixture_array'] = [3, 5]
    assert model['value'](result, ctx, 'PREV.PREV.fixture_array^1') == 5
    assert model['value'](result, ctx, 'PREV.PREV.id') == 'A'
    assert model['value'](result, ctx, 'PREV.PREV.PREV.id') == 'D'
    execute([('add_to_array', '=', [('array', '=', 'PREV.PREV.fixture_array'), ('value', '=', 7)]),
             ('set_variable', '=', [('PREV.PREV.fixture_variable', '=', 9)])], result, ctx)
    assert result['countries']['A']['arrays']['fixture_array'] == [3, 5, 7]
    assert variables(result, 'A')['fixture_variable'] == 9
    assert 'PREV.fixture_array' not in result['countries']['B']['arrays']
    assert variables(result, 'B').get('PREV.fixture_variable') is None
    adapter_cases['compound_previous_frame_read_write_preserves_current_and_native_root'] += 1
    try: model['value'](result, context('D', scope='C', previous=('B',)), 'PREV.PREV.fixture_variable')
    except AssertionError: pass
    else: raise AssertionError('Missing native previous frame silently resolved an unrelated country')
    adapter_cases['compound_previous_frame_missing_stack_fails_closed'] += 1

for service in ('mil', 'civ'):
    if family_filter and service != family_filter: continue
    if focus in (None, 'accepted'):
        for kind in ('request', 'offer'):
            result, provider, recipient = network(service, kind)
            assert send(result, service, kind)
            assert response(result, service, kind)
            assert_fresh_provider(result, service, provider, 1700, .3)
            assert_fields(result, service, recipient, expected_fields(result, service, recipient, .5, ((3, .3),)))
            assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1, ((3, .3),)))
            groups['native_request_offer_refresh_provider_and_all_existing_clients_before_aggregation'] += 1
    if focus in (None, 'revoke'):
        result, provider, recipient = network(service)
        seed(result, service, recipient, provider)
        for actor in result['countries']: physical(result, actor)
        for actor in result['countries']: aggregate(result, actor)
        revoke(result, service, provider, recipient)
        assert_fresh_provider(result, service, provider, 200, 1)
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1, ((3, 1),)))
        assert_fields(result, service, recipient, expected_fields(result, service, recipient, .5))
        groups['native_revoke_recovers_provider_own_base_and_remaining_client_immediately'] += 1
    if focus in (None, 'daily'):
        result, provider, recipient = network(service)
        variables(result, 'C')['num_battalions'] = 1500
        variables(result, 'C')['num_controlled_states'] = 15
        extended['hook'](result, actor='C')
        assert_fresh_provider(result, service, provider, 1600, .4)
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', .5, ((3, .4),)))
        groups['daily_native_client_getter_changes_refresh_incoming_provider_and_client'] += 1
    if focus in (None, 'war_load'):
        result, provider, recipient = network(service)
        result['countries'][provider]['wars'].add('C'); result['countries']['C']['wars'].add(provider)
        extended['hook'](result, actor=provider)
        assert_fresh_provider(result, service, provider, 100, 1)
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1))
        assert result['countries'][provider]['arrays']['COM_' + service + '_treaty_array'] == ['C']
        groups['dormant_direct_war_consent_has_no_provider_load_and_no_borrowed_benefit'] += 1
    if focus in (None, 'typed_flags'):
        for kind in ('request', 'offer'):
            result, provider, recipient = network(service, kind, existing=False)
            assert send(result, service, kind) and response(result, service, kind)
            expected = 'eon_sat_com_' + service + '_accepted@B'
            assert expected in result['countries']['A']['flags'], ('Accepted COM callback did not set its typed family/actor flag', service, kind)
            assert not any(flag.startswith('recently_accepted_mil_com_@') for actor in result['countries'].values() for flag in actor['flags'])
            assert not any(flag.startswith('eon_sat_com_') and '_accepted@' in flag for actor, data in result['countries'].items() if actor != 'A' for flag in data['flags'])
            declarations = [entry for entry in result.get('timer_declarations', []) if entry[1] == expected]
            assert declarations == [('A', expected, 180)]
            helper = 'eon_sat_com_' + ('mil_' if service == 'mil' else '') + 'accept_' + kind
            def flag_nodes(nodes):
                found = []
                for key, op, body in nodes:
                    if key == 'set_country_flag' and isinstance(body, list) and one(body, 'flag') == 'eon_sat_com_' + service + '_accepted@PREV': found.append(body)
                    elif isinstance(body, list): found.extend(flag_nodes(body))
                return found
            flag = flag_nodes(model['effects'][helper]); assert len(flag) == 1
            assert float(one(flag[0], 'value')) == 1 and float(one(flag[0], 'days')) == 180
            groups['four_native_success_callbacks_write_only_actor_owned_typed180day_cooldown'] += 1
    if focus in (None, 'typed_read'):
        result = state()
        result['countries']['B']['flags'].add('eon_sat_com_' + service + '_accepted@A')
        assert cooldown_score(result, service) == -1000, ('Typed cooldown was not read by its native AI modifier', service)
        assert cooldown_score(result, 'civ' if service == 'mil' else 'mil') == 0
        groups['native_revoke_ai_typed_flags_affect_only_their_own_family'] += 1
    if focus in (None, 'projected_gap'):
        result = state()
        variables(result, 'B').update({'var_COM_' + service + '_receiver_cap': 100 if service == 'mil' else 1000,
            'var_COM_' + service + '_receiver_num': 110 if service == 'mil' else 1100,
            'var_sat_network_traffic_' + service: 1.1})
        variables(result, 'A').update(num_battalions=40, num_controlled_states=4)
        assert projected(result, service), ('Projected overload between current traffic1 and1.249 was missed', service)
        groups['native_ai_checks_prospective_traffic_even_inside_existing_current_traffic_gap'] += 1
    if focus in (None, 'projected_existing'):
        result = state(); variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
        physical(result, 'B'); seed(result, service, 'A', 'B')
        variables(result, 'B').update({'var_COM_' + service + '_receiver_cap': 100 if service == 'mil' else 200,
            'var_COM_' + service + '_receiver_num': 80 if service == 'mil' else 160,
            'var_sat_network_traffic_' + service: .8})
        variables(result, 'A').update(num_battalions=50, num_controlled_states=1)
        assert not projected(result, service), ('Existing active client was counted twice in projected provider load', service)
        groups['native_ai_does_not_double_count_an_existing_reciprocal_eligible_client'] += 1
    if focus in (None, 'projected_zero'):
        result = state(); variables(result, 'B')['var_COM_' + service + '_receiver_cap'] = 0
        assert projected(result, service)
        groups['native_ai_retains_explicit_zero_capacity_overload_without_division'] += 1
    if focus in (None, 'zero_cap'):
        result = state(); variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
        result['countries']['B']['arrays']['COM_satellite_array'] = [0] * 8
        seed(result, service, 'A', 'B')
        for actor in result['countries']: physical(result, actor)
        aggregate(result, 'A')
        assert_num(variables(result, 'B')['var_COM_' + service + '_receiver_num'], 100, 'Higher-tier zero-capacity dormant consent still consumed provider receivers')
        assert_fields(result, service, 'A', expected_fields(result, service, 'A', 1))
        assert result['countries']['A']['arrays']['COM_' + service + '_access_array'] == ['B']
        assert result['countries']['B']['arrays']['COM_' + service + '_treaty_array'] == ['A']
        groups['higher_tier_zero_capacity_consent_is_retained_dormant_without_load_or_foreign_base'] += 1
    if focus in (None, 'congested'):
        result = state(); variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
        variables(result, 'A').update(num_battalions=3000, num_controlled_states=30)
        seed(result, service, 'A', 'B')
        physical(result, 'B'); aggregate(result, 'A')
        assert_num(variables(result, 'B')['var_COM_' + service + '_receiver_cap'], 1000, 'Congested native capacity changed')
        assert_num(variables(result, 'B')['var_COM_' + service + '_receiver_num'], 3100, 'Positive-capacity bonus0 provider lost client load and could oscillate')
        assert_num(variables(result, 'B')['var_COM_' + service + '_sat_system_bonus'], 0, 'Overloaded positive-capacity native bonus changed')
        groups['positive_capacity_overloaded_bonus_zero_keeps_active_client_load'] += 1

    if focus is None:
        # The three independent flag facts have eight distinct truth rows.
        for legacy in (False, True):
            for military in (False, True):
                for civil in (False, True):
                    result = state()
                    for present, name in ((legacy, 'recently_accepted_mil_com_@A'),
                                          (military, 'eon_sat_com_mil_accepted@A'), (civil, 'eon_sat_com_civ_accepted@A')):
                        if present: result['countries']['B']['flags'].add(name)
                    assert cooldown_score(result, service) == (-1000 if legacy or (military if service == 'mil' else civil) else 0)
                    groups['native_ai_legacy_and_two_typed_flag_truth_table_retains_single_weight'] += 1
        for wrong in ('other actor', 'reverse pair', 'other partner'):
            result = state()
            actor, partner = ('C', 'A') if wrong == 'other actor' else ('A', 'B') if wrong == 'reverse pair' else ('B', 'C')
            result['countries'][actor]['flags'].add('eon_sat_com_' + service + '_accepted@' + partner)
            assert cooldown_score(result, service) == 0
            groups['typed_revoke_cooldown_respects_original_actor_and_exact_partner'] += 1
        for kind in ('request', 'offer'):
            result, provider, recipient = network(service, kind, existing=False)
            legacy = 'recently_accepted_mil_com_@B'
            result['countries']['A']['flags'].add(legacy)
            result['timer_declarations'] = [('A', legacy, 20)]
            assert send(result, service, kind) and response(result, service, kind)
            assert legacy in result['countries']['A']['flags']
            assert [row for row in result['timer_declarations'] if row[1] == legacy] == [('A', legacy, 20)]
            original = list(result['timer_declarations'])
            response(result, service, kind)
            assert result['timer_declarations'] == original
            groups['legacy_declared_remaining_window_is_not_copied_renewed_and_consumed_success_cannot_renew_typed_flag'] += 1
            # A typed opposite-family flag remains a soft AI fact for humans.
            result, provider, recipient = network(service, kind, existing=False)
            result['countries']['A']['flags'].update({'eon_sat_com_mil_accepted@B', 'eon_sat_com_civ_accepted@B', legacy})
            assert send(result, service, kind)
            response(result, service, kind, accepted=False)
            assert not any('accepted@' in row[1] for row in result.get('timer_declarations', []))
            groups['native_human_admission_does_not_turn_accepted_ai_cooldown_into_a_hard_gate'] += 1
        for alteration in ('rejected', 'withdrawn', 'wrong peer', 'wrong kind', 'expired'):
            result, provider, recipient = network(service, existing=False)
            assert send(result, service)
            if alteration == 'withdrawn':
                if service == 'civ': assert civilian['withdraw'](result, 'com')
                else: assert extended['withdraw'](result, 'com_mil')
            elif alteration == 'expired': result['countries']['A']['flags'].discard('eon_sat_com_' + ('mil_' if service == 'mil' else '') + 'window')
            response(result, service, 'offer' if alteration == 'wrong kind' else 'request', peer='C' if alteration == 'wrong peer' else 'B', accepted=alteration != 'rejected')
            assert not any(flag.startswith('eon_sat_com_') and '_accepted@' in flag for data in result['countries'].values() for flag in data['flags'])
            assert not any('accepted@' in row[1] for row in result.get('timer_declarations', []))
            groups['rejected_withdrawn_expired_wrong_identity_callbacks_do_not_install_cooldown'] += 1

        # Target already present is counted once even inside the old traffic gap.
        for mode, expected in (('active current1.1', False), ('unilateral', True), ('direct war dormant', True), ('below recipient dormant', True)):
            result = state(); variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
            physical(result, 'B'); seed(result, service, 'A', 'B')
            if mode == 'unilateral': result['countries']['B']['arrays']['COM_' + service + '_treaty_array'].clear()
            elif mode == 'direct war dormant': result['countries']['B']['wars'].add('A'); result['countries']['A']['wars'].add('B')
            elif mode == 'below recipient dormant': variables(result, 'A')['var_COM_' + service + '_system_idx'] = 5
            variables(result, 'B').update({'var_COM_' + service + '_receiver_cap': 100 if service == 'mil' else 1000,
                'var_COM_' + service + '_receiver_num': 110 if service == 'mil' else 1100,
                'var_sat_network_traffic_' + service: 1.1})
            variables(result, 'A').update(num_battalions=30, num_controlled_states=3)
            assert projected(result, service) == expected, (service, mode)
            groups['native_projected_ai_counts_only_existing_reciprocal_live_eligible_clients_once'] += 1
        for proposed_ratio, expected in ((1.249, False), (1.25, True)):
            result = state(); variables(result, 'B').update({'var_COM_' + service + '_receiver_cap': 1000,
                'var_COM_' + service + '_receiver_num': proposed_ratio * 1000 - (100 if service == 'civ' else 10),
                'var_sat_network_traffic_' + service: 0})
            variables(result, 'A').update(num_battalions=10, num_controlled_states=1)
            assert projected(result, service) == expected
            groups['native_projected_threshold_retains_literal_strict1point249_boundary'] += 1

        # Upper-tier nonbinding consent remains dormant with no physical cap;
        # positive-capacity congestion keeps load, avoiding oscillation.
        result = state(); variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
        seed(result, service, 'A', 'B'); result['countries']['B']['arrays']['COM_satellite_array'] = [0] * 8
        network_refresh(result, 'A')
        assert_fields(result, service, 'A', expected_fields(result, service, 'A', 1))
        result['countries']['B']['arrays']['COM_satellite_array'][3] = 10
        network_refresh(result, 'A')
        assert_fields(result, service, 'A', expected_fields(result, service, 'A', 1, ((3, 1),)))
        revoke(result, service)
        result['countries']['B']['arrays']['COM_satellite_array'] = [0] * 8
        network_refresh(result, 'A')
        result['countries']['B']['arrays']['COM_satellite_array'][3] = 10
        network_refresh(result, 'A')
        assert result['countries']['A']['arrays']['COM_' + service + '_access_array'] == []
        assert_fields(result, service, 'A', expected_fields(result, service, 'A', 1))
        groups['physical_capacity_recovery_reactivates_only_retained_consent_never_revoked_identity'] += 1
        for kind in ('request', 'offer'):
            result, provider, recipient = network(service, kind, existing=False)
            variables(result, provider)['var_COM_' + service + '_system_idx'] = 0
            assert send(result, service, kind)
            result['countries'][provider]['arrays']['COM_satellite_array'] = [0] * 8
            response(result, service, kind)
            assert result['countries'][recipient]['arrays']['COM_' + service + '_access_array'] == []
            assert not any('_accepted@' in row[1] for row in result.get('timer_declarations', []))
            groups['actual_callback_refresh_detects_physical_first_tier_loss_despite_positive_cached_count'] += 1
            result, provider, recipient = network(service, kind, existing=False)
            variables(result, provider)['var_COM_' + service + '_system_idx'] = 0
            assert send(result, service, kind)
            result['countries'][provider]['arrays']['COM_satellite_array'] = [0] * 8
            extended['hook'](result, actor='A')
            pending_prefix = 'eon_sat_com_' + ('mil_' if service == 'mil' else '')
            assert pending_prefix + 'cancelled' in result['countries']['A']['flags']
            result['countries'][provider]['arrays']['COM_satellite_array'][3] = 10
            response(result, service, kind)
            assert result['countries'][recipient]['arrays']['COM_' + service + '_access_array'] == []
            assert send(result, service, kind) and response(result, service, kind)
            assert result['countries'][recipient]['arrays']['COM_' + service + '_access_array'] == [provider]
            groups['daily_fresh_first_tier_loss_latches_pending_cancel_until_original_response_then_allows_recovery'] += 1

        for subject in (False, True):
            for extended_first in (False, True):
                for victim in ('B', 'C'):
                    result, provider, recipient = network(service)
                    seed(result, service, recipient, provider); network_refresh(result, recipient)
                    # Explicit native preflip existence remains true.
                    extended['hook'](result, victim=victim, subject=subject, extended_first=extended_first)
                    if victim == provider:
                        assert result['countries'][recipient]['arrays']['COM_' + service + '_access_array'] == []
                        assert_fields(result, service, recipient, expected_fields(result, service, recipient, .5))
                        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1))
                    else:
                        assert result['countries'][provider]['arrays']['COM_' + service + '_treaty_array'] == [recipient]
                        assert_fresh_provider(result, service, provider, 1600, .4)
                        assert_fields(result, service, recipient, expected_fields(result, service, recipient, .5, ((3, .4),)))
                    groups['both_annex_hooks_and_hook_orders_refresh_survivor_load_base_without_preflip_identity_leak'] += 1

        # Borrowed totals are never re-lent: B's own base8 differs from its
        # borrowed aggregate30, so the native highest cap cannot hide leakage.
        result = state()
        for actor in result['countries']: result['countries'][actor]['arrays']['COM_satellite_array'] = [0] * 7 + [10]
        variables(result, 'A')['var_COM_' + service + '_system_idx'] = 5
        variables(result, 'B')['var_COM_' + service + '_system_idx'] = 3
        variables(result, 'C').update(num_battalions=1500, num_controlled_states=15)
        seed(result, service, 'B', 'A'); seed(result, service, 'C', 'B')
        network_refresh(result, 'B', root='D')
        assert_fresh_provider(result, service, 'B', 1600, .4)
        assert_fields(result, service, 'B', expected_fields(result, service, 'B', .4, ((5, 1),)))
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', .5, ((3, .4),)))
        groups['foreign_borrowed_totals_are_not_re_lent_along_a_chain_with_unrelated_native_root'] += 1
        result = state()
        for actor in ('A', 'B'): variables(result, actor)['var_COM_' + service + '_system_idx'] = 3
        variables(result, 'A').update(num_battalions=1500, num_controlled_states=15)
        seed(result, service, 'A', 'B'); seed(result, service, 'B', 'A')
        network_refresh(result, 'A')
        for actor in ('A', 'B'): assert_fields(result, service, actor, expected_fields(result, service, actor, .4, ((3, .4),)))
        original = {actor: (all_fields(result, service, actor), all_fields(result, service, actor, True)) for actor in result['countries']}
        network_refresh(result, 'B')
        assert original == {actor: (all_fields(result, service, actor), all_fields(result, service, actor, True)) for actor in result['countries']}
        groups['reciprocal_cycles_use_all_own_bases_before_aggregation_and_refresh_idempotently'] += 1

        result, provider, recipient = network(service)
        variables(result, 'D')['var_COM_' + service + '_system_idx'] = 5
        result['countries']['D']['arrays']['COM_satellite_array'] = [0] * 7 + [10]
        variables(result, 'D').update(num_battalions=1500, num_controlled_states=15)
        seed(result, service, 'C', 'D')
        for factor in FACTORS[service]:
            variables(result, 'D')['var_COM_' + service + '_' + factor + '_base'] = 999
            variables(result, 'D')['var_COM_' + service + '_' + factor] = 999
        assert send(result, service) and response(result, service)
        assert_fields(result, service, 'D', expected_fields(result, service, 'D', .4), True)
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1, ((3, .3), (5, .4))))
        assert all(value == 999 for value in all_fields(result, service, 'D').values())
        groups['other_incoming_provider_is_synced_leaf_only_before_affected_client_aggregation'] += 1

        result, provider, recipient = network(service)
        gui = result['countries'][provider]['arrays']
        gui['COM_' + service + '_systems_array'] = [1]
        for factor in FACTORS[service]:
            gui['COM_' + service + '_' + factor + '_array'] = [result['global']['arrays']['COM_' + service + '_' + factor + '_max_array'][1]]
        maximum = result['global']['arrays']['COM_sat_system_max_array'][0]
        result['temp'] = {'i': 0, 'eon_sat_removed_country': 0}
        execute([('COM_' + service + '_button_update', '=', 'yes')], result, context('D', scope=provider))
        assert variables(result, provider)['var_COM_' + service + '_system_idx'] == 1
        assert variables(result, provider)['var_COM_' + service + '_sat_system_max'] == maximum
        assert gui['COM_' + service + '_systems_array'] == []
        bonus = min(10 / maximum, 1)
        assert_fields(result, service, provider, expected_fields(result, service, provider, bonus), True)
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1, ((1, bonus),)))
        groups['both_actual_native_gui_endpoints_refresh_clients_with_current_this_and_literal_selected_maximum'] += 1

        result, provider, recipient = network(service)
        result['global']['arrays']['fixture_actors'] = ['A', 'C']
        result['global']['arrays']['fixture_trace'] = []
        result['temp'] = {'eon_sat_removed_country': 0}
        execute([('for_each_scope_loop', '=', [
            ('array', '=', 'global.fixture_actors'), ('value', '=', 'fixture_actor'), ('index', '=', 'fixture_index'),
            ('eon_sat_com_network_refresh', '=', 'yes'),
            ('add_to_array', '=', [('array', '=', 'global.fixture_trace'), ('value', '=', 'THIS.id')]),
            ('add_to_array', '=', [('array', '=', 'global.fixture_trace'), ('value', '=', 'fixture_index')]),
            ('set_variable', '=', [('fixture_actor_marker', '=', 'fixture_actor')])])], result, context('D'))
        assert result['global']['arrays']['fixture_trace'] == ['A', 0, 'C', 1]
        assert variables(result, 'A')['fixture_actor_marker'] == 'A' and variables(result, 'C')['fixture_actor_marker'] == 'C'
        assert_fields(result, service, 'C', expected_fields(result, service, 'C', 1, ((3, 1),)))
        groups['native_outer_custom_index_value_and_country_frame_survive_nested_network_scratch'] += 1

        for invalid in (-1, 3.5, 8):
            result = state(); other = 'civ' if service == 'mil' else 'mil'
            variables(result, 'A')['var_COM_' + service + '_system_idx'] = invalid
            variables(result, 'A')['var_COM_' + other + '_system_idx'] = 3
            for factor in FACTORS[service]: variables(result, 'A')['var_COM_' + service + '_' + factor + '_base'] = 77
            result['temp'] = {}; execute([('eon_sat_com_sync_own', '=', 'yes')], result, context('A'))
            assert all(value == 77 for value in all_fields(result, service, 'A', True).values())
            assert_fields(result, other, 'A', expected_fields(result, other, 'A', 1), True)
            groups['invalid_selected_role_does_not_index_its_base_table_or_block_other_valid_role_calculator'] += 1

        result, provider, recipient = network(service)
        before = inactive_world(result)
        assert send(result, service) and response(result, service)
        revoke(result, service)
        assert inactive_world(result) == before
        groups['com_graph_preserves_money_debt_wars_other_native_country_facts_and_unrelated_flags'] += 1

print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'actual_source_scenarios': sum(groups.values()),
    'adapter_semantics_cases': sum(adapter_cases.values()), 'total_cases': sum(groups.values()) + sum(adapter_cases.values()),
    'groups': dict(groups), 'adapter_groups': dict(adapter_cases),
    'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
    'proof_scope': 'bounded ordered actual-source COM graph and native cooldown/AI modifiers; not HOI4 runtime'}, indent=2))
