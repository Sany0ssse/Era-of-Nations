"""Ordered actual-source proof for remaining satellite access and COM traffic."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '150cb6f114f7f8896495f57206a1a854af06e056'
groups = Counter()
SOURCE_PATHS = (
    'common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt',
    'common/scripted_effects/00_missiles_scripted_effects.txt',
    'common/scripted_effects/eon_satellite_extended_effects.txt',
    'common/scripted_triggers/eon_satellite_extended_triggers.txt',
    'common/decisions/eon_satellite_extended_decisions.txt',
    'common/decisions/categories/eon_satellite_extended_categories.txt',
    'common/on_actions/eon_satellite_extended_on_actions.txt',
    'localisation/english/eon_satellite_extended_l_english.yml',
    'localisation/russian/eon_satellite_extended_l_russian.yml',
)

# Package12 definitions only; its 106 scenarios run separately in its runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_12/test_satellites.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# Focused actual-source regressions. Root must observe RED before gameplay edits.'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'remaining_satellite_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch, read = (source[name] for name in ('ast', 'one', 'context', 'switch', 'read'))
trigger, execute = source['trigger'], source['execute']
actions = source['actions']

FAMILIES = {
    'gnss_mil': ('GNSS', 'mil', 'pending_mil_access_country', ('army_speed_factor', 'air_cas_efficiency', 'air_nav_efficiency', 'air_strategic_bomber_bombing_factor', 'positioning', 'naval_hit_chance')),
    'com_mil': ('COM', 'mil', 'pending_mil_com_access_country', ('max_command_power', 'army_org_factor', 'planning_speed', 'air_escort_efficiency', 'air_intercept_efficiency', 'naval_coordination')),
    'spy_mil': ('SPY', 'mil', 'pending_mil_spy_access_country', ('max_planning_factor', 'recon_factor', 'air_weather_penalty', 'spotting_chance', 'convoy_raiding_efficiency_factor', 'convoy_escort_efficiency')),
    'spy_civ': ('SPY', 'civ', 'pending_civ_spy_access_country', ('research_speed_factor', 'civilian_intel_factor', 'army_intel_factor', 'navy_intel_factor', 'airforce_intel_factor', 'root_out_resistance_effectiveness_factor')),
}
missile_effects = ast(read('common/scripted_effects/00_missiles_scripted_effects.txt'))
for upper, service, pointer, factors in FAMILIES.values():
    for name in ('add_access_' + upper + '_' + service + '_vars', 'add_offer_access_' + upper + '_' + service + '_vars'):
        model['effects'][name] = one(missile_effects, name)
for registry, path in (('effects', 'common/scripted_effects/eon_satellite_extended_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_satellite_extended_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, operator, body in ast(read(path))}
        for key, body in additions.items():
            assert key not in model[registry] or model[registry][key] == body, 'Extended helpers overwrite a different helper'
        model[registry].update(additions)

def identity(family, kind):
    upper, service, pointer, factors = FAMILIES[family]
    return kind + '_' + service + '_' + upper.lower() + '_access'

def literal_caps():
    result = {}
    body = one(ast(read('common/scripted_effects/00_missiles_models.txt')), 'set_all_sat_system_tech')
    for key, operator, value in body:
        if key != 'add_to_array': continue
        assert len(value) == 1
        field, op, literal = value[0]
        if field.startswith('global.') and field.endswith('_max_array'):
            result.setdefault(field.removeprefix('global.'), []).append(float(literal))
    for upper, service, pointer, factors in FAMILIES.values():
        for factor in factors: assert len(result[upper + '_' + service + '_' + factor + '_max_array']) == 8
    return result

def state():
    result = source['state']()
    result['global']['arrays'].update(literal_caps())
    for actor, country in result['countries'].items():
        for upper, service, pointer, factors in FAMILIES.values():
            prefix = upper + '_' + service
            country['variables']['var_' + prefix + '_system_idx'] = 0 if actor == 'A' else 3
            for suffix in ('access_array', 'treaty_array', 'access_system_idx_array'): country['arrays'][prefix + '_' + suffix] = []
            for factor in factors:
                field = 'var_' + prefix + '_' + factor
                country['variables'][field + '_base'] = -.01 if actor == 'A' and factor == 'air_weather_penalty' else -.03 if factor == 'air_weather_penalty' else .01 if actor == 'A' else .03
                country['variables'][field] = country['variables'][field + '_base']
        country['variables'].update(num_battalions=0, num_ships=0, num_deployed_planes=0, var_COM_mil_sat_system_max=10)
        country['arrays']['COM_satellite_array'] = [0, 0, 0, 10, 0, 0, 0, 0]
        country['arrays']['COM_sat_receiver_tech_array'] = [100] * 8
    for actor in result['countries']:
        result['temp'] = {}
        execute([('eon_sat_com_sync_own', '=', 'yes'), ('eon_sat_com_apply_civ', '=', 'yes'), ('eon_sat_com_apply_mil', '=', 'yes')], result, context(actor))
    return result

def effect(result, family, kind='request', entry='complete_effect', actor='A', peer='B'):
    result['temp'] = {}
    body = one(actions, identity(family, kind))
    entries = [nodes for key, operator, nodes in body if key == entry]
    assert len(entries) <= 1
    if entries: execute(entries[0], result, context(actor, scope=peer))

def arrays(result, family, actor='A'):
    upper, service, pointer, factors = FAMILIES[family]
    prefix = upper + '_' + service
    return (result['countries'][actor]['arrays'][prefix + '_access_array'],
            result['countries'][actor]['arrays'][prefix + '_access_system_idx_array'])

def helper(result, name, actor='A', peer=None, temporary=None):
    result['temp'] = dict(temporary or {})
    ctx = context(actor) if peer is None else switch(context(actor, scope=peer), actor)
    execute([(name, '=', 'yes')], result, ctx)

def pending(result, family, actor='A'):
    variables = result['countries'][actor]['variables']
    return tuple(variables.get('eon_sat_' + family + '_' + field, 0) for field in ('partner', 'kind', 'level'))

def send(result, family, kind='request', actor='A', peer='B', force=False):
    body = one(actions, identity(family, kind)); result['temp'] = {}
    ready = True
    for key, operator, nodes in body:
        if key in ('allowed', 'visible', 'selectable', 'can_be_sent'):
            ready = ready and trigger(nodes, result, context(actor, scope=peer))
    assert float(one(body, 'cost')) == 0
    if ready or force: effect(result, family, kind, 'on_sent_effect', actor, peer)
    return ready

def response(result, family, kind='request', accepted=True, actor='A', peer='B'):
    result['temp'] = {}
    authorized = not accepted or trigger([('eon_sat_' + family + '_' + kind + '_authorized', '=', 'yes')],
                                        result, switch(context(actor, scope=peer), actor))
    # Deliver the actual native callback. The script independently closes a
    # consumed invalid answer; no synthetic can_be_accepted guard is invented.
    declarations = len(result.get('timer_declarations', []))
    effect(result, family, kind, 'complete_effect' if accepted else 'reject_effect', actor, peer)
    if accepted and family == 'com_mil':
        return (actor, 'eon_sat_com_mil_accepted@' + peer, 180) in result.get('timer_declarations', [])[declarations:]
    return authorized

def prepare(result, family, kind='request', actor='A', peer='B'):
    upper, service, pointer, factors = FAMILIES[family]
    if kind == 'offer':
        result['countries'][actor]['variables']['var_' + upper + '_' + service + '_system_idx'] = 3
        result['countries'][peer]['variables']['var_' + upper + '_' + service + '_system_idx'] = 0
    assert send(result, family, kind, actor, peer)

def withdraw(result, family, actor='A', force=False):
    upper, service, pointer, factors = FAMILIES[family]
    decision_nodes = ast(read('common/decisions/eon_satellite_extended_decisions.txt'))
    wanted = 'eon_withdraw_' + service + '_' + upper.lower() + '_proposal'
    def matches(nodes):
        found = []
        for name, op, body in nodes:
            if name == wanted: found.append(body)
            if isinstance(body, list): found.extend(matches(body))
        return found
    matched = matches(decision_nodes); assert len(matched) == 1
    body = matched[0]; assert float(one(body, 'cost')) == 0
    result['temp'] = {}; ctx = context(actor)
    ready = all(trigger(one(body, key), result, ctx) for key in ('allowed', 'visible', 'available'))
    if ready or force: execute(one(body, 'complete_effect'), result, ctx)
    return ready

def hook(result, actor='A', victim=None, subject=False, extended_first=True):
    current = one(ast(read('common/on_actions/eon_satellite_extended_on_actions.txt')), 'on_actions')
    previous = one(ast(read('common/on_actions/eon_satellite_on_actions.txt')), 'on_actions')
    ctx = context(actor) if victim is None else context(victim, 'D') if subject else context('D', victim)
    name = 'on_daily' if victim is None else 'on_subject_annexed' if subject else 'on_annex'
    for hooks in ((current, previous) if extended_first else (previous, current)):
        result['temp'] = {}
        execute(one(one(hooks, name), 'effect'), result, ctx)

def seed_consent(result, family, recipient='A', provider='B', copies=1):
    upper, service, pointer, factors = FAMILIES[family]
    prefix = upper + '_' + service
    result['countries'][recipient]['arrays'][prefix + '_access_array'].extend([provider] * copies)
    result['countries'][recipient]['arrays'][prefix + '_access_system_idx_array'].extend([3] * copies)
    result['countries'][provider]['arrays'][prefix + '_treaty_array'].extend([recipient] * copies)

def values(result, family, actor='A', base=False):
    upper, service, pointer, factors = FAMILIES[family]
    return {factor: result['countries'][actor]['variables']['var_' + upper + '_' + service + '_' + factor + ('_base' if base else '')]
            for factor in factors}

def expected_gain(result, family, recipient='A', providers=('B',)):
    upper, service, pointer, factors = FAMILIES[family]
    expected = values(result, family, recipient, True)
    level = result['countries'][recipient]['variables']['var_' + upper + '_' + service + '_system_idx']
    eligible = [provider for provider in providers if result['countries'][provider]['exists']
                and recipient not in result['countries'][provider]['wars']
                and result['countries'][provider]['variables']['var_' + upper + '_' + service + '_system_idx'] in range(0, 8)
                and (result['countries'][provider]['variables']['var_' + upper + '_' + service + '_system_idx'] > 0
                     or result['countries'][provider]['variables'].get('var_' + upper + '_' + service + '_sat_system_num', 0) > 0)
                and level in range(0, 8) and result['countries'][provider]['variables']['var_' + upper + '_' + service + '_system_idx'] >= level]
    if eligible:
        highest = max(result['countries'][provider]['variables']['var_' + upper + '_' + service + '_system_idx'] for provider in eligible)
        for factor in factors:
            total = expected[factor] + sum(values(result, family, provider, True)[factor] for provider in eligible)
            bound = result['global']['arrays'][upper + '_' + service + '_' + factor + '_max_array'][highest]
            expected[factor] = max(total, bound) if factor == 'air_weather_penalty' else min(total, bound)
    return expected

def assert_values(result, family, expected, actor='A'):
    actual = values(result, family, actor)
    assert all(model['compare'](actual[field], '=', wanted) for field, wanted in expected.items()), (family, actor, actual, expected)

def snapshot(result): return deepcopy(result['countries'])

def outside_extended(result):
    owned_variables = tuple('var_' + upper + '_' + service + '_' for upper, service, pointer, factors in FAMILIES.values())
    owned_arrays = tuple(upper + '_' + service + '_' for upper, service, pointer, factors in FAMILIES.values())
    pointers = {pointer for upper, service, pointer, factors in FAMILIES.values()}
    return {actor: {key: deepcopy(value) for key, value in data.items() if key not in ('variables', 'arrays', 'flags')}
            | {'variables': {key: deepcopy(value) for key, value in data['variables'].items()
                             if not key.startswith(owned_variables + ('eon_sat_',)) and key not in pointers},
               'arrays': {key: deepcopy(value) for key, value in data['arrays'].items()
                          if not key.startswith(owned_arrays + ('eon_sat_',))},
               'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_sat_', 'recently_accepted_', 'recently_revoke_'))}}
            for actor, data in result['countries'].items()}

# Initial actual-source REDs must be observed before production changes.
focus = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == '--focus' else None
available = ('duplicate', 'index', 'orphan', 'pending', 'beneficiary', 'mil_overload', 'mil_zero_cap', 'negative_cap', 'zero_max',
             'zero_level', 'zero_level_offer', 'zero_refresh', 'zero_unavailable', 'zero_lifecycle')
assert focus in (None,) + available, ('Unknown focused proof', sys.argv[1:])
selected = sys.argv[4] if len(sys.argv) == 5 and sys.argv[3] == '--family' else None
if len(sys.argv) == 5:
    focus = sys.argv[2]; assert sys.argv[1] == '--focus' and focus in available and (selected in FAMILIES or focus == 'zero_max' and selected == 'com_civ')

for family in FAMILIES:
    if selected and selected != family: continue
    upper, service, pointer, factors = FAMILIES[family]
    if focus in (None, 'zero_level', 'zero_level_offer'):
        prefix = upper + '_' + service
        for kind in ('request', 'offer'):
            if focus == 'zero_level_offer' and kind != 'offer': continue
            result = state()
            provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
            for country in (provider, recipient):
                result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
            result['countries'][provider]['variables']['var_' + prefix + '_sat_system_num'] = 2
            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)
            assert send(result, family, kind), ('Working first-tier provider was blocked by numeric level zero', family, kind)
            assert pending(result, family) == ('B', 1 if kind == 'request' else 2, 0)
            assert response(result, family, kind)
            assert arrays(result, family, recipient) == ([provider], [0])
            assert result['countries'][provider]['arrays'][prefix + '_treaty_array'] == [recipient]
            groups['four_working_first_tier_providers_with_positive_native_satellite_counts_support_request_and_offer'] += 1
    if focus in (None, 'zero_refresh'):
        result = state(); prefix = upper + '_' + service
        for country in ('A', 'B'):
            result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 2
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)
        for factor in factors:
            result['countries']['B']['variables']['var_' + prefix + '_' + factor + '_base'] = -100 if factor == 'air_weather_penalty' else 100
        seed_consent(result, family)
        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)
        expected = {factor: result['global']['arrays'][prefix + '_' + factor + '_max_array'][0] for factor in factors}
        assert_values(result, family, expected)
        assert arrays(result, family) == (['B'], [0])
        groups['four_first_tier_live_reciprocal_providers_contribute_and_clamp_all24_fields_at_actual_global_index_zero'] += 1
    if focus in (None, 'zero_unavailable'):
        prefix = upper + '_' + service
        for kind in ('request', 'offer'):
            result = state()
            provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
            for country in (provider, recipient):
                result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
                result['countries'][country]['variables']['var_' + prefix + '_sat_system_num'] = 0
                if family == 'com_mil': source['set_com_count_fixture'](result, country, 0)
            before = snapshot(result)
            assert not send(result, family, kind)
            send(result, family, kind, force=True)
            response(result, family, kind)
            assert snapshot(result) == before
            groups['first_tier_without_native_satellites_remains_unavailable_and_cached_native_click_inert'] += 1
        result = state()
        for country in ('A', 'B'):
            result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
            result['countries'][country]['variables']['var_' + prefix + '_sat_system_num'] = 0
            if family == 'com_mil': source['set_com_count_fixture'](result, country, 0)
        seed_consent(result, family)
        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)
        assert arrays(result, family) == (['B'], [0])
        assert_values(result, family, values(result, family, base=True))
        groups['first_tier_without_satellites_retains_dormant_reciprocal_consent_without_service_gain'] += 1
    if focus in (None, 'zero_lifecycle'):
        prefix = upper + '_' + service
        for kind in ('request', 'offer'):
            result = state()
            provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
            for country in (provider, recipient):
                result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
            result['countries'][provider]['variables']['var_' + prefix + '_sat_system_num'] = 2
            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)
            assert send(result, family, kind)
            result['countries'][provider]['variables']['var_' + prefix + '_sat_system_num'] = 0
            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 0)
            assert not response(result, family, kind)
            assert pending(result, family) == (0, 0, 0) and not arrays(result, family, recipient)[0]
            result['countries'][provider]['variables']['var_' + prefix + '_sat_system_num'] = 2
            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)
            assert send(result, family, kind) and response(result, family, kind)
            assert_values(result, family, expected_gain(result, family, recipient, (provider,)), recipient)
            groups['eight_first_tier_native_callbacks_recheck_satellite_count_loss_before_response_and_allow_consumed_new_round'] += 1

        result = state()
        for country in ('A', 'B'):
            result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 2
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)
        assert send(result, family)
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 0
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0)
        hook(result)
        assert pending(result, family) == ('B', 1, 0)
        assert 'eon_sat_' + family + '_cancelled' in result['countries']['A']['flags']
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 2
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)
        assert not response(result, family)
        assert not arrays(result, family)[0] and pending(result, family) == (0, 0, 0)
        assert send(result, family) and response(result, family)
        groups['first_tier_daily_count_loss_latches_cancelled_until_consumed_response_even_if_provider_recovers'] += 1

        result = state()
        for country in ('A', 'B'):
            result['countries'][country]['variables']['var_' + prefix + '_system_idx'] = 0
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 2
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)
        seed_consent(result, family)
        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)
        assert_values(result, family, expected_gain(result, family))
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 0
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0)
        hook(result)
        assert arrays(result, family) == (['B'], [0])
        assert_values(result, family, values(result, family, base=True))
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 2
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)
        hook(result)
        assert arrays(result, family) == (['B'], [0])
        assert_values(result, family, expected_gain(result, family))
        effect(result, family, 'revoke', actor='B', peer='A')
        result['countries']['B']['variables']['var_' + prefix + '_sat_system_num'] = 4
        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 4)
        hook(result)
        assert arrays(result, family) == ([], [])
        assert_values(result, family, values(result, family, base=True))
        groups['first_tier_live_count_loss_and_recovery_preserve_consent_but_explicit_revoke_does_not_revive'] += 1
    if focus in (None, 'duplicate'):
        result = state()
        effect(result, family, entry='on_sent_effect')
        effect(result, family)
        effect(result, family)
        assert arrays(result, family) == (['B'], [3]), ('Repeated callback duplicated provider', family, arrays(result, family))
        groups['four_remaining_families_accept_callback_grants_provider_once'] += 1
    if focus in (None, 'index'):
        result = state()
        for peer in ('B', 'C'):
            effect(result, family, entry='on_sent_effect', peer=peer)
            effect(result, family, peer=peer)
        result['countries']['B']['variables']['var_' + upper + '_' + service + '_system_idx'] = 5
        effect(result, family, 'revoke', actor='B', peer='A')
        assert arrays(result, family) == (['C'], [3]), ('Revoke left stale tier after provider changed level', family, arrays(result, family))
        groups['four_remaining_families_revoke_rebuilds_live_index_without_losing_equal_provider'] += 1
    if focus in (None, 'orphan'):
        result = state()
        effect(result, family, entry='on_sent_effect', peer='C')
        effect(result, family, peer='C')
        effect(result, family, 'revoke', actor='B', peer='A')
        assert arrays(result, family) == (['C'], [3]), ('Unowned revoke erased different provider tier', family, arrays(result, family))
        groups['four_remaining_families_unowned_revoke_is_inert'] += 1
    if focus in (None, 'pending'):
        result = state()
        result['countries']['A']['variables']['var_' + upper + '_' + service + '_system_idx'] = 3
        effect(result, family, 'offer', 'on_sent_effect')
        effect(result, family, 'offer', 'reject_effect')
        effect(result, family, 'offer', 'on_sent_effect', peer='C')
        effect(result, family, 'offer', 'reject_effect')
        assert result['countries']['A']['variables'].get(pointer) == 'C', ('Stale different-partner reject erased current outgoing owner', family, result['countries']['A']['variables'].get(pointer))
        groups['four_remaining_families_old_partner_response_preserves_new_partner'] += 1
    if focus in (None, 'beneficiary'):
        result = state()
        prefix = upper + '_' + service
        result['countries']['A']['variables']['var_' + prefix + '_system_idx'] = 4
        result['countries']['A']['arrays'][prefix + '_access_array'] = ['B']
        result['countries']['A']['arrays'][prefix + '_access_system_idx_array'] = [3]
        result['countries']['B']['arrays'][prefix + '_treaty_array'] = ['A']
        result['temp'] = {}
        execute([('add_access_' + prefix + '_vars', '=', 'yes')], result, context('A'))
        expected = {factor: result['countries']['A']['variables']['var_' + prefix + '_' + factor + '_base'] for factor in factors}
        assert all(model['compare'](result['countries']['A']['variables']['var_' + prefix + '_' + factor], '=', wanted) for factor, wanted in expected.items())
        result['temp'] = {}
        execute([('add_offer_access_' + prefix + '_vars', '=', 'yes')], result, switch(context('B', scope='A'), 'B'))
        actual = {factor: result['countries']['A']['variables']['var_' + prefix + '_' + factor] for factor in factors}
        assert all(model['compare'](actual[factor], '=', wanted) for factor, wanted in expected.items()), ('Offer refresh credited weaker provider because it compared provider with THIS instead of recipient', family, actual, expected)
        groups['request_and_offer_refresh_use_same_recipient_tier_eligibility'] += 1

if focus in (None, 'mil_overload', 'mil_zero_cap'):
    for proof in ('mil_overload', 'mil_zero_cap'):
        if focus is not None and focus != proof: continue
        result = state()
        country = result['countries']['A']
        country['variables'].update(var_COM_mil_system_idx=3, var_COM_civ_system_idx=3,
                                    var_sat_network_traffic_civ=0, var_COM_mil_sat_system_bonus=.8,
                                    num_battalions=1500 if proof != 'mil_zero_cap' else 0)
        if proof == 'mil_zero_cap': country['arrays']['COM_satellite_array'] = [0] * 8
        result['temp'] = {}
        execute([('update_COM_system_stats', '=', 'yes')], result, context('A'))
        variables = country['variables']
        if proof != 'mil_zero_cap':
            assert variables['var_sat_network_traffic_mil'] == 1.5 and model['compare'](variables['var_COM_mil_sat_system_bonus'], '=', .5), ('Military overload read civilian traffic and skipped penalty', variables['var_sat_network_traffic_mil'], variables['var_COM_mil_sat_system_bonus'])
            groups['military_COM_overload_penalty_uses_actual_military_traffic'] += 1
        else:
            assert variables['var_COM_mil_receiver_cap'] == 0 and variables['var_COM_mil_sat_system_bonus'] == 0, ('Zero military capacity retained stale service bonus', variables['var_COM_mil_receiver_cap'], variables['var_COM_mil_sat_system_bonus'])
            groups['zero_military_COM_capacity_resets_stale_service_bonus'] += 1

if focus in (None, 'negative_cap'):
    result = state()
    result['countries']['B']['variables']['var_SPY_mil_air_weather_penalty_base'] = -.3
    effect(result, 'spy_mil', entry='on_sent_effect')
    effect(result, 'spy_mil')
    expected = result['global']['arrays']['SPY_mil_air_weather_penalty_max_array'][3]
    actual = result['countries']['A']['variables']['var_SPY_mil_air_weather_penalty']
    assert model['compare'](actual, '=', expected), ('Negative weather-penalty benefit exceeded native tier bound', actual, expected)
    groups['negative_native_SPY_weather_benefit_bound_uses_lower_limit'] += 1

if focus in (None, 'zero_max'):
    for service in ('mil', 'civ'):
        if selected and selected != 'com_' + service: continue
        for satellite_count in (0, 5):
            result = state()
            country = result['countries']['A']
            country['variables'].update(var_COM_mil_system_idx=3, var_COM_civ_system_idx=3)
            country['variables']['var_COM_' + service + '_sat_system_max'] = 0
            country['arrays']['COM_satellite_array'] = [0, 0, 0, satellite_count, 0, 0, 0, 0]
            result['temp'] = {}
            # Explicit primitive: an unguarded zero denominator fails closed;
            # this asserts script safety, not unknown native engine arithmetic.
            execute([('update_COM_system_stats', '=', 'yes')], result, context('A'))
            assert country['variables']['var_COM_' + service + '_coverage'] == 0 and country['variables']['var_COM_' + service + '_sat_system_bonus'] == 0, ('Zero maximum needs guarded zero coverage without a native division', service, satellite_count, country['variables']['var_COM_' + service + '_coverage'])
            groups['both_COM_service_maximum_zero_branches_use_explicit_guarded_zero_coverage'] += 1

if focus is None:
    for family, (upper, service, pointer, factors) in FAMILIES.items():
        prefix = upper + '_' + service
        for kind in ('request', 'offer'):
            result = state(); prepare(result, family, kind)
            provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
            pp = {actor: data['variables']['political_power'] for actor, data in result['countries'].items()}
            provider_before = values(result, family, provider, base=family == 'com_mil')
            assert pending(result, family) == ('B', 1 if kind == 'request' else 2, 3)
            assert ('A', 'eon_sat_' + family + '_window', 30.0) in result['timer_declarations']
            assert response(result, family, kind)
            assert arrays(result, family, recipient) == ([provider], [3])
            assert result['countries'][provider]['arrays'][prefix + '_treaty_array'] == [recipient]
            assert_values(result, family, expected_gain(result, family, recipient, (provider,)), recipient)
            assert_values(result, family, provider_before, provider)
            assert pending(result, family) == (0, 0, 0)
            accepted_flag = ('eon_sat_com_mil_accepted@B' if family == 'com_mil' else 'recently_accepted_' + service + '_' + upper.lower() + '_@B')
            # Preserve the actual original spellings, including the absent
            # GNSS military request cooldown and GNSS/SPY names without access.
            if family == 'gnss_mil' and kind == 'request':
                assert accepted_flag not in result['countries']['A']['flags']
            else:
                assert accepted_flag in result['countries']['A']['flags'], (family, kind, accepted_flag, result['countries']['A']['flags'])
                assert ('A', accepted_flag, 180.0) in result['timer_declarations']
            response(result, family, kind)
            assert arrays(result, family, recipient) == ([provider], [3])
            assert pp == {actor: data['variables']['political_power'] for actor, data in result['countries'].items()}
            groups['all_eight_native_proposals_preserve_free_cost_recipient24fields_and_original_cooldown_roles_consume_once'] += 1

            result = state(); prepare(result, family, kind)
            response(result, family, kind, accepted=False)
            assert pending(result, family) == (0, 0, 0) and not arrays(result, family, recipient)[0]
            assert send(result, family, kind), 'Normal consumed refusal permits a new owned round'
            groups['all_eight_consumed_native_refusals_release_only_owned_family_without_a_grant'] += 1

        result = state(); prepare(result, family)
        before = snapshot(result)
        assert not send(result, family, peer='C')
        send(result, family, peer='C', force=True)
        response(result, family, 'offer')
        response(result, family, peer='C')
        assert snapshot(result) == before
        groups['each_family_serialization_and_wrong_kind_wrong_peer_callbacks_preserve_current_owner'] += 1

        for mutation in ('provider upgrade', 'provider zero', 'recipient upgrade', 'dead peer', 'direct war', 'expired window'):
            result = state(); prepare(result, family)
            if mutation == 'provider upgrade': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 5
            elif mutation == 'provider zero': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 0
            elif mutation == 'recipient upgrade': result['countries']['A']['variables']['var_' + prefix + '_system_idx'] = 4
            elif mutation == 'dead peer': result['countries']['B']['exists'] = False
            elif mutation == 'direct war': result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
            else: result['countries']['A']['flags'].discard('eon_sat_' + family + '_window')
            assert not response(result, family)
            assert not arrays(result, family)[0] and pending(result, family) == (0, 0, 0)
            groups['each_actual_accept_callback_rechecks_frozen_provider_level_own_eligibility_liveness_war_and_deadline'] += 1

        for level in (0, 1, 7, 8, -1, 3.5):
            result = state(); result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = level
            if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0 if level == 0 else 10)
            ready = send(result, family)
            assert ready == (level in (1, 7))
            if ready: assert response(result, family) and arrays(result, family)[1] == [level]
            else:
                before = snapshot(result); send(result, family, force=True)
                assert snapshot(result) == before
            groups['current_literal_0_to7_supported_tiers_guard_fresh_cached_clicks'] += 1

        result = state(); result['countries']['A']['variables'][pointer] = 'C'
        assert not send(result, family)
        before = snapshot(result)
        response(result, family); response(result, family, accepted=False)
        assert snapshot(result) == before
        other = next(candidate for candidate in FAMILIES if candidate != family)
        assert send(result, other), 'Legacy unknown ownership locks its family alone'
        groups['four_unmanaged_legacy_pointers_keep_unknown_owner_and_do_not_lock_other_families'] += 1

        result = state()
        result['countries']['A']['variables'].update({'eon_sat_' + family + '_partner': 'D', 'eon_sat_' + family + '_kind': 2, 'eon_sat_' + family + '_level': 7})
        result['countries']['A']['flags'].update({'eon_sat_' + family + '_cancelled', 'eon_sat_' + family + '_window'})
        prepare(result, family); assert response(result, family) and arrays(result, family) == (['B'], [3])
        groups['fresh_unreserved_init_clears_only_owned_orphan_flags_and_terms'] += 1

        for mutation in ('duplicate live providers', 'changed tier', 'dormant zero', 'weaker provider', 'fractional provider', 'out of range provider', 'dead provider', 'direct war', 'unilateral access', 'self entry'):
            result = state(); seed_consent(result, family, copies=2 if mutation == 'duplicate live providers' else 1); seed_consent(result, family, provider='C')
            if mutation == 'changed tier': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 5
            elif mutation == 'dormant zero': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 0
            elif mutation == 'weaker provider': result['countries']['A']['variables']['var_' + prefix + '_system_idx'] = 4
            elif mutation == 'fractional provider': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 3.5
            elif mutation == 'out of range provider': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 8
            elif mutation == 'dead provider': result['countries']['B']['exists'] = False
            elif mutation == 'direct war': result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
            elif mutation == 'unilateral access': result['countries']['B']['arrays'][prefix + '_treaty_array'] = []
            elif mutation == 'self entry': seed_consent(result, family, provider='A')
            helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)
            providers = ['C'] if mutation in ('dead provider', 'unilateral access') else ['B', 'C']
            indices = [3] if len(providers) == 1 else [5 if mutation == 'changed tier' else 0 if mutation in ('dormant zero', 'fractional provider', 'out of range provider') else 3, 3]
            assert arrays(result, family) == (providers, indices), (family, mutation, arrays(result, family))
            assert_values(result, family, expected_gain(result, family, providers=tuple(providers)))
            groups['four_families_live_ID_dedup_rebuild_tiers_retain_dormant_consent_filter_bad_or_ineligible_service'] += 1

        result = state(); seed_consent(result, family, copies=3); seed_consent(result, family, provider='C', copies=2)
        for provider in ('B', 'C'):
            for factor in factors:
                field = 'var_' + prefix + '_' + factor + '_base'
                cap = result['global']['arrays'][prefix + '_' + factor + '_max_array'][3]
                result['countries'][provider]['variables'][field] = cap
            helper(result, 'eon_sat_refresh_' + family, provider)
        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)
        assert arrays(result, family) == (['B', 'C'], [3, 3])
        assert_values(result, family, expected_gain(result, family, providers=('B', 'C')))
        effect(result, family, 'revoke', actor='B', peer='A')
        assert arrays(result, family) == (['C'], [3])
        assert_values(result, family, expected_gain(result, family, providers=('C',)))
        before = snapshot(result); effect(result, family, 'revoke', actor='B', peer='A'); assert snapshot(result) == before
        effect(result, family, 'revoke', actor='C', peer='A')
        assert arrays(result, family) == ([], [])
        assert_values(result, family, values(result, family, base=True))
        groups['all_four_provider_revoke_callbacks_cap24fields_remove_one_duplicate_ID_and_return_to_own_base'] += 1

        for kind in ('request', 'offer'):
            result = state(); prepare(result, family, kind)
            original = pending(result, family)
            pp = result['countries']['A']['variables']['political_power']
            assert not withdraw(result, family, actor='B')
            withdraw(result, family, actor='B', force=True)
            assert pending(result, family) == original
            assert withdraw(result, family)
            assert pending(result, family) == original and 'eon_sat_' + family + '_cancelled' in result['countries']['A']['flags']
            assert not withdraw(result, family)
            assert not send(result, family, peer='C')
            assert not response(result, family, kind)
            recipient = 'A' if kind == 'request' else 'B'
            assert pending(result, family) == (0, 0, 0) and not arrays(result, family, recipient)[0]
            assert result['countries']['A']['variables']['political_power'] == pp
            assert 'eon_sat_' + family + '_quarantine@B' not in result['countries']['A']['flags']
            assert send(result, family, kind)
            groups['four_real_withdraw_buttons_for_both_roles_preserve_identity_until_reply_with_no_grant_cost_or_quarantine'] += 1

        for mutation in ('AI actor', 'dead actor', 'no owned request'):
            result = state()
            if mutation != 'no owned request': prepare(result, family)
            if mutation == 'AI actor': result['countries']['A']['ai'] = True
            elif mutation == 'dead actor': result['countries']['A']['exists'] = False
            before = snapshot(result)
            assert not withdraw(result, family)
            withdraw(result, family, force=True)
            assert snapshot(result) == before
            groups['fresh_human_owned_live_withdraw_guards_prevent_cached_forced_clicks'] += 1

        for mutation in ('expired window', 'dead peer', 'zero peer', 'changed tier', 'direct war'):
            result = state(); prepare(result, family)
            if mutation == 'expired window': result['countries']['A']['flags'].discard('eon_sat_' + family + '_window')
            elif mutation == 'dead peer': result['countries']['B']['exists'] = False
            elif mutation == 'zero peer': result['countries']['A']['variables']['eon_sat_' + family + '_partner'] = 0
            elif mutation == 'changed tier': result['countries']['B']['variables']['var_' + prefix + '_system_idx'] = 5
            else: result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
            hook(result)
            if mutation in ('changed tier', 'direct war'):
                assert pending(result, family) == ('B', 1, 3)
                assert 'eon_sat_' + family + '_cancelled' in result['countries']['A']['flags']
                assert not send(result, family, peer='C')
                response(result, family, accepted=False)
                assert pending(result, family) == (0, 0, 0)
            else:
                assert pending(result, family) == (0, 0, 0)
                if mutation != 'zero peer':
                    assert 'eon_sat_' + family + '_quarantine@B' in result['countries']['A']['flags']
                    result['countries']['B']['exists'] = True
                    assert not send(result, family)
                    prepare(result, family, peer='C')
                    owned_c = pending(result, family)
                    response(result, family)
                    assert pending(result, family) == owned_c and not arrays(result, family)[0]
            groups['forced_expiry_missing_peer_quarantine_known_pair_while_transient_invalid_policy_holds_original_reply'] += 1

        for subject in (False, True):
            for victim in ('A', 'B'):
                for extended_first in (False, True):
                    result = state(); prepare(result, family)
                    assert source['send'](result, 'com', 'offer', 'C', victim)
                    result['countries'][victim]['exists'] = False
                    hook(result, victim=victim, subject=subject, extended_first=extended_first)
                    assert pending(result, family) == (0, 0, 0)
                    assert source['pending'](result, 'com', 'C')[:3] == (0, 0, 0)
                    assert 'eon_sat_' + family + '_quarantine@B' in result['countries']['A']['flags']
                    assert 'eon_sat_com_quarantine@' + victim in result['countries']['C']['flags']
                    result['countries'][victim]['exists'] = True
                    assert not send(result, family)
                    prepare(result, family, peer='C')
                    current = pending(result, family)
                    response(result, family)
                    assert pending(result, family) == current and not arrays(result, family)[0]
                    groups['four_families_pending_annex_both_roles_both_hooks_both12_13_orders_preserve_each_original_actor_tombstone'] += 1

        for subject in (False, True):
            for extended_first in (False, True):
                result = state(); prepare(result, family); assert response(result, family)
                assert source['send'](result, 'com', 'offer', 'C', 'B')
                assert source['response'](result, 'com', 'offer', actor='C', partner='B')
                # Victim existence still true models callback ordering. Its
                # own arrays clear before each family's final reconciliation.
                hook(result, victim='B', subject=subject, extended_first=extended_first)
                assert arrays(result, family) == ([], [])
                assert not result['countries']['B']['arrays'][prefix + '_treaty_array']
                assert not result['countries']['B']['arrays']['COM_civ_access_array']
                assert not result['countries']['C']['arrays']['COM_civ_treaty_array']
                groups['mixed_civilian_extended_active_annex_before_existence_flip_cleans_consent_in_both_hook_orders'] += 1

    result = state()
    for family in FAMILIES: prepare(result, family)
    assert source['send'](result, 'gnss') and source['send'](result, 'com')
    current = {family: pending(result, family) for family in FAMILIES}
    for family in ('gnss', 'com'):
        assert result['countries']['A']['variables']['eon_sat_' + family + '_partner'] == 'B'
    assert withdraw(result, 'spy_mil')
    response(result, 'spy_mil', accepted=False)
    for family in FAMILIES:
        if family != 'spy_mil': assert pending(result, family) == current[family]
    assert source['response'](result, 'gnss') and source['response'](result, 'com')
    for family in FAMILIES:
        if family != 'spy_mil': assert response(result, family) and arrays(result, family) == (['B'], [3])
    assert not arrays(result, 'spy_mil')[0]
    groups['all_six_satellite_families_can_negotiate_independently_one_withdrawal_does_not_consume_other_five'] += 1

    result = state()
    before = outside_extended(result)
    for family in FAMILIES:
        prepare(result, family); assert response(result, family)
        effect(result, family, 'revoke', actor='B', peer='A')
    assert outside_extended(result) == before
    groups['extended_access_grant_and_revoke_preserve_economy_energy_CT_civilian_service_and_other_diplomacy'] += 1

    for old_civ_traffic in (0, 2):
        for military_load, expected_bonus in ((500, 1), (1500, .5), (2500, 0)):
            result = state(); country = result['countries']['A']
            country['variables'].update(var_COM_mil_system_idx=3, var_COM_civ_system_idx=3,
                                        var_sat_network_traffic_civ=old_civ_traffic, num_battalions=military_load)
            result['temp'] = {}
            execute([('update_COM_system_stats', '=', 'yes')], result, context('A'))
            assert model['compare'](country['variables']['var_sat_network_traffic_mil'], '=', military_load / 1000)
            assert model['compare'](country['variables']['var_COM_mil_sat_system_bonus'], '=', expected_bonus)
            groups['military_traffic_current_ratio_underload_overload_clamp_is_independent_of_stale_civilian_ratio'] += 1

    result = state(); country = result['countries']['A']
    country['variables'].update(var_COM_mil_system_idx=3, var_COM_civ_system_idx=4, var_COM_mil_sat_system_max=10)
    country['arrays']['COM_satellite_array'] = [0, 0, 0, 2, 3, 0, 0, 0]
    country['arrays']['COM_sat_receiver_tech_array'] = [0, 0, 0, 100, 200, 0, 0, 0]
    result['temp'] = {}
    execute([('update_COM_system_stats', '=', 'yes')], result, context('A'))
    assert country['variables']['var_COM_mil_receiver_cap'] == 800 and country['variables']['var_COM_civ_receiver_cap'] == 600
    assert country['variables']['var_COM_mil_sat_system_num'] == 5 and country['variables']['var_COM_civ_sat_system_num'] == 3
    groups['both_original_capacity_sums_across_eligible_tiers_are_preserved_without_false_overwrite_repair'] += 1

    result = state(); country = result['countries']['A']
    country['variables'].update(var_COM_mil_system_idx=3, var_COM_civ_system_idx=3)
    seed_consent(result, 'com_mil', recipient='B', provider='A', copies=2)
    seed_consent(result, 'com_mil', recipient='C', provider='A')
    result['countries']['B']['variables'].update(num_battalions=10, num_ships=3, num_deployed_planes=5)
    result['countries']['C']['variables'].update(num_battalions=20, num_ships=4, num_deployed_planes=7)
    result['temp'] = {}
    execute([('update_COM_system_stats', '=', 'yes')], result, context('A'))
    assert country['variables']['var_treaty_COM_mil_receiver_num'] == 49 and country['variables']['var_COM_mil_receiver_num'] == 49
    assert country['arrays']['COM_mil_treaty_array'] == ['B', 'C']
    assert model['compare'](country['variables']['var_sat_network_traffic_mil'], '=', .049)
    groups['military_receiver_load_sums_all_native_battalion_ship_plane_getters_once_per_consensual_unique_recipient'] += 1

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'adapter_semantics_cases': 0,
                  'total_cases': sum(groups.values()), 'groups': dict(groups), 'baseline': BASELINE,
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
                  'proof_scope': 'bounded ordered actual-source remaining satellite access; not HOI4 runtime'}, indent=2))
