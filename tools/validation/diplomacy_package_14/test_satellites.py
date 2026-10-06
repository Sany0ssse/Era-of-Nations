"""Ordered actual-source civilian first tier, SPY base and projected COM proof."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'f25dcfa040df4de947fe87e7a70f8f5fdd9ed659'
groups = Counter()
adapter_cases = Counter()

# Definition-only inheritance: the previous285 cases run in their own runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_13/test_satellites.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# Initial actual-source REDs must be observed before production changes.'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'civilian_first_tier_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch, read = (source[name] for name in ('ast', 'one', 'context', 'switch', 'read'))
trigger, execute = source['trigger'], source['execute']
civilian = source['source']
FACTORS = civilian['FACTORS']

# Installed1.19 documentation defines divide_temp_variable's default
# if_zero as0. Keep this native primitive confined to package14's loader;
# historical tests retain their original strict denominator seam.
inherited_execute = execute
def execute(nodes, result, ctx):
    if len(nodes) == 1 and nodes[0][0] == 'divide_temp_variable':
        key, operator, value = nodes[0]
        assert operator == '=' and len(value) == 1
        field, assignment, expression = value[0]
        assert assignment == '=' and not isinstance(expression, list)
        divisor = model['value'](result, ctx, expression)
        result.setdefault('native_temp_divisions', []).append((ctx['scope'], field, divisor))
        result['temp'][field] = result['temp'].get(field, 0) / divisor if divisor else 0
        return
    inherited_execute(nodes, result, ctx)

def install_native_divide(namespace, seen=None):
    seen = set() if seen is None else seen
    if id(namespace) in seen: return
    seen.add(id(namespace))
    namespace['execute'] = execute
    for field in ('source', 'loader', 'model'):
        child = namespace.get(field)
        if isinstance(child, dict): install_native_divide(child, seen)
install_native_divide(source)

missile_effects = ast(read('common/scripted_effects/00_missiles_scripted_effects.txt'))
model['effects']['calculate_SPY_mil_gui_vars'] = one(missile_effects, 'calculate_SPY_mil_gui_vars')
missile_triggers = ast(read('common/scripted_triggers/MD_missile_scripted_triggers.txt'))
for service in ('mil', 'civ'):
    name = 'NOT_share_COM_' + service + '_satellites_above_network_traffic_limit'
    model['capacity_triggers'][name] = one(missile_triggers, name)

SOURCE_PATHS = (
    'common/scripted_effects/eon_satellite_effects.txt',
    'common/scripted_triggers/eon_satellite_triggers.txt',
    'common/scripted_effects/00_missiles_scripted_effects.txt',
    'common/scripted_triggers/MD_missile_scripted_triggers.txt',
    'localisation/english/eon_satellite_l_english.yml',
    'localisation/russian/eon_satellite_l_russian.yml',
)

def literal_tables():
    result = {}
    for key, operator, value in one(ast(read('common/scripted_effects/00_missiles_models.txt')), 'set_all_sat_system_tech'):
        if key != 'add_to_array': continue
        assert len(value) == 1
        field, op, literal = value[0]
        if field.startswith('global.') and field.endswith(('_max_array', '_min_array')):
            result.setdefault(field.removeprefix('global.'), []).append(float(literal))
    for upper, factors in FACTORS.items():
        for factor in factors:
            assert len(result[upper + '_civ_' + factor + '_max_array']) == 8
    assert len(result['SPY_mil_air_weather_penalty_max_array']) == 8
    assert len(result['SPY_mil_air_weather_penalty_min_array']) == 8
    return result

def state():
    result = source['state']()
    result['global']['arrays'].update(literal_tables())
    for actor, country in result['countries'].items():
        for upper in FACTORS:
            country['variables']['var_' + upper + '_civ_sat_system_num'] = 0
        civilian['set_com_count_fixture'](result, actor, 0)
    return result

def grant_values(result, upper, actor='A', base=False):
    return {factor: result['countries'][actor]['variables']['var_' + upper + '_civ_' + factor + ('_base' if base else '')]
            for factor in FACTORS[upper]}

def assert_values(result, upper, expected, actor='A'):
    actual = grant_values(result, upper, actor)
    assert all(model['compare'](actual[key], '=', value) for key, value in expected.items()), (upper, actor, actual, expected)

def zero_setup(result, family, kind='request', count=2):
    upper = family.upper()
    provider, recipient = ('B', 'A') if kind == 'request' else ('A', 'B')
    for actor in (provider, recipient):
        result['countries'][actor]['variables']['var_' + upper + '_civ_system_idx'] = 0
    result['countries'][provider]['variables']['var_' + upper + '_civ_sat_system_num'] = count
    if upper == 'COM':
        civilian['set_com_count_fixture'](result, provider, count)
        civilian['helper'](result, 'eon_sat_com_sync_own', recipient)
    return provider, recipient

def projected(result, service, actor='A', target='B'):
    result['temp'] = {}
    return trigger([('NOT_share_COM_' + service + '_satellites_above_network_traffic_limit', '=', 'yes')],
                   result, context(actor, scope=target))

def civilian_expected(result, family, provider='B', recipient='A'):
    upper = family.upper(); level = result['countries'][provider]['variables']['var_' + upper + '_civ_system_idx']
    return {factor: min(result['countries'][recipient]['variables']['var_' + upper + '_civ_' + factor + '_base']
                        + result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor + '_base'],
                        result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][level])
            for factor in FACTORS[upper]}

# Focused actual-source regressions: ROOT must observe RED before game edits.
focus = None
family_filter = None
if len(sys.argv) in (3, 5):
    assert sys.argv[1] == '--focus'
    focus = sys.argv[2]
    if len(sys.argv) == 5:
        assert sys.argv[3] == '--family'; family_filter = sys.argv[4]
assert focus in (None, 'zero_level', 'zero_offer', 'zero_refresh', 'zero_unavailable', 'zero_lifecycle', 'zero_providers', 'zero_annex',
                 'weather_base', 'weather_overlimit', 'weather_curve', 'projected_zero', 'projected_positive', 'native_divide')
assert family_filter in (None, 'gnss', 'com', 'mil', 'civ')

for family in ('gnss', 'com'):
    if family_filter and family_filter != family: continue
    upper = family.upper()
    if focus in (None, 'zero_level', 'zero_offer'):
        for kind in ('request', 'offer'):
            if focus == 'zero_offer' and kind != 'offer': continue
            result = state(); provider, recipient = zero_setup(result, family, kind)
            assert civilian['send'](result, family, kind), ('Working civilian first-tier constellation was blocked', family, kind)
            assert civilian['response'](result, family, kind)
            assert civilian['grants'](result, recipient, upper) == [provider]
            assert civilian['indices'](result, recipient, upper) == [0]
            assert result['countries'][provider]['arrays'][upper + '_civ_treaty_array'] == [recipient]
            groups['both_civilian_working_first_tier_constellations_support_native_request_and_offer'] += 1
    if focus in (None, 'zero_refresh'):
        result = state(); zero_setup(result, family)
        civilian['seed_consent'](result, upper)
        for factor in FACTORS[upper]: result['countries']['B']['variables']['var_' + upper + '_civ_' + factor + '_base'] = 100
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        expected = {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][0] for factor in FACTORS[upper]}
        assert_values(result, upper, expected)
        assert civilian['grants'](result, 'A', upper) == ['B'] and civilian['indices'](result, 'A', upper) == [0]
        groups['both_civilian_first_tier_consent_contributes_and_clamps_actual_global_index_zero'] += 1
    if focus in (None, 'zero_unavailable'):
        for kind in ('request', 'offer'):
            result = state(); zero_setup(result, family, kind, count=0)
            before = civilian['snapshot'](result)
            assert not civilian['send'](result, family, kind)
            civilian['send'](result, family, kind, force=True)
            civilian['response'](result, family, kind)
            assert civilian['snapshot'](result) == before
            groups['civilian_first_tier_with_no_native_satellites_stays_unavailable_and_cached_click_inert'] += 1
        result = state(); zero_setup(result, family, count=0)
        civilian['seed_consent'](result, upper)
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        assert civilian['grants'](result, 'A', upper) == ['B'] and civilian['indices'](result, 'A', upper) == [0]
        assert_values(result, upper, grant_values(result, upper, base=True))
        groups['civilian_first_tier_without_satellites_keeps_dormant_consent_without_benefit'] += 1
    if focus in (None, 'zero_lifecycle'):
        for kind in ('request', 'offer'):
            result = state(); provider, recipient = zero_setup(result, family, kind)
            assert civilian['send'](result, family, kind)
            before = civilian['snapshot'](result)
            civilian['response'](result, family, 'offer' if kind == 'request' else 'request')
            civilian['response'](result, family, kind, partner='C')
            assert civilian['snapshot'](result) == before
            result['countries'][provider]['variables']['var_' + upper + '_civ_sat_system_num'] = 0
            if upper == 'COM': civilian['set_com_count_fixture'](result, provider, 0)
            assert not civilian['response'](result, family, kind)
            assert not civilian['grants'](result, recipient, upper)
            result['countries'][provider]['variables']['var_' + upper + '_civ_sat_system_num'] = 2
            if upper == 'COM': civilian['set_com_count_fixture'](result, provider, 2)
            assert civilian['send'](result, family, kind) and civilian['response'](result, family, kind)
            assert_values(result, upper, civilian_expected(result, family, provider, recipient), recipient)
            groups['four_civilian_first_tier_replies_preserve_wrong_peer_kind_and_recheck_lost_native_counts'] += 1

        result = state(); zero_setup(result, family)
        assert civilian['send'](result, family)
        result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 0)
        source['hook'](result)
        assert 'eon_sat_' + family + '_pending' in result['countries']['A']['flags']
        assert 'eon_sat_' + family + '_cancelled' in result['countries']['A']['flags']
        result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 2
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 2)
        assert not civilian['response'](result, family)
        assert not civilian['grants'](result, 'A', upper)
        assert civilian['send'](result, family) and civilian['response'](result, family)
        groups['civilian_daily_count_loss_cancellation_latches_until_consumed_reply_despite_recovery'] += 1

        result = state(); zero_setup(result, family)
        civilian['seed_consent'](result, upper)
        source['hook'](result)
        assert_values(result, upper, civilian_expected(result, family))
        result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 0)
        source['hook'](result)
        assert civilian['grants'](result, 'A', upper) == ['B'] and civilian['indices'](result, 'A', upper) == [0]
        assert_values(result, upper, grant_values(result, upper, base=True))
        result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 2
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 2)
        source['hook'](result)
        assert_values(result, upper, civilian_expected(result, family))
        civilian['effect'](result, 'revoke_civ_' + family + '_access', actor='B', partner='A')
        result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 4
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 4)
        source['hook'](result)
        assert civilian['grants'](result, 'A', upper) == [] and civilian['indices'](result, 'A', upper) == []
        assert_values(result, upper, grant_values(result, upper, base=True))
        groups['civilian_tier_zero_count_loss_and_recovery_preserve_consent_but_revoke_prevents_revival'] += 1

        for legacy_pointer in ('B', 'C'):
            result = state(); zero_setup(result, family)
            pointer = 'pending_civ_access_country' if family == 'gnss' else 'pending_civ_com_access_country'
            result['countries']['A']['variables'][pointer] = legacy_pointer
            before = civilian['snapshot'](result)
            assert not civilian['send'](result, family)
            civilian['send'](result, family, force=True)
            civilian['response'](result, family); civilian['response'](result, family, accepted=False)
            assert civilian['snapshot'](result) == before
            groups['unknown_civilian_legacy_pointer_ownership_blocks_first_tier_without_synthetic_migration'] += 1
    if focus in (None, 'zero_providers'):
        result = state(); zero_setup(result, family)
        if family == 'com':
            for factor in FACTORS[upper]: result['countries']['A']['variables']['var_COM_civ_' + factor + '_base'] = .01
        result['countries']['C']['variables'].update({'var_' + upper + '_civ_system_idx': 0,
                                                    'var_' + upper + '_civ_sat_system_num': 2})
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)
        civilian['seed_consent'](result, upper, provider='B', duplicates=3)
        civilian['seed_consent'](result, upper, provider='C', duplicates=2)
        for provider in ('B', 'C'):
            for factor in FACTORS[upper]: result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor + '_base'] = .005
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        assert civilian['grants'](result, 'A', upper) == ['B', 'C'] and civilian['indices'](result, 'A', upper) == [0, 0]
        assert_values(result, upper, {factor: .02 for factor in FACTORS[upper]})
        for provider in ('B', 'C'):
            for factor in FACTORS[upper]: result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor + '_base'] = 100
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        bounds = {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][0] for factor in FACTORS[upper]}
        assert_values(result, upper, bounds)
        civilian['effect'](result, 'revoke_civ_' + family + '_access', actor='B', partner='A')
        assert civilian['grants'](result, 'A', upper) == ['C'] and civilian['indices'](result, 'A', upper) == [0]
        assert_values(result, upper, civilian_expected(result, family, 'C') if family == 'com' else bounds)
        groups['two_working_civilian_tier_zero_providers_sum_once_clamp_index_zero_and_same_tier_revoke_preserves_peer'] += 1

        result = state(); zero_setup(result, family)
        result['countries']['C']['variables'].update({'var_' + upper + '_civ_system_idx': 3,
                                                    'var_' + upper + '_civ_sat_system_num': 2})
        if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)
        civilian['seed_consent'](result, upper, provider='B')
        civilian['seed_consent'](result, upper, provider='C')
        if family == 'com':
            for actor, base in (('A', .01), ('B', .03), ('C', .03)):
                for factor in FACTORS[upper]: result['countries'][actor]['variables']['var_COM_civ_' + factor + '_base'] = base
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        assert civilian['indices'](result, 'A', upper) == [0, 3]
        assert_values(result, upper, {factor: .07 for factor in FACTORS[upper]})
        for provider in ('B', 'C'):
            for factor in FACTORS[upper]: result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor + '_base'] = 100
        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')
        assert_values(result, upper, {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][3] for factor in FACTORS[upper]})
        civilian['effect'](result, 'revoke_civ_' + family + '_access', actor='C', partner='A')
        assert civilian['grants'](result, 'A', upper) == ['B'] and civilian['indices'](result, 'A', upper) == [0]
        assert_values(result, upper, civilian_expected(result, family) if family == 'com' else {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][0] for factor in FACTORS[upper]})
        groups['mixed_civilian_zero_and_higher_providers_both_contribute_with_strongest_native_cap_then_fall_back_after_revoke'] += 1
    if focus in (None, 'zero_annex'):
        for subject in (False, True):
            result = state(); zero_setup(result, family)
            assert civilian['send'](result, family) and civilian['response'](result, family)
            # Victim existence remains true to model the native preflip order.
            source['hook'](result, victim='B', subject=subject)
            assert civilian['grants'](result, 'A', upper) == [] and civilian['indices'](result, 'A', upper) == []
            assert not result['countries']['B']['arrays'][upper + '_civ_treaty_array']
            assert_values(result, upper, grant_values(result, upper, base=True))
            groups['both_native_annex_hooks_remove_active_civilian_first_tier_consent_before_existence_flips'] += 1

            result = state(); zero_setup(result, family)
            assert civilian['send'](result, family)
            result['countries']['B']['exists'] = False
            source['hook'](result, victim='B', subject=subject)
            assert 'eon_sat_' + family + '_pending' not in result['countries']['A']['flags']
            assert 'eon_sat_' + family + '_quarantine@B' in result['countries']['A']['flags']
            result['countries']['B']['exists'] = True
            assert not civilian['send'](result, family)
            result['countries']['C']['variables'].update({'var_' + upper + '_civ_system_idx': 0,
                                                        'var_' + upper + '_civ_sat_system_num': 2})
            if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)
            assert civilian['send'](result, family, partner='C')
            fresh = civilian['snapshot'](result)
            civilian['response'](result, family)
            assert civilian['snapshot'](result) == fresh
            assert civilian['response'](result, family, partner='C')
            groups['both_native_annex_hooks_retire_unconsumed_civilian_first_tier_pair_and_preserve_fresh_different_peer_response'] += 1

if focus in ('weather_base', 'weather_overlimit'):
    result = state(); country = result['countries']['A']
    country['variables'].update(var_SPY_mil_system_idx=3, var_SPY_mil_sat_system_bonus=2 if focus == 'weather_overlimit' else 1)
    result['temp'] = {}
    execute([('calculate_SPY_mil_gui_vars', '=', 'yes')], result, context('A'))
    expected = result['global']['arrays']['SPY_mil_air_weather_penalty_max_array'][3]
    actual = country['variables']['var_SPY_mil_air_weather_penalty_base']
    assert model['compare'](actual, '=', expected), ('Native negative SPY base exceeds declared full/overcoverage bounds', actual, expected)
    groups['actual_SPY_base_calculator_bounds_full_or_overcoverage_at_negative_literal_tier_cap'] += 1

if focus in (None, 'weather_curve'):
    for tier in range(8):
        for bonus in (0, .25, 1, 2):
            result = state(); country = result['countries']['A']
            country['variables'].update(var_SPY_mil_system_idx=tier, var_SPY_mil_sat_system_bonus=bonus)
            before = deepcopy(result['countries'])
            execute([('calculate_SPY_mil_gui_vars', '=', 'yes')], result, context('A'))
            for factor in source['FAMILIES']['spy_mil'][3]:
                upper = result['global']['arrays']['SPY_mil_' + factor + '_max_array'][tier]
                lower = result['global']['arrays']['SPY_mil_' + factor + '_min_array'][tier]
                expected = max(upper * bonus, lower) if factor != 'air_weather_penalty' else max(upper, min(upper * bonus, lower))
                actual = country['variables']['var_SPY_mil_' + factor + '_base']
                assert model['compare'](actual, '=', expected), ('Native literal SPY calculator bounds', tier, bonus, factor, actual, expected)
            assert result['countries']['B'] == before['B'] and result['countries']['C'] == before['C']
            groups['all_eight_native_SPY_tiers_bound_negative_weather_full_proportional_zero_and_overcoverage_without_altering_positive_fields'] += 1

if focus in (None, 'projected_zero'):
    for service in ('mil', 'civ'):
        if family_filter and family_filter != service: continue
        for capacity in (0, -5):
            result = state()
            result['countries']['A']['variables'].update({'var_COM_' + service + '_receiver_cap': capacity,
                                                         'var_COM_' + service + '_receiver_num': 0,
                                                         'var_sat_network_traffic_' + service: 0})
            result['countries']['B']['variables'].update(num_battalions=2, num_ships=3, num_deployed_planes=5, num_controlled_states=1)
            actual = projected(result, service)
            assert actual, ('No native capacity projected overload returned false', service, capacity, actual)
            assert not result.get('native_temp_divisions'), ('No-capacity branch executed a divide', service, capacity)
            groups['both_projected_COM_zero_and_negative_capacities_are_unavailable_without_executing_a_divide'] += 1

if focus in (None, 'projected_positive'):
    for service in ('mil', 'civ'):
        if family_filter and family_filter != service: continue
        for current, cap, existing, demand, expected in ((1.25, 1000, 1250, 100, True),
                                                        (.9, 1000, 900, 300, False),
                                                        (.9, 1000, 900, 400, True),
                                                        (1, 1000, 1000, 1000, True),
                                                        (1.249, 1000, 1249, 1000, True),
                                                        (1.24901, 1000, 1249.01, 1000, True),
                                                        (1, 1000, 1000, 249, False),
                                                        (1, 1000, 1000, 249.1, True)):
            result = state()
            result['countries']['A']['variables'].update({'var_sat_network_traffic_' + service: current,
                                                         'var_COM_' + service + '_receiver_cap': cap,
                                                         'var_COM_' + service + '_receiver_num': existing})
            result['countries']['B']['variables'].update(num_battalions=demand, num_ships=0, num_deployed_planes=0,
                                                        num_controlled_states=demand / 100)
            assert projected(result, service) == expected, (service, current, cap, existing, demand, expected)
            assert result['native_temp_divisions'] == [('B', 'temp1', cap)]
            groups['positive_COM_capacities_use_current_native_demand_and_literal_projected_threshold'] += 1

if focus is None:
    for service in ('mil', 'civ'):
        result = state()
        result['countries']['A']['variables'].update({'var_COM_' + service + '_receiver_cap': 1000,
                                                     'var_COM_' + service + '_receiver_num': 900,
                                                     'var_sat_network_traffic_' + service: .9})
        result['countries']['B']['variables'].update({'var_COM_' + service + '_receiver_cap': 0,
                                                     'var_COM_' + service + '_receiver_num': 90000,
                                                     'var_sat_network_traffic_' + service: 9,
                                                     'num_battalions': 100, 'num_ships': 0, 'num_deployed_planes': 0,
                                                     'num_controlled_states': 1})
        before = civilian['snapshot'](result)
        assert not projected(result, service)
        assert result['native_temp_divisions'] == [('B', 'temp1', 1000)]
        assert civilian['snapshot'](result) == before
        result['countries']['A']['variables']['var_COM_' + service + '_receiver_cap'] = 0
        assert projected(result, service) and not result['native_temp_divisions'][1:]
        groups['both_COM_projected_helpers_read_ROOT_provider_capacity_and_THIS_recipient_demand_without_persistent_country_mutation'] += 1

    for military_units, expected in (((0, 1300, 0), True), ((0, 0, 1200), False), ((400, 500, 400), True)):
        result = state()
        result['countries']['A']['variables'].update(var_COM_mil_receiver_cap=1000, var_COM_mil_receiver_num=0, var_sat_network_traffic_mil=0)
        result['countries']['B']['variables'].update(zip(('num_battalions', 'num_ships', 'num_deployed_planes'), military_units))
        assert projected(result, 'mil') == expected
        assert model['compare'](result['temp']['temp1'], '=', sum(military_units) / 1000)
        groups['military_projected_load_preserves_native_ship_plane_and_battalion_units_and_sum'] += 1

    result = state()
    def economic_values(state):
        return {actor: {key: value for key, value in country['variables'].items()
                        if not key.startswith(('var_GNSS_', 'var_COM_', 'var_SPY_', 'var_treaty_COM_', 'var_sat_network_traffic_', 'eon_sat_', 'pending_'))}
                for actor, country in state['countries'].items()}
    before_economy = economic_values(result)
    for family in source['FAMILIES']: source['prepare'](result, family)
    for family in ('gnss', 'com'):
        zero_setup(result, family)
        assert civilian['send'](result, family)
    extended = {family: source['pending'](result, family) for family in source['FAMILIES']}
    com_pending = civilian['pending'](result, 'com')
    assert civilian['withdraw'](result, 'gnss')
    civilian['response'](result, 'gnss', accepted=False)
    assert civilian['pending'](result, 'com') == com_pending
    assert civilian['response'](result, 'com')
    for family in source['FAMILIES']:
        assert source['pending'](result, family) == extended[family]
        assert source['response'](result, family)
    assert civilian['grants'](result, 'A', 'GNSS') == []
    assert civilian['grants'](result, 'A', 'COM') == ['B']
    assert economic_values(result) == before_economy
    groups['all_six_satellite_families_remain_independent_with_civilian_first_tier_and_one_withdrawal_without_economic_rewards'] += 1

if focus in (None, 'native_divide'):
    for divisor, expected in ((0, 0), (4, 3)):
        result = state(); result['temp'] = {'probe': 12}
        execute([('divide_temp_variable', '=', [('probe', '=', str(divisor))])], result, context('A'))
        assert result['temp']['probe'] == expected
        adapter_cases['documented_native_temp_divide_default_if_zero_and_nonzero_ratio'] += 1

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'adapter_semantics_cases': sum(adapter_cases.values()),
                  'total_cases': sum(groups.values()) + sum(adapter_cases.values()), 'groups': dict(groups), 'adapter_groups': dict(adapter_cases), 'baseline': BASELINE,
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
                  'proof_scope': 'bounded ordered actual-source civilian first tier, SPY base and COM projected traffic; not HOI4 runtime'}, indent=2))
