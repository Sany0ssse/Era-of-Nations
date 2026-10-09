"""Build a private frozen-source migration probe; never install or launch it.

The fixture invokes production helpers. Seeded cohorts are private test data;
the population settlement algorithm is never copied into the fixture.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast

NS = 'eon_native_migration_probe'
MARK = 'EON_MIGRATION_NATIVE_V1'
P = NS + '_'
DOCS = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cv(name, value, compare='equals'):
    return f'check_variable = {{ var = {name} value = {value} compare = {compare} }} '


def setv(name, value):
    return f'set_variable = {{ {name} = {value} }} '


def scope_state(tag, body):
    return f'var:global.{P}{tag.lower()}_state = {{ {body} }} '


def flow(source='nep', target='ger', country='ger', amount=1000, kind=1):
    result = 'eon_migration_clear_flow_scratch = yes '
    for name, value in (('source_state', f'global.{P}{source}_state'),
                        ('target_state', f'global.{P}{target}_state'),
                        ('origin_country', f'global.{P}origin'),
                        ('origin_slot', f'global.{P}origin_slot'),
                        ('target_country', f'global.{P}{country}_id')):
        result += setv('global.eon_migration_' + name, value)
    if amount is not None: result += setv('global.eon_migration_amount', amount)
    if kind is not None: result += setv('global.eon_migration_kind', kind)
    return result + 'eon_migration_move_population = yes '


def seed(tag, stock, fresh=0, age=0, integrated=0, longterm=0):
    values = (('stock', stock), ('fresh', fresh), ('age', age),
              ('integrated', integrated), ('longterm', longterm))
    return scope_state(tag, 'eon_migration_prepare_state_ledger = yes ' + ''.join(
        setv(f'eon_refugee_{name}^global.{P}origin_slot', value) for name, value in values
    ) + 'eon_migration_recount_state = yes ')


def capture_population(suffix):
    body = ''.join(scope_state(tag, setv(f'global.{P}{tag}_{suffix}_k', 'state_population_k'))
                   for tag in ('nep', 'ger', 'fra'))
    body += setv(f'global.{P}total_{suffix}_k', f'global.{P}nep_{suffix}_k')
    for tag in ('ger', 'fra'):
        body += f'add_to_variable = {{ global.{P}total_{suffix}_k = global.{P}{tag}_{suffix}_k }} '
    return body


def capture_owned_population(suffix):
    return ''.join(setv(f'global.{P}{tag.lower()}_{suffix}_owned_k', 0) + tag +
                   ' = { every_owned_state = { add_to_variable = { ' +
                   f'global.{P}{tag.lower()}_{suffix}_owned_k = state_population_k' + ' } } } '
                   for tag in ('NEP', 'GER'))


def capture_world_population(suffix):
    name = f'global.{P}world_{suffix}_k'
    return setv(name, 0) + 'every_state = { add_to_variable = { ' + name + ' = state_population_k } } '


def build(source, output, docs=DOCS, validate_only=False):
    source, output, docs = source.resolve(), output.resolve(), docs.resolve()
    assert source.is_dir(), 'Require an existing production source snapshot'
    assert not output.exists(), 'Preserve earlier native receipts'
    assert '.local' in output.parts, 'Fixture output must remain private under .local'
    assert output != source and source not in output.parents, 'Do not write fixtures inside production source'
    assertions = []
    expectations = {}

    def check(label, predicate, expected):
        assert label not in expectations
        assertions.append(label)
        expectations[label] = {'predicate': predicate.strip(), 'expected': expected}
        return (f'log = "{MARK} BEGIN {label}" '
                f'if = {{ limit = {{ {predicate} }} log = "{MARK} PASS {label}" '
                f'add_to_variable = {{ global.{P}passes = 1 }} }} '
                f'else = {{ log = "{MARK} FAIL {label}" '
                f'add_to_variable = {{ global.{P}fails = 1 }} }} '
                f'log = "{MARK} END {label}" ')

    def observe_bool(label, predicate):
        return (f'if = {{ limit = {{ {predicate} }} log = "{MARK} OBS {label}=1" }} '
                f'else = {{ log = "{MARK} OBS {label}=0" }} ')

    def observe_wars(phase):
        return ''.join(observe_bool(phase + '_' + tag + '_at_war', tag + ' = { has_war = yes }') +
                       observe_bool(phase + '_' + tag + '_in_faction', tag + ' = { is_in_faction = yes }')
                       for tag in ('NEP', 'GER', 'FRA'))

    def observe_treaty(phase):
        return (f'log = "{MARK} OBS treaty_{phase}_ROOT pending=[?pending_migration_agreement_country] '
                'terms=[?eon_migration_treaty_pending_terms] add=[?migrants_add] cut=[?migrants_cut]" '
                f'GER = {{ log = "{MARK} OBS treaty_{phase}_THIS sender=[?eon_migration_treaty_pending_sender] '
                'terms=[?eon_migration_treaty_pending_terms] add=[?migrants_add] cut=[?migrants_cut] '
                'unemployment=[?total_unemployed_percentage_display]" } ' +
                observe_bool('treaty_' + phase + '_importer_add_flag', 'GER = { ROOT = { has_country_flag = migration_agreement_migrants_add@PREV } }') +
                observe_bool('treaty_' + phase + '_exporter_cut_flag', 'GER = { has_country_flag = migration_agreement_migrants_cut@ROOT }') +
                observe_bool('treaty_' + phase + '_native_scopes', 'GER = { tag = GER ROOT = { tag = NEP } }') +
                observe_bool('treaty_' + phase + '_high_unemployment', 'GER = { has_dynamic_modifier = { modifier = high_unemployment_modifier } }') +
                observe_bool('treaty_' + phase + '_opinion_allowed', 'GER = { has_opinion = { target = ROOT value > 9 } }') +
                observe_bool('treaty_' + phase + '_response_current', 'GER = { eon_migration_treaty_response_current = yes }') +
                observe_bool('treaty_' + phase + '_terms_available', 'GER = { eon_migration_treaty_terms_available = yes }') +
                observe_bool('treaty_' + phase + '_response_valid', 'GER = { eon_migration_treaty_response_valid = yes }'))

    g = lambda suffix: f'global.{P}{suffix}'
    origin = f'global.{P}origin'
    origin_slot = f'global.{P}origin_slot'
    cohort = lambda name: f'eon_refugee_{name}^{origin_slot}'
    untouched = lambda suffix='after': cv(g('total_' + suffix + '_k'), g('total_before_k'))

    body = f'log = "{MARK} RUN_BEGIN" '
    body += check('native_root_scope', 'tag = NEP ROOT = { tag = NEP }', 'ROOT and THIS are NEP')
    body += f'log = "{MARK} OBS BEFORE_EVENT_REGISTRY size=[?global.eon_migration_array_size]" '
    body += ('every_country = { eon_migration_initialize_country = yes '
             f'log = "{MARK} OBS AFTER_COUNTRY_REGISTER slot=[?eon_migration_origin_slot] '
             'fund=[?eon_refugee_relief_fund] size=[?global.eon_migration_array_size]" } ')
    body += f'log = "{MARK} OBS AFTER_EVENT_REGISTRY size=[?global.eon_migration_array_size]" '
    for tag, minimum in (('NEP', 50), ('GER', 3000), ('FRA', 50)):
        body += (tag + ' = { ' + setv(g(tag.lower() + '_id'), 'THIS.id') +
                 setv(g(tag.lower() + '_slot'), 'eon_migration_origin_slot') +
                 'random_owned_controlled_state = { limit = { is_core_of = PREV ' +
                 cv('state_population_k', minimum, 'greater_than') + '} ' +
                 setv(g(tag.lower() + '_state'), 'THIS') + '} } ')
    body += setv(origin, g('nep_id'))
    body += setv(origin_slot, g('nep_slot'))
    body += f'log = "{MARK} OBS registry origin_token=[?{origin}] origin_slot=[?{origin_slot}] size=[?global.eon_migration_array_size]" '
    body += check('append_only_registry_maps_full_country_tokens', cv(origin_slot, 0, 'greater_than') +
                  cv(f'global.eon_migration_origins^{origin_slot}', g('nep_id')) +
                  cv(f'global.eon_migration_origins^{g("ger_slot")}', g('ger_id')),
                  'Separate stable integer slots map to full native NEP and GER scope tokens')
    body += setv(g('registry_size_before'), 'global.eon_migration_array_size')
    body += 'NEP = { eon_migration_register_country = yes eon_migration_register_country = yes } '
    body += check('native_origin_registry_registration_is_idempotent', cv('global.eon_migration_array_size', g('registry_size_before')) +
                  cv('eon_migration_origin_slot', g('nep_slot')) +
                  cv(f'global.eon_migration_origins^{origin_slot}', g('nep_id')),
                  'Repeated production registration retains the exact full token, own slot and array size')
    body += setv('eon_migration_origin_slot', g('ger_slot'))
    body += 'eon_migration_register_country = yes '
    body += check('native_origin_registry_recovers_overwritten_country_slot', cv('eon_migration_origin_slot', g('nep_slot')) +
                  cv('global.eon_migration_array_size', g('registry_size_before')) +
                  cv(f'global.eon_migration_origins^{origin_slot}', g('nep_id')),
                  'Overwritten own slot recovers the existing canonical full-token entry without registry growth')
    body += check('selected_live_owned_controlled_core_states', ''.join(scope_state(tag,
                  f'is_owned_by = {tag.upper()} is_controlled_by = {tag.upper()} is_core_of = {tag.upper()} ' +
                  cv('state_population_k', 50, 'greater_than')) for tag in ('nep', 'ger', 'fra')),
                  'Three runtime state pointers refer to live owned, controlled core territory')
    body += capture_population('before')
    body += scope_state('nep', 'add_manpower = 1000 ' + setv(g('primitive_plus_k'), 'state_population_k'))
    body += setv(g('primitive_expected_k'), g('nep_before_k'))
    body += f'add_to_variable = {{ {g("primitive_expected_k")} = 1 }} '
    body += check('state_add_manpower_changes_population_k', cv(g('primitive_plus_k'), g('primitive_expected_k')),
                  'STATE add_manpower +1000 changes actual state_population_k by exactly +1')
    body += scope_state('nep', 'add_manpower = -1000 ' + setv(g('primitive_restored_k'), 'state_population_k'))
    body += check('state_population_primitive_restores_exactly', cv(g('primitive_restored_k'), g('nep_before_k')),
                  'STATE -1000 restores the actual starting population')
    body += seed('nep', 777)
    body += check('native_country_slot_indexed_ledger', scope_state('nep', cv(cohort('stock'), 777) +
                  cv('eon_refugees_total', 777)), 'Production array prepare/recount resolves the own NEP integer slot as777')
    body += seed('nep', 0)

    # Nothing later, especially private wars, runs after a primitive failure.
    later = observe_wars('initial')
    # NEP starts the2000 bookmark in a civil war against NPM. Normalize this
    # private scenario rather than treating the real bookmark as peaceful.
    later += 'NEP = { if = { limit = { has_war_with = NPM } white_peace = { tag = NPM } } } '
    for tag in ('NEP', 'GER', 'FRA'):
        later += (tag + ' = { every_enemy_country = { white_peace = { tag = PREV } } '
                  'if = { limit = { is_in_faction = yes } leave_faction = yes } } ')
    later += observe_wars('normalized')
    later += ('GER = { remove_ideas = closed_borders ' + setv('population_total_m', 20) +
             setv('gdp_per_capita', 10) + setv('eon_refugee_policy', 1) +
             setv('eon_refugee_relief_fund', 0) + 'set_country_flag = eon_migration_relief_initialized } '
             'NEP = { remove_ideas = closed_borders ' + setv('gdp_per_capita', 10) +
             setv('eon_migration_peace_months', 3) + setv('eon_migration_home_control_ratio', 1) + '} '
             'FRA = { remove_ideas = closed_borders ' + setv('gdp_per_capita', 10) +
             setv('eon_refugee_policy', 1) + 'set_country_flag = eon_migration_relief_initialized } ')
    later += check('representative_countries_start_at_peace', ''.join(tag + ' = { has_war = no is_in_faction = no } '
                   for tag in ('NEP', 'GER', 'FRA')),
                   'Private NEP, GER and FRA scenario is genuinely peaceful and independent before core tests')
    later += flow() + capture_population('after')
    later += setv(g('expected_nep_k'), g('nep_before_k')) + f'add_to_variable = {{ {g("expected_nep_k")} = -1 }} '
    later += setv(g('expected_ger_k'), g('ger_before_k')) + f'add_to_variable = {{ {g("expected_ger_k")} = 1 }} '
    later += check('refugees_real_source_debit_target_credit', cv(g('nep_after_k'), g('expected_nep_k')) +
                   cv(g('ger_after_k'), g('expected_ger_k')) + untouched(),
                   '1000 actual people leave NEP state and enter GER state; three-state total is conserved')
    later += check('refugee_cohort_receipt_fresh_zero_age', scope_state('ger', cv(cohort('stock'), 1000) +
                   cv(cohort('fresh'), 1000) + cv(cohort('age'), 0) + cv(cohort('longterm'), 0) +
                   cv(cohort('integrated'), 0)), 'GER origin-NEP cohort has stock=fresh=1000, age/integrated/longterm=0')
    later += check('flow_amount_consumed_synchronously', cv('global.eon_migration_amount', 0) +
                   cv('global.eon_migration_debit', 0) + cv('global.eon_migration_target_state', 0) +
                   cv('global.eon_migration_kind', 0), 'Amount/debit/target/kind are clear when production helper returns')
    for label, arguments in (
        ('duplicate_consumed_flow', None), ('invalid_kind', {'kind': 5}),
        ('same_state', {'target': 'nep', 'country': 'nep'}),
        ('wrong_target_country', {'country': 'fra'}), ('missing_amount', {'amount': None}),
        ('missing_kind', {'kind': None}), ('fresh_only_return', {'source': 'ger', 'target': 'nep', 'country': 'nep', 'amount': 1, 'kind': 2}),
    ):
        later += 'eon_migration_move_population = yes ' if arguments is None else flow(**arguments)
        later += capture_population('guard')
        later += check(label + '_atomic', cv(g('nep_guard_k'), g('nep_after_k')) +
                       cv(g('ger_guard_k'), g('ger_after_k')) + untouched('guard') +
                       scope_state('ger', cv(cohort('stock'), 1000) + cv(cohort('fresh'), 1000)),
                       'Invalid/repeated flow changes neither actual population nor the existing cohort')
    later += seed('ger', 2000, fresh=100, age=6, integrated=1800, longterm=700)
    later += flow('ger', 'nep', 'nep', 1201, 2) + capture_population('guard')
    later += check('fresh_longterm_return_exclusion', cv(g('ger_guard_k'), g('ger_after_k')) +
                   scope_state('ger', cv(cohort('stock'), 2000) + cv(cohort('longterm'), 700)),
                   '1201 exceeds movable 2000-100-700=1200 and is refused atomically')
    later += flow('ger', 'nep', 'nep', 500, 2)
    later += check('return_debits_cohort_preserves_fresh_longterm', scope_state('ger', cv(cohort('stock'), 1500) +
                   cv(cohort('fresh'), 100) + cv(cohort('longterm'), 700) + cv(cohort('integrated'), 1400)) +
                   scope_state('nep', cv(cohort('stock'), 0)), 'Return500 leaves1500 stock,100 fresh,700 longterm,1400 integrated; home gets no refugee copy')
    later += seed('fra', 700, age=60, integrated=560, longterm=350)
    later += flow('ger', 'fra', 'fra', 700, 3)
    later += check('onward_preserves_origin_and_settled_residents', scope_state('ger', cv(cohort('stock'), 800) +
                   cv(cohort('fresh'), 100) + cv(cohort('longterm'), 700) + cv(cohort('integrated'), 700)) +
                   scope_state('fra', cv(cohort('stock'), 1400) + cv(cohort('fresh'), 700) +
                   cv(cohort('longterm'), 350) + cv(cohort('integrated'), 560)),
                   'Only700 movable people relocate, same origin; source and target settled residents remain')
    later += check('receiving_cohort_native_weighted_age', scope_state('fra', cv(cohort('age'), 30)),
                   '700 residents aged60 plus700 new arrivals give weighted age30')
    later += flow('ger', 'nep', 'nep', 1, 2) + capture_population('guard')
    later += check('no_return_of_fresh_or_settled_remainder', scope_state('ger', cv(cohort('stock'), 800) +
                   cv(cohort('fresh'), 100) + cv(cohort('longterm'), 700)), 'Stock800 equals100 fresh+700 settled; nothing can return')
    later += flow(amount=250, kind=4)
    later += check('workers_have_separate_origin_indexed_stock', scope_state('ger',
                   cv(f'eon_labor_stock^{origin_slot}', 250) + cv(cohort('stock'), 800)),
                   '250 worker receipts enter labor ledger without a refugee copy')
    later += capture_population('settled')
    later += check('all_settlements_conserve_real_population', untouched('settled'), 'All valid returns/onward/worker movements conserve actual three-state population')

    # Execute the actual origin-slot loop, not just a manually pointed return.
    later += seed('ger', 10000, age=3)
    later += ('GER = { ' + setv('eon_refugee_month_returned', 0) + setv('gdp_per_capita', 10) + ' } '
              'NEP = { ' + setv('gdp_per_capita', 10) + setv('eon_migration_peace_months', 3) +
              setv('eon_migration_home_control_ratio', 1) + ' } ')
    later += capture_owned_population('return_before')
    later += scope_state('ger', 'eon_migration_process_refugee_cohorts = yes ')
    later += capture_owned_population('return_after')
    later += setv(g('return_source_loss'), g('ger_return_before_owned_k'))
    later += f'subtract_from_variable = {{ {g("return_source_loss")} = {g("ger_return_after_owned_k")} }} '
    later += f'multiply_variable = {{ {g("return_source_loss")} = 1000 }} '
    later += setv(g('return_target_gain'), g('nep_return_after_owned_k'))
    later += f'subtract_from_variable = {{ {g("return_target_gain")} = {g("nep_return_before_owned_k")} }} '
    later += f'multiply_variable = {{ {g("return_target_gain")} = 1000 }} '
    later += f'log = "{MARK} OBS actual_return origin_token=[?global.eon_migration_origin_country] source_loss=[?{g("return_source_loss")}] target_gain=[?{g("return_target_gain")}]" '
    later += check('actual_cohort_loop_resolves_full_origin_and_returns_voluntarily', cv(g('return_source_loss'), 200) +
                   cv(g('return_target_gain'), 200) + cv('global.eon_migration_origin_country', g('nep_id')) +
                   scope_state('ger', cv(cohort('stock'), 9800)) + 'GER = { ' + cv('eon_refugee_month_returned', 200) + ' }',
                   'Actual registry-slot cohort loop resolves peaceful NEP full token and returns200/10000; all-owned population and receipt agree')

    later += 'GER = { eon_migration_refresh_country = yes } '
    later += check('twenty_million_population_capacity', 'GER = { ' + cv('eon_refugee_capacity', 400000) + ' }',
                   'Population20 million gives reception capacity400000')
    later += setv(g('large_count'), 20) + f'multiply_variable = {{ {g("large_count")} = 1000000 }} '
    later += setv(g('large_count_m'), g('large_count')) + f'divide_variable = {{ {g("large_count_m")} = 1000000 }} '
    later += f'log = "{MARK} OBS large_count raw=[?{g("large_count")}] millions=[?{g("large_count_m")}]" '
    later += check('twenty_million_counter_roundtrip', cv(g('large_count_m'), 20),
                   '20*1000000 then /1000000 must remain20, exposing native fixed-point saturation')
    later += ('GER = { ' + setv('eon_migration_month_in', g('large_count')) +
              setv('eon_migration_month_out', 0) + 'eon_migration_display_rates = yes } ')
    later += f'GER = {{ log = "{MARK} OBS display capacity=[?eon_refugee_capacity] annual_rate=[?net_immigration_rate]" }} '
    later += check('twenty_million_display_denominator', 'GER = { ' + cv('net_immigration_rate', 12) + ' }',
                   '20million net people /20million population annualized gives12, without overflow')

    later += seed('ger', 200000)
    later += ('GER = { clr_country_flag = eon_refugee_fund_week_consumed ' + setv('eon_refugee_relief_fund', .1) +
              'eon_migration_relief_weekly = yes } ')
    later += f'GER = {{ log = "{MARK} OBS weekly cost=[?eon_refugee_weekly_cost] paid=[?eon_refugee_weekly_fund_paid] fund=[?eon_refugee_relief_fund]" }} '
    later += check('weekly_refugee_fund_exact_native_debit', 'GER = { ' + cv('eon_refugee_weekly_cost', .015) +
                   cv('eon_refugee_weekly_fund_paid', .015) + cv('eon_refugee_relief_fund', .085) +
                   cv('eon_refugee_weekly_net_cost', 0) + 'has_country_flag = eon_refugee_fund_week_consumed }',
                   '200000 people at GDP10 cost.015; fund.1 becomes.085 and paid/net=.015/0')
    later += 'GER = { eon_migration_relief_weekly = yes } '
    later += check('weekly_fund_second_call_inert', 'GER = { ' + cv('eon_refugee_relief_fund', .085) +
                   cv('eon_refugee_weekly_fund_paid', .015) + ' }', 'The same native week cannot spend the fund twice')
    later += seed('ger', 200000, integrated=200000, longterm=200000)
    later += 'GER = { eon_migration_refresh_country = yes } '
    later += check('longterm_residents_leave_emergency_spending', 'GER = { ' + cv('eon_refugee_weekly_cost', 0) +
                   cv('eon_refugees_hosted', 200000) + cv('eon_refugees_longterm', 200000) + ' }',
                   '200000 settled residents still exist but have no extra emergency cost')

    # Real helper scopes mirror native action ROOT donor/importer and THIS GER.
    later += ('set_variable = { treasury = 10 } GER = { ' + setv('eon_refugee_relief_fund', 0) +
              'eon_humanitarian_aid_send_offer = yes } ')
    later += check('humanitarian_native_root_donor_this_recipient', 'GER = { ROOT = { tag = NEP '
                   'has_country_flag = eon_humanitarian_aid_pending ' + cv('eon_humanitarian_aid_partner', 'PREV') +
                   cv('treasury', 10) + ' } ' + cv('eon_refugee_relief_fund', 0) + ' }',
                   'Sending reserves NEP donor→GER recipient, with no monetary payment')
    later += 'GER = { eon_humanitarian_aid_accept_offer = yes eon_humanitarian_aid_accept_offer = yes } '
    later += check('humanitarian_accept_exact_once_restricted_fund', cv('treasury', 9.9) +
                   'NOT = { has_country_flag = eon_humanitarian_aid_pending } GER = { ' +
                   cv('eon_refugee_relief_fund', .1) + ' }', 'Two accept calls debit NEP once.1 and credit only GER civilian fund.1')
    later += ('GER = { ' + setv('total_unemployed_percentage_display', .2) +
              setv('unemployment_threshold_display_var', .06) +
              'add_dynamic_modifier = { modifier = high_unemployment_modifier } '
              'add_opinion_modifier = { target = ROOT modifier = migration_agreement_opinion } '
              'eon_migration_treaty_start = yes } ')
    later += observe_treaty('started')
    later += check('treaty_native_importer_exporter_pending_pair', cv('pending_migration_agreement_country', g('ger_id')) +
                   'GER = { ' + cv('eon_migration_treaty_pending_sender', 'ROOT.id') + ' }',
                   'ROOT NEP importer records GER exporter; GER records exact ROOT sender')
    later += check('treaty_response_valid_before_accept', 'GER = { eon_migration_treaty_response_valid = yes }',
                   'The exact native pending pair and all production execution-time terms still validate')
    later += 'GER = { eon_migration_treaty_establish = yes } '
    later += observe_treaty('established')
    later += check('treaty_accept_bilateral_flags', 'GER = { ROOT = { has_country_flag = migration_agreement_migrants_add@PREV } } '
                   'GER = { has_country_flag = migration_agreement_migrants_cut@ROOT }',
                   'Production establish creates reciprocal importer/exporter flags on the exact native pair')
    later += check('treaty_accept_counters_match_one_pair', cv('migrants_add', .05) +
                   'GER = { ' + cv('migrants_cut', -.05) + ' }',
                   'Counter reconciliation sees the native reciprocal pair and produces exactly+.05/-.05')
    later += setv(g('accepted_add'), 'migrants_add') + 'GER = { ' + setv(g('accepted_cut'), 'migrants_cut') + ' } '
    later += 'GER = { eon_migration_treaty_finish_response = yes eon_migration_treaty_establish = yes } '
    later += observe_treaty('drained')
    later += check('treaty_pending_drained_and_duplicate_inert', cv('pending_migration_agreement_country', 0) +
                   cv('eon_migration_treaty_pending_terms', 0) + cv('migrants_add', g('accepted_add')) +
                   'GER = { ' + cv('eon_migration_treaty_pending_sender', 0) + cv('eon_migration_treaty_pending_terms', 0) +
                   cv('migrants_cut', g('accepted_cut')) + ' }',
                   'Both native pending records drain; duplicate establish cannot change the accepted counters')
    later += ('NEP = { ' + setv('average_worker_fulfillment', .5) + setv('population_total_m', 20) +
              setv('eon_labor_month_arrived', 0) + 'eon_migration_refresh_country = yes } ')
    later += capture_owned_population('labor_before')
    later += 'GER = { eon_migration_labor_departures = yes } '
    later += capture_owned_population('labor_after')
    later += setv(g('labor_source_loss'), g('ger_labor_before_owned_k'))
    later += f'subtract_from_variable = {{ {g("labor_source_loss")} = {g("ger_labor_after_owned_k")} }} '
    later += f'multiply_variable = {{ {g("labor_source_loss")} = 1000 }} '
    later += setv(g('labor_target_gain'), g('nep_labor_after_owned_k'))
    later += f'subtract_from_variable = {{ {g("labor_target_gain")} = {g("nep_labor_before_owned_k")} }} '
    later += f'multiply_variable = {{ {g("labor_target_gain")} = 1000 }} '
    later += f'log = "{MARK} OBS labor source_loss=[?{g("labor_source_loss")}] target_gain=[?{g("labor_target_gain")}]" '
    later += check('actual_labor_router_moves_under_active_treaty', cv(g('labor_source_loss'), 0, 'greater_than') +
                   cv(g('labor_source_loss'), g('labor_target_gain')) +
                   'NEP = { ' + cv('eon_labor_month_arrived', g('labor_target_gain')) + ' }',
                   'Actual production GER exporter router moves workers to NEP importer; all-owned-state loss/gain and labor receipt agree')
    later += 'GER = { eon_migration_treaty_cancel_pair = yes eon_migration_treaty_cancel_pair = yes } '
    later += check('treaty_cancel_keeps_residents_and_removes_modifiers', cv('migrants_add', 0) +
                   'NOT = { has_dynamic_modifier = { modifier = migrants_agreement_add } } '
                   'GER = { ' + cv('migrants_cut', 0) + 'NOT = { has_dynamic_modifier = { modifier = migrants_agreement_cut } } } ' +
                   scope_state('ger', cv(cohort('stock'), 200000)), 'Repeated cancellation clears agreement scalars/modifiers and keeps every resident')

    # Private end-of-probe war, after native primitive success. No combat tick is
    # needed: this tests has_war safety and controlled damaged domestic needs.
    later += 'GER = { if = { limit = { is_in_faction = yes } leave_faction = yes } } FRA = { if = { limit = { is_in_faction = yes } leave_faction = yes } } '
    later += observe_wars('before_private_war')
    later += 'GER = { declare_war_on = { target = FRA type = annex_everything } } '
    later += observe_wars('after_private_war')
    later += check('private_war_activates_safety_guard', 'GER = { has_war = yes has_war_with = FRA } '
                   'FRA = { has_war = yes has_war_with = GER }',
                   'Independent private GER/FRA genuinely declare war on each other after primitive success')
    later += scope_state('ger', 'damage_building = { type = infrastructure damage = 1 } ')
    later += ('GER = { clr_country_flag = eon_refugee_fund_week_consumed ' + setv('gdp_per_capita', 10) +
              setv('eon_refugee_relief_fund', .1) + 'eon_migration_relief_weekly = yes } ')
    later += f'GER = {{ log = "{MARK} OBS domestic need=[?eon_civilian_relief_need] cost=[?eon_refugee_weekly_cost] paid=[?eon_refugee_weekly_fund_paid] fund=[?eon_refugee_relief_fund]" }} '
    later += check('domestic_wartime_relief_native_need_and_fund', 'GER = { ' + cv('eon_civilian_relief_need', 20000) +
                   cv('eon_refugee_weekly_cost', .0015) + cv('eon_refugee_weekly_fund_paid', .0015) +
                   cv('eon_refugee_relief_fund', .0985) + ' }',
                   'Controlled damaged core need20000 costs20000*.05/1million*1.5=.0015; fund.1 becomes.0985')
    later += 'GER = { eon_migration_relief_weekly = yes } '
    later += check('domestic_weekly_second_call_inert', 'GER = { ' + cv('eon_refugee_relief_fund', .0985) + ' }',
                   'Domestic humanitarian relief also consumes the fund only once per native week')
    # One willing distant receiver with exactly1000 places. Source exposure may
    # include other GER border states, so total requested/unplaced is observed;
    # all native source-state population receipts must still sum to1000 moved.
    later += ('every_country = { ' + setv(P + 'saved_policy', 'eon_refugee_policy') +
              setv('eon_refugee_policy', 0) + 'eon_migration_refresh_country = yes } '
              'NEP = { ' + setv('population_total_m', 1) + setv('eon_refugee_policy', 2) +
              setv('eon_refugee_month_arrived', 0) + ' } GER = { ' +
              setv('eon_refugee_month_unplaced', 0) + ' } ')
    later += 'NEP = { GER = { set_country_flag = eon_diplomatic_relations_established@PREV } } '
    later += scope_state('nep', 'eon_migration_prepare_state_ledger = yes ' + ''.join(
        setv(f'eon_refugee_{name}^global.{P}ger_slot', value)
        for name, value in (('stock', 29000), ('fresh', 0), ('age', 60), ('integrated', 29000), ('longterm', 29000))
    ) + 'eon_migration_recount_state = yes ')
    later += 'NEP = { eon_migration_refresh_country = yes } '
    later += f'log = "{MARK} OBS distant_capacity hosted=[?eon_refugees_hosted] capacity=[?eon_refugee_capacity] remaining=[?eon_refugee_capacity_remaining] policy=[?eon_refugee_policy] ger_token=[?{g("ger_id")}] ger_slot=[?{g("ger_slot")}]" '
    later += check('distant_refugee_fixture_has_exact_capacity', cv('eon_refugee_capacity_remaining', 1000) +
                   cv('eon_refugee_policy', 2) + 'NEP = { GER = { has_country_flag = eon_diplomatic_relations_established@PREV } }',
                   'Only willing distant NEP has exactly1000 free places via the existing GER diplomatic channel')
    later += capture_owned_population('refugee_before')
    later += 'GER = { eon_migration_refugee_departures = yes } '
    later += capture_owned_population('refugee_after')
    later += setv(g('refugee_source_loss'), g('ger_refugee_before_owned_k'))
    later += f'subtract_from_variable = {{ {g("refugee_source_loss")} = {g("ger_refugee_after_owned_k")} }} '
    later += f'multiply_variable = {{ {g("refugee_source_loss")} = 1000 }} '
    later += setv(g('refugee_target_gain'), g('nep_refugee_after_owned_k'))
    later += f'subtract_from_variable = {{ {g("refugee_target_gain")} = {g("nep_refugee_before_owned_k")} }} '
    later += f'multiply_variable = {{ {g("refugee_target_gain")} = 1000 }} '
    later += f'GER = {{ log = "{MARK} OBS refugee_router actual_loss=[?{g("refugee_source_loss")}] actual_gain=[?{g("refugee_target_gain")}] unplaced=[?eon_refugee_month_unplaced]" }} '
    later += check('actual_refugee_router_partial_capacity_conserves_population', cv(g('refugee_source_loss'), 1000) +
                   cv(g('refugee_target_gain'), 1000) + cv('eon_refugee_month_arrived', 1000),
                   'Actual wartime departure/distant admission helpers move exactly1000 people; all-owned-state debit/credit and receipt agree')
    later += check('actual_refugee_router_retains_unplaced_remainder', 'GER = { ' +
                   cv('eon_refugee_month_unplaced', 19000, 'greater_than_or_equals') + ' } ' +
                   cv('eon_refugee_capacity_remaining', 0),
                   'At least one20000 candidate leaves at least19000 unplaced; only1000 receiver places are spent')
    later += 'every_country = { ' + setv('eon_refugee_policy', P + 'saved_policy') + ' } '
    later += seed('ger', 1000, fresh=1000, age=0)
    later += seed('fra', 10000, age=2)
    later += ('GER = { ' + setv('eon_migration_peace_months', 9) +
              'eon_migration_update_home_safety = yes } NEP = { ' + setv('gdp_per_capita', 10) + setv('eon_migration_peace_months', 3) +
              'eon_migration_update_home_safety = yes } ')
    later += 'FRA = { ' + setv('gdp_per_capita', 10) + ' } '
    later += check('monthly_home_safety_actual_war_and_peace', 'GER = { ' + cv('eon_migration_peace_months', 0) +
                   'eon_migration_safe_return_country = no } NEP = { ' + cv('eon_migration_peace_months', 4) + ' }',
                   'Actual GER war resets peace9→0 and blocks return; peaceful NEP increments3→4')
    # The real peaceful home-control share may be below1 after the bookmark's
    # civil war. Freeze that native share as the expected calibrated return.
    later += setv(g('monthly_expected_return'), 'eon_migration_home_control_ratio')
    later += f'multiply_variable = {{ {g("monthly_expected_return")} = 200 }} round_variable = {g("monthly_expected_return")} '
    later += setv(g('monthly_expected_fra_stock'), 10000)
    later += f'subtract_from_variable = {{ {g("monthly_expected_fra_stock")} = {g("monthly_expected_return")} }} '
    later += capture_owned_population('monthly_before') + capture_world_population('before')
    later += 'clr_global_flag = eon_migration_month_consumed eon_migration_monthly_pulse = yes '
    later += capture_owned_population('monthly_after') + capture_world_population('after')
    later += setv(g('monthly_nep_gain'), g('nep_monthly_after_owned_k'))
    later += f'subtract_from_variable = {{ {g("monthly_nep_gain")} = {g("nep_monthly_before_owned_k")} }} '
    later += f'multiply_variable = {{ {g("monthly_nep_gain")} = 1000 }} '
    later += setv(g('monthly_world_delta_k'), g('world_after_k'))
    later += f'subtract_from_variable = {{ {g("monthly_world_delta_k")} = {g("world_before_k")} }} '
    later += f'log = "{MARK} OBS monthly_origin return_expected=[?{g("monthly_expected_return")}] home_gain=[?{g("monthly_nep_gain")}] world_delta_k=[?{g("monthly_world_delta_k")}]" '
    later += check('monthly_registry_origin_return_and_world_conservation', cv(g('monthly_expected_return'), 0, 'greater_than') +
                   cv(g('monthly_nep_gain'), g('monthly_expected_return')) +
                   cv(g('monthly_world_delta_k'), -.001, 'greater_than') + cv(g('monthly_world_delta_k'), .001, 'less_than') +
                   scope_state('fra', cv(cohort('stock'), g('monthly_expected_fra_stock'))) +
                   'FRA = { ' + cv('eon_refugee_month_returned', g('monthly_expected_return')) + ' } ' +
                   cv(f'global.eon_migration_origins^{origin_slot}', g('nep_id')),
                   'Actual monthly slot loop returns the native home-control-calibrated share to exact NEP token; all STATE population conserved within less than1person rounding')
    later += check('monthly_world_fresh_phase_and_origin_age', scope_state('ger', cv(cohort('stock'), 1000) +
                   cv(cohort('fresh'), 0) + cv(cohort('age'), 1)) +
                   'has_global_flag = eon_migration_month_consumed NEP = { ' + cv('eon_migration_peace_months', 5) + ' }',
                   'One explicit real world pulse clears prior fresh1000, increments age0→1 and safety once')
    later += 'eon_migration_monthly_pulse = yes '
    later += check('monthly_second_pulse_locked', scope_state('ger', cv(cohort('age'), 1)) +
                   'NEP = { ' + cv('eon_migration_peace_months', 5) + ' }', 'Repeated monthly pulse is inert under production27-day global lock')
    later += check('monthly_final_scratch_all_clear', ''.join(cv('global.eon_migration_' + name, 0)
                   for name in ('amount', 'debit', 'source_state', 'target_state', 'origin_country', 'origin_slot',
                                'target_country', 'previous_host', 'return_gdpc', 'kind')),
                   'All ten production global scratch fields, including the separate origin slot, are clear after world update')

    # Run copy observations last. Keep the first dynamic country alive using
    # one exact unledgered NZL state, so the engine cannot recycle its landless
    # tag for the second callback. No wars, aid consent or world pulses follow.
    ledger_names = ('refugee_stock', 'refugee_fresh', 'refugee_age',
                    'refugee_integrated', 'refugee_longterm', 'labor_stock')
    copy_index, copy_value = P + 'copy_index', P + 'copy_value'
    for tag in ('nep', 'ger', 'fra'):
        snapshot = ''
        for name in ledger_names:
            size, array = P + 'copy_' + name + '_size', P + 'copy_' + name
            snapshot += setv(size, 0)
            snapshot += (f'for_each_loop = {{ array = eon_{name} index = {copy_index} value = {copy_value} '
                         f'add_to_variable = {{ {size} = 1 }} }} ')
            snapshot += f'resize_array = {{ array = {array} size = {size} value = 0 }} '
            snapshot += (f'for_each_loop = {{ array = eon_{name} index = {copy_index} value = {copy_value} ' +
                         setv(f'{array}^{copy_index}', copy_value) + '} ')
        later += scope_state(tag, snapshot)
    later += setv(g('test_keepalive_state'), 0)
    later += ('NZL = { random_owned_controlled_state = { limit = { is_core_of = PREV '
              'NOT = { has_state_flag = eon_migration_has_ledger } ' +
              cv('eon_refugees_total', 0) + cv('eon_labor_migrants_total', 0) +
              '} ' + setv(g('test_keepalive_state'), 'THIS') +
              setv(g('test_keepalive_population_k'), 'state_population_k') + ' } } ')
    keepalive_state = lambda content: f'var:{g("test_keepalive_state")} = {{ {content} }} '
    later += check('private_keepalive_state_is_unledgered_NZL_territory',
                   cv(g('test_keepalive_state'), 0, 'not_equals') +
                   keepalive_state('is_owned_by = NZL is_controlled_by = NZL '
                                   'NOT = { has_state_flag = eon_migration_has_ledger } ' +
                                   cv('eon_refugees_total', 0) + cv('eon_labor_migrants_total', 0)),
                   'Exactly one private NZL owned/controlled state has no migration ledger and no refugee/labor stock before the final keepalive transfer')
    later += setv('eon_refugee_relief_fund', .1) + setv('eon_refugee_weekly_fund_paid', .01)
    later += 'set_country_flag = eon_refugee_fund_week_consumed '
    later += setv(g('copy_source_treasury'), 'treasury')
    later += 'GER = { ' + setv(g('copy_donor_treasury'), 'treasury') + ' } '
    later += setv(g('copy_registry_before_recovery'), 'global.eon_migration_array_size')
    later += setv('eon_migration_origin_slot', g('ger_slot')) + 'eon_migration_initialize_country = yes '

    def copy_source_intact():
        return ('NEP = { ' + cv('eon_migration_origin_slot', g('nep_slot')) +
                cv('eon_refugee_relief_fund', .1) + cv('eon_refugee_weekly_fund_paid', .01) +
                cv('treasury', g('copy_source_treasury')) +
                'has_country_flag = eon_refugee_fund_week_consumed } GER = { ' +
                cv('treasury', g('copy_donor_treasury')) + ' } ')

    later += check('canonical_slot_recovery_preserves_restricted_fund_and_lock',
                   copy_source_intact() + cv('global.eon_migration_array_size', g('copy_registry_before_recovery')),
                   'Existing NEP token recovers its original slot while preserving fund0.1, paid0.01, weekly lock and both treasuries')

    def dynamic_copy_probe(label, simulated=False):
        prefix = 'SIMULATED_COPY' if simulated else 'NEW_RAW'
        result = setv(g(label + '_size_before'), 'global.eon_migration_array_size')
        result += setv(g(label + '_size_expected'), 'global.eon_migration_array_size')
        result += f'add_to_variable = {{ {g(label + "_size_expected")} = 1 }} '
        result += 'create_dynamic_country = { original_tag = NEP copy_tag = NEP '
        # These observations precede every migration helper and simulated seed.
        result += setv(g(label + '_id'), 'THIS.id')
        for name, variable in (('raw_slot', 'eon_migration_origin_slot'),
                               ('raw_fund', 'eon_refugee_relief_fund'),
                               ('raw_paid', 'eon_refugee_weekly_fund_paid')):
            result += setv(g(label + '_' + name), variable)
        for name, flag in (('raw_initialized', 'eon_migration_relief_initialized'),
                           ('raw_weeklock', 'eon_refugee_fund_week_consumed')):
            result += setv(g(label + '_' + name), 0)
            result += ('if = { limit = { has_country_flag = ' + flag + ' } ' +
                       setv(g(label + '_' + name), 1) + '} ')
        result += setv(g(label + '_mapped_slot_before_seed'), 0)
        result += (f'for_each_loop = {{ array = global.eon_migration_origins '
                   f'index = {P}copy_registry_index value = {P}copy_registry_token '
                   'if = { limit = { ' + cv(P + 'copy_registry_token', 'THIS') + '} ' +
                   setv(g(label + '_mapped_slot_before_seed'), P + 'copy_registry_index') + '} } ')
        result += setv(g(label + '_mapsize_before_seed'), 'global.eon_migration_array_size')
        result += (f'log = "{MARK} OBS {prefix} token=[?{g(label + "_id")}] '
                   f'fund=[?{g(label + "_raw_fund")}] paid=[?{g(label + "_raw_paid")}] '
                   f'slot=[?{g(label + "_raw_slot")}] initialized=[?{g(label + "_raw_initialized")}] '
                   f'weeklock=[?{g(label + "_raw_weeklock")}] '
                   f'mapped_slot_before_seed=[?{g(label + "_mapped_slot_before_seed")}] '
                   f'mapsize_before_seed=[?{g(label + "_mapsize_before_seed")}]" ')
        result += observe_bool(prefix + '_initialized', cv(g(label + '_raw_initialized'), 1))
        result += observe_bool(prefix + '_weeklock', cv(g(label + '_raw_weeklock'), 1))
        if simulated:
            result += check('simulated_copy_has_new_full_token_before_any_seed',
                            cv(g(label + '_id'), g('native_dynamic_copy_id'), 'not_equals') +
                            cv(g(label + '_id'), g('nep_id'), 'not_equals'),
                            'The second callback has a genuinely distinct full token before inherited finance fields are seeded; the first dynamic country remains alive')
            # create_dynamic_country can run production initialization before
            # child effects. Freeze the exact pre-seed map as the contract:
            # existing full token must recover/preserve; unmapped must clear.
            result += setv(g(label + '_expected_slot'), g(label + '_mapsize_before_seed'))
            result += setv(g(label + '_expected_mapsize'), g(label + '_mapsize_before_seed'))
            result += f'add_to_variable = {{ {g(label + "_expected_mapsize")} = 1 }} '
            result += setv(g(label + '_expected_fund'), 0) + setv(g(label + '_expected_paid'), 0)
            result += setv(g(label + '_expected_weeklock'), 0)
            result += ('if = { limit = { ' + cv(g(label + '_mapped_slot_before_seed'), 0, 'greater_than') + '} ' +
                       setv(g(label + '_expected_slot'), g(label + '_mapped_slot_before_seed')) +
                       setv(g(label + '_expected_mapsize'), g(label + '_mapsize_before_seed')) +
                       setv(g(label + '_expected_fund'), .1) + setv(g(label + '_expected_paid'), .01) +
                       setv(g(label + '_expected_weeklock'), 1) +
                       f'log = "{MARK} OBS SIMULATED_COPY_EXPECT_MAPPED_RECOVERY" }} '
                       f'else = {{ log = "{MARK} OBS SIMULATED_COPY_EXPECT_UNMAPPED_CLEAR" }} ')
            # Separate deterministic regression: do not imply native copy_tag
            # necessarily copies all these fields. The raw callback above says.
            result += setv('eon_migration_origin_slot', g('nep_slot'))
            result += setv('eon_refugee_relief_fund', .1) + setv('eon_refugee_weekly_fund_paid', .01)
            result += 'set_country_flag = eon_migration_relief_initialized set_country_flag = eon_refugee_fund_week_consumed '
            result += (f'log = "{MARK} OBS SIMULATED_COPY_SEEDED '
                       'fund=[?eon_refugee_relief_fund] paid=[?eon_refugee_weekly_fund_paid] '
                       'slot=[?eon_migration_origin_slot]" ')
        expected_slot = g(label + '_expected_slot') if simulated else g(label + '_size_before')
        expected_mapsize = g(label + '_expected_mapsize') if simulated else g(label + '_size_expected')
        expected_fund = g(label + '_expected_fund') if simulated else 0
        expected_paid = g(label + '_expected_paid') if simulated else 0
        expected_lock = ('OR = { AND = { ' + cv(g(label + '_expected_weeklock'), 0) +
                         'NOT = { has_country_flag = eon_refugee_fund_week_consumed } } AND = { ' +
                         cv(g(label + '_expected_weeklock'), 1) +
                         'has_country_flag = eon_refugee_fund_week_consumed } } ') if simulated else 'NOT = { has_country_flag = eon_refugee_fund_week_consumed } '

        def freeze_after(phase):
            snapshot = ''
            for name, variable in (('slot', 'eon_migration_origin_slot'), ('fund', 'eon_refugee_relief_fund'),
                                   ('paid', 'eon_refugee_weekly_fund_paid'), ('mapsize', 'global.eon_migration_array_size')):
                snapshot += setv(g(label + '_' + phase + '_' + name), variable)
            snapshot += setv(g(label + '_' + phase + '_weeklock'), 0)
            snapshot += ('if = { limit = { has_country_flag = eon_refugee_fund_week_consumed } ' +
                         setv(g(label + '_' + phase + '_weeklock'), 1) + '} ')
            snapshot += (f'log = "{MARK} OBS {prefix}_{phase.upper()} '
                         f'fund=[?{g(label + "_" + phase + "_fund")}] '
                         f'paid=[?{g(label + "_" + phase + "_paid")}] '
                         f'weeklock=[?{g(label + "_" + phase + "_weeklock")}] '
                         f'slot=[?{g(label + "_" + phase + "_slot")}] '
                         f'mapsize=[?{g(label + "_" + phase + "_mapsize")}]" ')
            return snapshot

        result += 'eon_migration_initialize_country = yes '
        result += freeze_after('after_first_helper')
        result += setv(g(label + '_slot'), 'eon_migration_origin_slot')
        result += check(label + '_distinct_append_only_slot',
                        cv(g(label + '_id'), g('nep_id'), 'not_equals') +
                        cv('eon_migration_origin_slot', expected_slot) +
                        cv('global.eon_migration_array_size', expected_mapsize) +
                        cv(f'global.eon_migration_origins^{g(label + "_slot")}', 'THIS') +
                        cv(f'global.eon_migration_origins^{g("nep_slot")}', g('nep_id')),
                        ('Frozen pre-seed exact registry state selects canonical recovery without growth or one append for a truly unmapped token; original mapping remains intact' if simulated else
                         'New dynamic full token gets exactly one new registry slot; the original full-token mapping remains intact'))
        if simulated:
            result += check('simulated_copy_fund_matches_frozen_registry_contract', cv('eon_refugee_relief_fund', expected_fund),
                            'Already-mapped token preserves seeded fund0.1; truly unmapped copied token must clear it to0')
            result += check('simulated_copy_paid_matches_frozen_registry_contract', cv('eon_refugee_weekly_fund_paid', expected_paid),
                            'Already-mapped token preserves paid0.01; truly unmapped copied token must clear it to0')
            result += check('simulated_copy_weeklock_matches_frozen_registry_contract', expected_lock,
                            'Already-mapped token preserves the seeded weekly lock; truly unmapped copied token must remove it')
            result += check('simulated_copy_source_finance_remains_intact', copy_source_intact(),
                            'Both classification branches preserve original NEP fund0.1/paid0.01/lock and both recorded treasuries')
        result += check(label + '_restricted_fund_not_cloned',
                        cv('eon_refugee_relief_fund', expected_fund) + cv('eon_refugee_weekly_fund_paid', expected_paid) +
                        expected_lock + copy_source_intact(),
                        ('Frozen pre-seed mapping strictly selects preserved0.1/0.01/lock for canonical recovery or cleared0/0/no lock for genuinely unmapped inherited fields; source remains intact' if simulated else
                         'Actual native copied fields yield new-country fund0/paid0/no weekly lock; original fund0.1/paid0.01/lock and treasuries are preserved'))
        result += 'eon_migration_initialize_country = yes eon_migration_register_country = yes '
        result += freeze_after('after_repeat_helper')
        result += check(label + '_repeat_registration_is_inert',
                        cv('global.eon_migration_array_size', expected_mapsize) +
                        cv('eon_migration_origin_slot', g(label + '_slot')) +
                        cv('eon_refugee_relief_fund', expected_fund) + cv('eon_refugee_weekly_fund_paid', expected_paid) +
                        expected_lock + copy_source_intact(),
                        'Repeated registration preserves the exact frozen branch result and map size, without altering original finance')
        # A landless dynamic tag cannot accept the production humanitarian offer.
        # Seed its post-registration credit boundary explicitly, not a fake UI
        # consent or donor-transfer receipt; aid consent is probed above.
        result += setv('eon_refugee_relief_fund', .2) + setv('eon_refugee_weekly_fund_paid', .015)
        result += 'set_country_flag = eon_refugee_fund_week_consumed '
        result += 'eon_migration_initialize_country = yes eon_migration_register_country = yes '
        result += check(label + '_new_registered_credit_is_preserved',
                        cv('global.eon_migration_array_size', expected_mapsize) +
                        cv('eon_migration_origin_slot', g(label + '_slot')) +
                        cv('eon_refugee_relief_fund', .2) + cv('eon_refugee_weekly_fund_paid', .015) +
                        'has_country_flag = eon_refugee_fund_week_consumed ' + copy_source_intact(),
                        'Explicit post-registration credit0.2, paid0.015 and new weekly lock survive repeated registration; this is a seeded credit-boundary test')
        if not simulated:
            # Native current-mod pattern: new COUNTRY -> chosen STATE ->
            # PREV COUNTRY, then transfer_state=PREV refers to that exact STATE.
            result += keepalive_state('PREV = { transfer_state = PREV } ' +
                                      setv(g('keepalive_population_after_k'), 'state_population_k') +
                                      setv(g('keepalive_owner_after'), 'owner') +
                                      setv(g('keepalive_controller_after'), 'controller'))
            result += (f'log = "{MARK} OBS PRIVATE_KEEPALIVE '
                       f'state=[?{g("test_keepalive_state")}] owner=[?{g("keepalive_owner_after")}] '
                       f'token=[?{g("native_dynamic_copy_id")}] '
                       f'before_k=[?{g("test_keepalive_population_k")}] '
                       f'after_k=[?{g("keepalive_population_after_k")}]" ')
            result += check('first_dynamic_country_alive_after_exact_keepalive_transfer',
                            'exists = yes ' + cv(g('keepalive_owner_after'), g('native_dynamic_copy_id')) +
                            cv(g('keepalive_controller_after'), g('native_dynamic_copy_id')) +
                            cv(g('keepalive_population_after_k'), g('test_keepalive_population_k')) +
                            keepalive_state('is_owned_by = PREV is_controlled_by = PREV '
                                            'NOT = { has_state_flag = eon_migration_has_ledger }'),
                            'First dynamic country exists and owns/controls only the chosen private unledgered NZL state; its actual STATE population is unchanged')
        return result + '} '

    later += dynamic_copy_probe('native_dynamic_copy')
    later += dynamic_copy_probe('simulated_dynamic_copy', simulated=True)
    later += setv(g('copy_ledger_changed'), 0)
    for tag in ('nep', 'ger', 'fra'):
        compare_ledgers = ''
        for name in ledger_names:
            size, array = P + 'copy_' + name + '_size', P + 'copy_' + name
            compare_ledgers += f'set_temp_variable = {{ {P}copy_count_after = 0 }} '
            compare_ledgers += (f'for_each_loop = {{ array = eon_{name} index = {copy_index} value = {copy_value} '
                                f'add_to_temp_variable = {{ {P}copy_count_after = 1 }} '
                                'if = { limit = { NOT = { ' + cv(f'{array}^{copy_index}', copy_value) +
                                '} } ' + setv(g('copy_ledger_changed'), 1) + '} } ')
            compare_ledgers += ('if = { limit = { NOT = { ' + cv(P + 'copy_count_after', size) +
                                '} } ' + setv(g('copy_ledger_changed'), 1) + '} ')
        later += scope_state(tag, compare_ledgers)
    later += check('dynamic_copy_does_not_clone_or_modify_state_cohorts',
                   cv(g('copy_ledger_changed'), 0) + scope_state('ger', cv(cohort('stock'), 1000)) +
                   scope_state('fra', cv(cohort('stock'), g('monthly_expected_fra_stock'))),
                   'Final dynamic callbacks and one private unledgered NZL keepalive transfer preserve every entry and exact length of all six ledger arrays on all three probe states')
    body += 'if = { limit = { ' + cv(g('fails'), 0) + ' } ' + later + '} else = { log = "' + MARK + ' ABORT primitive_gate" } '
    body += f'log = "{MARK} RUN_END passes=[?{g("passes")}] fails=[?{g("fails")}]" '
    fixture = {
        f'events/{NS}.txt': f'add_namespace = {NS}\ncountry_event = {{ id = {NS}.1 hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n',
        f'common/on_actions/!{NS}.txt': ('on_actions = { on_startup = { effect = { '
             f'log = "{MARK} OBS EARLY_BOOT size=[?global.eon_migration_array_size]" '
             f'NEP = {{ log = "{MARK} OBS BEFORE_FIRST_REGISTER '
             'slot=[?eon_migration_origin_slot] fund=[?eon_refugee_relief_fund] size=[?global.eon_migration_array_size]" '
             'eon_migration_initialize_country = yes '
             f'log = "{MARK} OBS AFTER_FIRST_REGISTER '
             'slot=[?eon_migration_origin_slot] fund=[?eon_refugee_relief_fund] size=[?global.eon_migration_array_size]" } } } }\n'),
        f'common/on_actions/{NS}.txt': ('on_actions = { on_startup = { effect = { '
             f'log = "{MARK} STARTUP" ' + setv(g('passes'), 0) + setv(g('fails'), 0) +
             f'NEP = {{ country_event = {{ id = {NS}.1 hours = 8 }} }} }} }} }}\n'),
    }
    for text in fixture.values(): ast(text)
    assert len(assertions) == len(set(assertions))
    if validate_only:
        return {'assertions': assertions, 'expectations': expectations, 'validated_fixture_only': True}
    directories = ('scripted_effects', 'scripted_triggers', 'scripted_diplomatic_actions',
                   'on_actions', 'dynamic_modifiers', 'opinion_modifiers', 'wargoals', 'scripted_localisation')
    dependencies = {str(path.relative_to(source)).replace('\\', '/'): sha(path)
                    for directory in directories for path in sorted((source / 'common' / directory).glob('*.txt'))}
    # A previously prepared frozen source can contain its private fixture. It
    # is bound below as fixture bytes, never as production source simultaneously.
    for rel in fixture: dependencies.pop(rel, None)
    assert all('common/scripted_effects/' + name in dependencies for name in (
        'eon_migration_relief_effects.txt', 'eon_migration_treaty_effects.txt', 'eon_humanitarian_aid_effects.txt'))
    for rel in ('events/eon_humanitarian_aid_events.txt', 'common/defines/MD_defines.lua'):
        dependencies[rel] = sha(source / rel)
    for directory in ('common/decisions', 'localisation/english', 'localisation/russian'):
        for path in sorted((source / directory).rglob('*')):
            if path.is_file() and path.suffix in ('.txt', '.yml'):
                rel = str(path.relative_to(source)).replace('\\', '/')
                dependencies[rel] = sha(path)
    output.mkdir(parents=True)
    for rel, text in fixture.items():
        path = output / 'mod' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    manifest = {
        'kind': 'native_migration_relief', 'schema': 1, 'marker': MARK,
        'assertions': assertions, 'expectations': expectations,
        'source_root': str(source), 'fixture_root': str(output / 'mod'),
        'expected_start_tag': 'NEP', 'countries': ['NEP', 'GER', 'FRA', 'NZL'],
        'source_sha256': dependencies,
        'fixture_sha256': {rel: sha(output / 'mod' / rel) for rel in fixture},
        'required_observations': ['EARLY_BOOT', 'BEFORE_FIRST_REGISTER', 'AFTER_FIRST_REGISTER',
                                  'BEFORE_EVENT_REGISTRY', 'AFTER_EVENT_REGISTRY',
                                  'NEW_RAW', 'NEW_RAW_AFTER_FIRST_HELPER', 'NEW_RAW_AFTER_REPEAT_HELPER',
                                  'SIMULATED_COPY', 'SIMULATED_COPY_AFTER_FIRST_HELPER',
                                  'SIMULATED_COPY_AFTER_REPEAT_HELPER'],
        'documentation_root': str(docs),
        'documentation_sha256': {name: sha(docs / name) for name in
            ('effects_documentation.md', 'triggers_documentation.md', 'dynamic_variables_documentation.md')},
        'limits': ['Private test data and helper execution; no native diplomatic UI consent clicks.',
                   'Actual STATE population_k, not country army reserves, is the conservation receipt.',
                   'Private GER/FRA war begins only after native population/array primitive assertions pass.',
                   'One synchronous world pulse, not a campaign balance, performance, save/reload or multiplayer test.',
                   'Final raw copy_tag and simulated copied-field callbacks use one exact private unledgered NZL state transfer to keep the first tag alive and force a distinct second token.',
                   'Simulated-copy expected cleanup or recovery is bound to the exact full-token registry before seed and the selected branch is logged; a mapped native callback does not exercise unmapped-copy cleanup.',
                   'Dynamic-country post-registration credits are explicitly seeded boundaries, not additional humanitarian consent/donor-transfer proof.',
                   'The20million scaled roundtrip tests that magnitude; it does not prove unbounded native variable capacity.'],
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--docs', type=Path, default=DOCS)
    parser.add_argument('--validate-only', action='store_true', help='Parse generated fixture and expectations without writing output')
    args = parser.parse_args()
    result = build(args.source, args.output, args.docs, args.validate_only)
    print(json.dumps({'prepared': not args.validate_only, 'validated_fixture_only': args.validate_only,
                      'assertions': len(result['assertions']), 'native_tested': False}))
