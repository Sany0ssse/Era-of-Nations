"""Meaningful material/project checks against current uranium source AST."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_model import Model, Source, p


def equal(actual, expected):
    assert math.isclose(actual, expected, abs_tol=1e-6, rel_tol=1e-10), (actual, expected)


def setup(source, stock=0, flow=0, imports=0, facilities=1, enabled=True):
    model = Model(source)
    country = model.country()
    country.variables.update({'eon_natural_uranium_stock_kg': stock,
                              'enrichment_facilities': facilities,
                              'var_reactor_material_stockpile': 0,
                              'nuclear_fuel_consumption': 0})
    # Fixture flow arguments are tU/week; native integer units are100kg/week.
    country.native['resource@uranium'] = flow*10
    country.native['resource_imported@uranium'] = imports*10
    if enabled: country.flags.add('enabled_nuclear_reactor_fuel_production')
    return model


def mine(model, reserve=18000, capacity=18, limit=30, flow=None):
    state = model.state()
    state.variables.update({'eon_uranium_reserve_kg': reserve,
                            'eon_uranium_capacity': capacity,
                            'eon_uranium_capacity_limit': limit,
                            'eon_uranium_applied_output': capacity*10})
    state.native['resource@uranium'] = (capacity if flow is None else flow)*10
    model.country().native['resource@uranium'] = state.native['resource@uranium']
    return state


def weekly(model): model.call('eon_uranium_weekly_materials')


def project(model, count):
    model.effect(p.ast('set_temp_variable = { eon_requested_facilities = '+str(count)+
                       ' } eon_enrichment_begin_project = yes'))


def run(source=None, emit=True):
    source, passed, failed, trace = source or Source(), [], [], []

    def case(name, body):
        try:
            models = body() or []
            for model in models:
                trace.append({'case': name, 'effects': sorted(model.visited_effects),
                              'triggers': sorted(model.visited_triggers),
                              'native_boundaries': model.native_calls})
            passed.append(name)
        except AssertionError as error:
            failed.append({'case': name, 'error': str(error)})

    def initialization_preserves_stocks():
        m = setup(source, stock=1234)
        m.country().variables['var_reactor_material_stockpile'] = 5678
        m.call('eon_uranium_initialize')
        m.call('eon_uranium_initialize')
        assert m.country().variables['eon_natural_uranium_stock_kg'] == 1234
        assert m.country().variables['var_reactor_material_stockpile'] == 5678
        assert 'eon_uranium_country_initialized' in m.country().flags
        return [m]
    case('initialization_preserves_campaign_stocks', initialization_preserves_stocks)

    for old in (2500, 0, None):
        def legacy_migration(old=old):
            m = setup(source, stock=1234)
            m.country().flags.discard('eon_uranium_reactor_stock_in_kg')
            if old is None: m.country().variables.pop('var_reactor_material_stockpile')
            else: m.country().variables['var_reactor_material_stockpile'] = old
            m.call('eon_uranium_initialize')
            if old is None: assert 'var_reactor_material_stockpile' not in m.country().variables
            else: equal(m.country().variables['var_reactor_material_stockpile'], old*57.7)
            assert 'eon_uranium_reactor_stock_in_kg' in m.country().flags
            equal(m.country().variables['eon_natural_uranium_stock_kg'], 1234)
            before = deepcopy(m.country().variables)
            m.call('eon_uranium_initialize')
            assert m.country().variables == before
            if old is None:
                m.country().variables['var_reactor_material_stockpile'] = 99
                m.call('eon_uranium_initialize')
                equal(m.country().variables['var_reactor_material_stockpile'], 99)
            return [m]
        case('legacy_stock_migration_once_uninitialized_'+str(old), legacy_migration)

    def initialized_kg_migration_marker():
        m = setup(source)
        m.country().flags.discard('eon_uranium_reactor_stock_in_kg')
        m.country().flags.add('eon_uranium_country_initialized')
        m.country().variables['var_reactor_material_stockpile'] = 2500
        m.call('eon_uranium_initialize')
        equal(m.country().variables['var_reactor_material_stockpile'], 2500)
        assert 'eon_uranium_reactor_stock_in_kg' in m.country().flags
        m.call('eon_uranium_initialize')
        equal(m.country().variables['var_reactor_material_stockpile'], 2500)
        return [m]
    case('previously_initialized_kg_inventory_is_not_migrated_again', initialized_kg_migration_marker)

    def fresh_startup_kg():
        m = setup(source)
        m.state().native['building_level@nuclear_reactor'] = 2
        m.country().flags.discard('eon_uranium_reactor_stock_in_kg')
        m.call('setup_starting_reactor_stockpile')
        equal(m.country().variables['var_reactor_material_stockpile'], 288500)
        assert 'eon_uranium_reactor_stock_in_kg' in m.country().flags
        m.call('eon_uranium_initialize')
        equal(m.country().variables['var_reactor_material_stockpile'], 288500)
        return [m]
    case('actual_new_game_setup_sets_kg_flag_and_preserves_125_week_buffer', fresh_startup_kg)

    def legacy_focus_reward():
        m = setup(source)
        m.effect(p.ast('set_temp_variable = { change_resource = 100 } change_reactor_grade_material_effect = yes'))
        equal(m.country().variables['var_reactor_material_stockpile'], 5770)
        return [m]
    case('actual_legacy_focus_reward_converts_abstract_units_to_kg', legacy_focus_reward)

    def projection_pure():
        m = setup(source, stock=18000, flow=9, imports=9)
        before = deepcopy(m.country().variables)
        for _ in range(12): m.call('eon_uranium_project_fuel')
        for key in ('eon_natural_uranium_stock_kg', 'var_reactor_material_stockpile'):
            assert m.country().variables[key] == before[key]
        equal(m.country().variables['nuclear_reactor_fuel_production'], 3000)
        assert 'eon_depleted_uranium_stock_kg' not in m.country().variables
        return [m]
    case('projection_repeated_has_no_material_credit', projection_pure)

    def imported_conservation():
        m = setup(source, flow=18, imports=18)
        weekly(m)
        v = m.country().variables
        equal(v['var_reactor_material_stockpile'], 2000)
        equal(v['eon_depleted_uranium_stock_kg'], 16000)
        equal(v['eon_natural_uranium_stock_kg'], 0)
        equal(v['eon_uranium_last_feed_kg'], 18000)
        equal(v['eon_uranium_last_delivered_kg'], v['var_reactor_material_stockpile']+v['eon_depleted_uranium_stock_kg'])
        before = deepcopy(v)
        weekly(m)
        assert m.country().variables == before
        return [m]
    case('imported_flow_ratio9_tails_and_duplicate_week', imported_conservation)

    def no_feed():
        m = setup(source, facilities=999)
        m.call('eon_uranium_project_fuel')
        assert m.country().variables['nuclear_reactor_fuel_production'] == 0
        weekly(m)
        assert m.country().variables['var_reactor_material_stockpile'] == 0
        assert m.country().variables['eon_uranium_last_feed_kg'] == 0
        return [m]
    case('unlimited_facilities_without_feed_produce_nothing', no_feed)

    def partial_capacity():
        m = setup(source, stock=900000, facilities=2)
        weekly(m)
        v = m.country().variables
        equal(v['var_reactor_material_stockpile'], 40000)
        equal(v['eon_natural_uranium_stock_kg'], 540000)
        equal(v['eon_depleted_uranium_stock_kg'], 320000)
        equal(900000, sum(v[key] for key in ('var_reactor_material_stockpile', 'eon_natural_uranium_stock_kg', 'eon_depleted_uranium_stock_kg')))
        return [m]
    case('capacity_limits_processing_without_destroying_extra_feed', partial_capacity)

    def disabled():
        m = setup(source, flow=18, imports=18, enabled=False)
        weekly(m)
        assert m.country().variables['eon_natural_uranium_stock_kg'] == 18000
        assert m.country().variables['var_reactor_material_stockpile'] == 0
        return [m]
    case('disabled_enrichment_keeps_imported_raw_material', disabled)

    def damage():
        m = setup(source, stock=180000)
        m.country().variables['number_of_damaged_enrichment_facilities'] = 1
        weekly(m)
        equal(m.country().variables['var_reactor_material_stockpile'], 8000)
        equal(m.country().variables['eon_natural_uranium_stock_kg'], 108000)
        n = setup(source, stock=180000)
        n.country().native['modifier@nuclear_reactor_fuel_production'] = -2
        weekly(n)
        assert n.country().variables['var_reactor_material_stockpile'] == 0
        return [m, n]
    case('damage_and_negative_modifier_do_not_create_negative_capacity', damage)

    def stock_headroom():
        m = setup(source, stock=18000)
        m.country().variables['var_reactor_material_stockpile'] = 19999990
        weekly(m)
        equal(m.country().variables['var_reactor_material_stockpile'], 20000000)
        equal(m.country().variables['eon_uranium_last_feed_kg'], 90)
        equal(m.country().variables['eon_natural_uranium_stock_kg'], 17910)
        return [m]
    case('finished_stock_headroom_preserves_unprocessed_feed', stock_headroom)

    def reactor_consumption():
        m = setup(source, stock=18000)
        m.country().variables['nuclear_fuel_consumption'] = 1154
        weekly(m)
        equal(m.country().variables['var_reactor_material_stockpile'], 846)
        equal(m.country().variables['eon_uranium_last_reactor_use_kg'], 1154)
        n = setup(source, stock=900)
        n.country().variables['nuclear_fuel_consumption'] = 1154
        weekly(n)
        assert n.country().variables['var_reactor_material_stockpile'] == 0
        equal(n.country().variables['eon_uranium_last_reactor_use_kg'], 100)
        return [m, n]
    case('reactor_use_clips_to_actual_finished_material', reactor_consumption)

    def final_deposit():
        m = setup(source)
        s = mine(m, reserve=10000, capacity=20)
        weekly(m)
        v = m.country().variables
        equal(s.variables['eon_uranium_reserve_kg'], 0)
        equal(s.native['resource@uranium'], 0)
        equal(v['eon_uranium_last_extracted_kg'], 10000)
        equal(v['eon_uranium_last_delivered_kg'], 10000)
        equal(10000, v['eon_natural_uranium_stock_kg']+v['var_reactor_material_stockpile']+v['eon_depleted_uranium_stock_kg'])
        return [m]
    case('finite_last_deposit_credits_final_extraction_before_shutdown', final_deposit)

    def capture():
        m = setup(source)
        s = mine(m, reserve=180000, capacity=18)
        s.owner = 'BBB'
        weekly(m)
        equal(s.variables['eon_uranium_reserve_kg'], 162000)
        equal(m.country().variables['eon_uranium_last_delivered_kg'], 18000)
        assert not m.country('BBB').variables.get('eon_natural_uranium_stock_kg', 0)
        return [m]
    case('captured_deposit_depletes_in_state_and_credits_controller', capture)

    def multiplied_reserve_export_conservation():
        m = setup(source, enabled=False)
        s = mine(m, reserve=9000, capacity=9, limit=30, flow=18)
        s.resource_multiplier = 2
        s.retained_delivered_share = 0.5
        m.country().native['resource@uranium'] = 90
        m.current = '101'
        m.call('eon_uranium_refresh_mine')
        equal(s.variables['eon_uranium_applied_output'], 45)
        equal(s.native['resource@uranium'], 90)
        equal(m.country().native['resource@uranium'], 45)
        # Native delivery and export allocation are explicit fixture oracles.
        # Both countries then execute the real production settlement source.
        m.country('BBB').native.update({'resource@uranium': 45, 'resource_imported@uranium': 45})
        m.country('BBB').variables.update({'enrichment_facilities': 0, 'nuclear_fuel_consumption': 0,
                                           'eon_natural_uranium_stock_kg': 0, 'var_reactor_material_stockpile': 0})
        m.current = m.root = 'AAA'
        weekly(m)
        m.current = m.root = 'BBB'
        weekly(m)
        equal(s.variables['eon_uranium_reserve_kg'], 0)
        equal(m.country().variables['eon_natural_uranium_stock_kg']+
              m.country('BBB').variables['eon_natural_uranium_stock_kg'], 9000)
        return [m]
    case('last_reserve_multiplier2_and_two_country_exports_do_not_duplicate_ore', multiplied_reserve_export_conservation)

    def fractional_reserve():
        m = setup(source)
        s = mine(m, reserve=100, capacity=1, flow=1)
        m.current = '101'
        m.call('eon_uranium_refresh_mine')
        equal(s.variables['eon_uranium_applied_output'], 1)
        equal(s.native['resource@uranium'], 1)
        m.current = 'AAA'
        weekly(m)
        equal(s.variables['eon_uranium_reserve_kg'], 0)
        equal(m.country().variables['eon_uranium_last_delivered_kg'], 100)
        return [m]
    case('fractional_geological_output_100kg_is_finite', fractional_reserve)

    def native_integer_no_ghost():
        m = setup(source, enabled=False)
        s = mine(m, reserve=150, capacity=0.15, flow=0)
        s.variables['eon_uranium_applied_output'] = 0
        m.current = '101'
        m.call('eon_uranium_refresh_mine')
        equal(s.variables['eon_uranium_applied_output'], 1)
        equal(s.native['resource@uranium'], 1)
        m.current = 'AAA'
        weekly(m)
        equal(s.variables['eon_uranium_reserve_kg'], 50)
        equal(s.variables['eon_uranium_applied_output'], 0)
        equal(s.native['resource@uranium'], 0)
        equal(m.country().variables['eon_natural_uranium_stock_kg'], 100)
        m.country().flags.discard('eon_uranium_weekly_settled')
        weekly(m)
        equal(m.country().variables['eon_natural_uranium_stock_kg'], 100)
        equal(s.variables['eon_uranium_reserve_kg'], 50)
        return [m]
    case('native_integer_apply_and_remove_leave_no_ghost_or_free_ore', native_integer_no_ghost)

    for order in (('AAA', 'BBB'), ('BBB', 'AAA')):
        def rights_shared_order(order=order):
            m = setup(source, enabled=False)
            s = mine(m, reserve=9000, capacity=9)
            m.country().native['resource@uranium'] = 0
            m.country('BBB').native.update({'resource@uranium': 90, 'resource_imported@uranium': 0})
            m.country('BBB').variables.update({'eon_natural_uranium_stock_kg': 0,
                                               'var_reactor_material_stockpile': 0,
                                               'enrichment_facilities': 0, 'nuclear_fuel_consumption': 0})
            m.country('BBB').resource_rights['101'] = {'uranium'}
            for actor in order:
                m.current = m.root = actor
                weekly(m)
            equal(s.variables['eon_uranium_reserve_kg'], 0)
            equal(s.variables['eon_uranium_state_last_extracted_kg'], 9000)
            equal(s.variables['eon_uranium_state_last_rights_recipient'], 2)
            equal(s.native['resource@uranium'], 0)
            equal(m.country().variables['eon_natural_uranium_stock_kg'], 0)
            equal(m.country('BBB').variables['eon_natural_uranium_stock_kg'], 9000)
            # Native predicate now returns false at zero output; the saved
            # extraction recipient must preserve the beneficiary's last week.
            assert not m.trigger(p.ast('has_resources_rights = { state = 101 resources = { uranium } }'))
            before = {key: deepcopy(item.variables) for key, item in m.entities.items()}
            for actor in order:
                m.current = m.root = actor
                weekly(m)
            assert before == {key: item.variables for key, item in m.entities.items()}
            # A real later week is supplied explicitly: flags expire and native
            # delivery is refreshed to zero. No remaining deposit means no ore.
            s.flags.discard('eon_uranium_state_weekly_settled')
            for actor in order:
                m.country(actor).flags.discard('eon_uranium_weekly_settled')
                m.country(actor).native['resource@uranium'] = 0
                m.current = m.root = actor
                weekly(m)
            equal(m.country('BBB').variables['eon_natural_uranium_stock_kg'], 9000)
            equal(s.variables['eon_uranium_reserve_kg'], 0)
            return [m]
        case('uranium_rights_shared_final_extraction_'+order[0]+'_first', rights_shared_order)

    for rights in (set(), {'steel'}):
        def false_foreign_claim(rights=rights):
            m = setup(source, enabled=False)
            s = mine(m, reserve=9000, capacity=9)
            m.country('BBB').native['resource@uranium'] = 90
            m.country('BBB').resource_rights['101'] = rights
            m.country('BBB').variables.update({'eon_natural_uranium_stock_kg': 0,
                                               'var_reactor_material_stockpile': 0,
                                               'enrichment_facilities': 0, 'nuclear_fuel_consumption': 0})
            m.current = m.root = 'BBB'
            weekly(m)
            equal(m.country('BBB').variables['eon_natural_uranium_stock_kg'], 0)
            equal(s.variables['eon_uranium_reserve_kg'], 9000)
            assert 'eon_uranium_state_weekly_settled' not in s.flags
            return [m]
        case('foreign_claim_without_uranium_rights_'+('_'.join(rights) if rights else 'none'), false_foreign_claim)

    def mine_project_success():
        m = setup(source)
        m.from_ = '101'
        mine(m, reserve=20000000, capacity=5, limit=15)
        m.country().variables['treasury'] = 0.25
        m.call('eon_uranium_begin_mine_project')
        assert m.country().variables['treasury'] == 0
        assert 'eon_uranium_mine_project' in m.state().flags
        m.call('eon_uranium_begin_mine_project')
        assert m.country().variables['treasury'] == 0
        m.call('eon_uranium_complete_mine_project')
        assert m.state().variables['eon_uranium_capacity'] == 7.5
        assert 'eon_uranium_mine_project' not in m.state().flags
        m.call('eon_uranium_complete_mine_project')
        assert m.state().variables['eon_uranium_capacity'] == 7.5
        assert m.country().variables['treasury'] == 0
        return [m]
    case('mine_project_paid_once_completed_once', mine_project_success)

    def mine_refund():
        m = setup(source)
        m.from_ = '101'
        mine(m, reserve=20000000, capacity=5, limit=15)
        m.country().variables['treasury'] = 1
        m.call('eon_uranium_begin_mine_project')
        equal(m.country().variables['treasury'], 0.75)
        m.state().owner = m.state().controller = 'BBB'
        m.call('eon_uranium_complete_mine_project')
        equal(m.country().variables['treasury'], 1)
        assert m.state().variables['eon_uranium_capacity'] == 5
        m.call('eon_uranium_complete_mine_project')
        equal(m.country().variables['treasury'], 1)
        return [m]
    case('lost_state_refunds_original_project_escrow_only_once', mine_refund)

    for condition in ('at_capacity', 'no_deposit', 'no_cash', 'wrong_owner', 'zero_reserve'):
        def blocked(condition=condition):
            m = setup(source)
            m.from_ = '101'
            mine(m, reserve=20000000, capacity=5, limit=15)
            m.country().variables['treasury'] = 1
            if condition == 'at_capacity': m.state().variables['eon_uranium_capacity'] = 15
            elif condition == 'no_deposit': m.state().variables.pop('eon_uranium_reserve_kg')
            elif condition == 'no_cash': m.country().variables['treasury'] = 0.24
            elif condition == 'wrong_owner': m.state().owner = 'BBB'
            elif condition == 'zero_reserve': m.state().variables['eon_uranium_reserve_kg'] = 0
            before = deepcopy(m.country().variables)
            m.call('eon_uranium_begin_mine_project')
            assert m.country().variables == before
            assert 'eon_uranium_mine_project' not in m.state().flags
            return [m]
        case('mine_start_rejects_'+condition, blocked)

    for capacity, limit, expected in ((0, 15, 1), (12, 15, 15), (0, 0.1, 0.1)):
        def geometric(capacity=capacity, limit=limit, expected=expected):
            m = setup(source)
            m.from_ = '101'
            mine(m, reserve=100, capacity=capacity, limit=limit)
            m.country().techs.clear()
            m.country().variables['treasury'] = 1
            m.call('eon_uranium_begin_mine_project')
            m.call('eon_uranium_complete_mine_project')
            equal(m.country().variables['treasury'], 0.75)
            equal(m.state().variables['eon_uranium_capacity'], expected)
            return [m]
        case('mine_geometric_capacity_'+str(capacity)+'_ceiling_'+str(limit)+'_without_nuclear_tech', geometric)

    def three_facilities():
        m = setup(source, facilities=0)
        m.country().variables['treasury'] = 75
        m.country().native['industrial_complex_total'] = 40
        project(m, 3)
        assert m.country().variables['treasury'] == 0
        assert m.country().variables['enrichment_facilities'] == 0
        assert m.country().variables['eon_enrichment_project_escrow'] == 75
        assert 'energy_building_enrichment_facilities' in m.country().missions
        project(m, 3)
        assert m.country().variables['treasury'] == 0
        m.call('eon_enrichment_complete_project')
        assert m.country().variables['enrichment_facilities'] == 3
        assert m.country().variables['treasury'] == 0
        assert 'eon_enrichment_project_paid' not in m.country().flags
        m.call('eon_enrichment_complete_project')
        assert m.country().variables['enrichment_facilities'] == 3
        return [m]
    case('enrichment_three_reserved_upfront_and_completed_once', three_facilities)

    def enrichment_refund():
        m = setup(source, facilities=0)
        m.country().variables['treasury'] = 100
        project(m, 1)
        assert m.country().variables['treasury'] == 75
        m.call('eon_enrichment_cancel_project')
        assert m.country().variables['treasury'] == 100
        assert 'eon_enrichment_project_paid' not in m.country().flags
        m.call('eon_enrichment_cancel_project')
        assert m.country().variables['treasury'] == 100
        assert m.country().variables['enrichment_facilities'] == 0
        return [m]
    case('enrichment_cancel_refunds_reserved_funds_only_once', enrichment_refund)

    for condition in ('count_overshoot', 'no_cash', 'no_technology', 'bankruptcy', 'mission_pending', 'already_paid', 'negative_count', 'zero_count', 'unsupported_count'):
        def blocked(condition=condition):
            m = setup(source, facilities=0)
            m.country().native['industrial_complex_total'] = 40
            m.country().variables['treasury'] = 75
            count = 3
            if condition == 'count_overshoot': m.country().variables['enrichment_facilities'] = 1
            elif condition == 'no_cash': m.country().variables['treasury'] = 74.99
            elif condition == 'no_technology': m.country().techs.clear()
            elif condition == 'bankruptcy': m.country().missions.add('bankruptcy_incoming_collapse')
            elif condition == 'mission_pending': m.country().missions.add('energy_building_enrichment_facilities')
            elif condition == 'already_paid': m.country().flags.add('eon_enrichment_project_paid')
            elif condition == 'negative_count': count = -1
            elif condition == 'zero_count': count = 0
            elif condition == 'unsupported_count': count = 2
            before = deepcopy(m.country().variables)
            project(m, count)
            assert m.country().variables == before
            return [m]
        case('enrichment_start_rejects_'+condition, blocked)

    def ai_purchase():
        m = setup(source, stock=0)
        m.country().ai = True
        m.country().variables['nuclear_fuel_consumption'] = 1154
        m.country().native['num_of_civilian_factories_available_for_projects'] = 1
        m.country('BBB').native['resource_exported@uranium'] = 80
        m.call('eon_uranium_daily')
        trades = [row for row in m.native_calls if 'create_import' in row]
        assert trades == [{'create_import': 'uranium', 'factories': 1, 'requested_native_capacity': 80, 'importer': 'AAA', 'exporter': 'BBB'}]
        m.call('eon_uranium_daily')
        assert len([row for row in m.native_calls if 'create_import' in row]) == 1
        # The native engine has not been emulated or assumed to deliver this trade.
        assert m.country().native['resource_imported@uranium'] == 0
        return [m]
    case('ai_import_request_bounded_and_correct_exporter_scope', ai_purchase)
    # create_import binds whole civilian factories. At the declared uranium
    # cic=.0125, one factory quotes capacity80 actual resource units.
    # These checks bind the source request and capacity; the native engine must
    # independently establish delivered/retained counters.
    for consumption, civs, exports, expected in ((1154, 10, 1000, 2), (2308, 10, 1000, 3),
                                                (8078, 10, 1000, 10), (3462, 10, 1000, 4),
                                                (3462, 2, 1000, 2), (3462, 10, 140, 1),
                                                (3462, 10, 80, 1), (3462, 10, 159, 1),
                                                (3462, 10, 160, 2), (3462, 10, 249, 3)):
        def bounded_import(consumption=consumption, civs=civs, exports=exports, expected=expected):
            m = setup(source)
            m.country().ai = True
            m.country().variables['nuclear_fuel_consumption'] = consumption
            m.country().native['num_of_civilian_factories_available_for_projects'] = civs
            m.country('BBB').native['resource_exported@uranium'] = exports
            m.call('eon_uranium_daily')
            trades = [row for row in m.native_calls if 'create_import' in row]
            assert trades == [{'create_import': 'uranium', 'factories': expected, 'requested_native_capacity': expected*80, 'importer': 'AAA', 'exporter': 'BBB'}]
            assert len(m.meta_expansions) == 1
            generated = p.one(m.meta_expansions[0]['ast'], 'create_import')
            assert p.one(generated, 'exporter') == 'BBB', 'Generated native exporter must be a literal selected-country tag'
            assert p.one(generated, 'factories') == str(expected)
            assert expected <= civs
            assert expected*80 <= exports, 'Request capacity exceeds native exporter allocation'
            assert m.country().native['resource_imported@uranium'] == 0, 'Source test must not emulate native delivery'
            return [m]
        case('ai_actual_import_target_'+str(consumption)+'_civ_'+str(civs)+'_exports_'+str(exports), bounded_import)
    def partial_domestic_import_shortfall():
        m = setup(source, flow=10)
        m.country().ai = True
        m.country().variables['nuclear_fuel_consumption'] = 3400
        m.country().native['num_of_civilian_factories_available_for_projects'] = 10
        m.country('BBB').native['resource_exported@uranium'] = 1000
        m.call('eon_uranium_daily')
        trades = [row for row in m.native_calls if 'create_import' in row]
        # Target30600kg minus existing10000kg needs3 factories (24000kg).
        assert trades == [{'create_import': 'uranium', 'factories': 3,
                           'requested_native_capacity': 240, 'importer': 'AAA', 'exporter': 'BBB'}]
        assert m.country().native['resource@uranium'] == 100
        assert m.country().native['resource_imported@uranium'] == 0
        return [m]
    case('ai_import_requests_only_uncovered_domestic_flow', partial_domestic_import_shortfall)
    for condition in ('human', 'disabled', 'no_facilities', 'no_civ', 'enough_flow', 'enough_stock', 'war', 'exporter_embargo', 'importer_embargo', 'no_export_capacity'):
        def ai_blocked(condition=condition):
            m = setup(source)
            m.country().ai = True
            m.country().variables['nuclear_fuel_consumption'] = 1154
            m.country().native['num_of_civilian_factories_available_for_projects'] = 1
            m.country('BBB').native['resource_exported@uranium'] = 80
            if condition == 'human': m.country().ai = False
            elif condition == 'disabled': m.country().flags.discard('enabled_nuclear_reactor_fuel_production')
            elif condition == 'no_facilities': m.country().variables['enrichment_facilities'] = 0
            elif condition == 'no_civ': m.country().native['num_of_civilian_factories_available_for_projects'] = 0
            elif condition == 'enough_flow': m.country().native['resource@uranium'] = 110
            elif condition == 'enough_stock': m.country().variables['eon_natural_uranium_stock_kg'] = 270036
            elif condition == 'war': m.country('BBB').wars.add('AAA')
            elif condition == 'exporter_embargo': m.country('BBB').embargoing.add('AAA')
            elif condition == 'importer_embargo': m.country().embargoing.add('BBB')
            elif condition == 'no_export_capacity': m.country('BBB').native['resource_exported@uranium'] = 79
            m.call('eon_uranium_daily')
            assert not any('create_import' in row for row in m.native_calls), m.native_calls
            return [m]
        case('ai_import_does_not_start_with_'+condition, ai_blocked)

    def exhausted_next_week():
        m = setup(source)
        mine(m, reserve=18000, capacity=18)
        weekly(m)
        v = m.country().variables
        equal(v['var_reactor_material_stockpile'], 2000)
        assert m.state().variables['eon_uranium_reserve_kg'] == 0
        # Expiry is an explicit fixture action; this is not a natural timer test.
        m.country().flags.discard('eon_uranium_weekly_settled')
        m.state().flags.discard('eon_uranium_state_weekly_settled')
        weekly(m)
        equal(v['var_reactor_material_stockpile'], 2000)
        assert v['eon_uranium_last_extracted_kg'] == 0
        assert v['eon_uranium_last_delivered_kg'] == 0
        return [m]
    case('exhausted_deposit_does_not_refill_on_next_settlement', exhausted_next_week)

    gui = 'common/scripted_guis/01_energy_gui.txt'
    for count, suffix in ((1, 'click'), (3, 'shift_click')):
        button = 'build_enrichment_facility_button_'+suffix
        enable = source.hook(gui, ['scripted_gui', 'energy_scripted_gui', 'triggers', button+'_enabled'])
        action = source.hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', button])
        def actual_gui(count=count, enable=enable, action=action):
            m = setup(source, facilities=0)
            m.country().variables['treasury'] = 100
            m.country().native['industrial_complex_total'] = 40
            m.entities['GLOBAL'].arrays['enrichment_countries'] = [1]
            assert m.trigger(enable)
            m.effect(action)
            equal(m.country().variables['treasury'], 100-25*count)
            assert m.country().variables['eon_enrichment_project_count'] == count
            assert m.country().variables['enrichment_facilities'] == 0
            assert 'energy_building_enrichment_facilities' in m.country().missions
            extensions = [row for row in m.native_calls if 'add_days_mission_timeout' in row]
            assert extensions == ([{'add_days_mission_timeout': 'energy_building_enrichment_facilities',
                                    'days': 365, 'scope': 'AAA'}] if count == 3 else []), extensions
            assert not m.trigger(enable)
            before = deepcopy(m.country().variables)
            m.effect(action)
            assert m.country().variables == before
            assert [row for row in m.native_calls if 'add_days_mission_timeout' in row] == extensions
            return [m]
        case('actual_gui_'+str(count)+'_facility_starts_paid_mission_once', actual_gui)

    category = 'GENERIC_economic_category'
    timeout = source.hook('common/decisions/generic.txt', [category, 'energy_building_enrichment_facilities', 'timeout_effect'])
    cancel = source.hook('common/decisions/generic.txt', [category, 'energy_building_enrichment_facilities', 'complete_effect'])
    def timeout_once():
        m = setup(source, facilities=0)
        m.country().variables['treasury'] = 100
        project(m, 1)
        m.effect(timeout)
        assert m.country().variables['enrichment_facilities'] == 1
        assert m.country().variables['treasury'] == 75
        before = deepcopy(m.country().variables)
        m.effect(timeout)
        assert m.country().variables == before, ('Late timeout changed stocks/payment', m.country().variables, before)
        return [m]
    case('actual_mission_timeout_does_not_fall_through_to_legacy_twice', timeout_once)

    def cancelled_timeout():
        m = setup(source, facilities=0)
        m.country().variables['treasury'] = 100
        project(m, 1)
        m.effect(cancel)
        assert m.country().variables['treasury'] == 100
        before = deepcopy(m.country().variables)
        m.effect(timeout)
        assert m.country().variables == before, 'Stale timeout after cancellation started a legacy project'
        return [m]
    case('actual_cancel_then_stale_timeout_cannot_build_unpaid_legacy_facilities', cancelled_timeout)

    def timer_only_legacy_project_blocks_new_start():
        m=setup(source,facilities=0)
        m.country().variables['treasury']=100
        m.country().native['industrial_complex_total']=200
        m.country().native['days_mission_timeout@energy_building_enrichment_facilities']=730
        assert not m.country().missions and 'eon_enrichment_project_paid' not in m.country().flags
        before=deepcopy(m.country().variables)
        project(m,1)
        assert m.country().variables == before
        assert not any('mission' in row or 'add_days_mission_timeout' in row for row in m.native_calls)
        return [m]
    case('legacy_native_timer_blocks_start_even_when_active_predicate_is_false',timer_only_legacy_project_blocks_new_start)

    def timer_only_paid_cancel_dispatches_remove_once():
        m=setup(source,facilities=0)
        m.country().variables['treasury']=100
        project(m,1)
        m.country().missions.clear()
        m.country().native['days_mission_timeout@energy_building_enrichment_facilities']=729
        m.effect(cancel)
        equal(m.country().variables['treasury'],100)
        equal(m.country().native['days_mission_timeout@energy_building_enrichment_facilities'],0)
        removes=[row for row in m.native_calls if 'remove_mission' in row]
        assert removes == [{'remove_mission':'energy_building_enrichment_facilities','scope':'AAA'}]
        m.effect(cancel)
        assert [row for row in m.native_calls if 'remove_mission' in row] == removes
        m.effect(timeout)
        equal(m.country().variables['enrichment_facilities'],0)
        equal(m.country().variables['treasury'],100)
        return [m]
    case('paid_cancel_removes_timer_and_refunds_once_without_active_predicate',timer_only_paid_cancel_dispatches_remove_once)

    mission = source.hook('common/decisions/generic.txt', [category, 'energy_building_enrichment_facilities'])
    mission_visible = p.one(mission, 'visible')
    energy_events = source.hook('events/00_Energy_events.txt', [])
    energy5 = [body for key, op, body in energy_events if key == 'country_event' and p.one(body, 'id') == 'energy.5']
    assert len(energy5) == 1
    cease = [body for key, op, body in energy5[0] if key == 'option' and p.one(body, 'name') == 'energy.5.a']
    assert len(cease) == 1
    # Option selection weights/name are metadata, not execution statements.
    # Execute every actual effect, including separately recorded native requests.
    cease_effects = [node for node in cease[0] if node[0] not in ('name', 'ai_chance')]

    def project_closed(m):
        c = m.country()
        assert 'eon_enrichment_project_paid' not in c.flags
        assert 'single_enrichment_facility' not in c.flags
        assert 'build_three_enrichment_facility' not in c.flags
        assert 'eon_enrichment_project_era' in c.flags
        for key in ('eon_enrichment_project_count', 'eon_enrichment_project_escrow', 'enrichment_facility_time'):
            assert key not in c.variables
        assert not m.trigger(mission_visible)
        equal(c.native['days_mission_timeout@energy_building_enrichment_facilities'], 0)
        assert 'energy_building_enrichment_facilities' not in c.missions

    for count in (1, 3):
        def actual_diplomatic_cancel(count=count):
            m = setup(source, facilities=0)
            c = m.country()
            c.variables['treasury'] = 100
            c.native['industrial_complex_total'] = 200
            project(m, count)
            c.missions.clear()  # Explicit selectable-mission false-active input.
            c.native['days_mission_timeout@energy_building_enrichment_facilities'] = 729 if count == 1 else 1094
            assert m.trigger(mission_visible)
            m.effect(cease_effects)
            project_closed(m)
            equal(c.variables['treasury'], 100)
            equal(c.variables['enrichment_facilities'], 0)
            assert {'add_opinion_modifier': 'canceled_our_enrichment_facility_construction',
                    'scope': 'AAA', 'target': 'BBB'} in m.native_calls
            assert {'country_event': 'energy.6', 'scope': 'BBB', 'days': 3} in m.native_calls
            m.effect(cease_effects)
            project_closed(m)
            equal(c.variables['treasury'], 100)
            before = deepcopy(c.variables)
            m.effect(timeout)
            assert c.variables == before, 'Canceled project fell through to legacy timeout'
            # Cancellation allows a fresh paid project while retaining its era
            # guard. Completion of that new project still executes exactly once.
            project(m, count)
            assert 'eon_enrichment_project_era' in c.flags
            assert c.variables['eon_enrichment_project_count'] == count
            equal(c.variables['treasury'], 100-25*count)
            m.effect(timeout)
            equal(c.variables['enrichment_facilities'], count)
            equal(c.variables['treasury'], 100-25*count)
            before = deepcopy(c.variables)
            m.effect(timeout)
            assert c.variables == before
            return [m]
        case('actual_energy5a_cancel_'+str(count)+'_clears_visibility_refunds_once_and_restarts', actual_diplomatic_cancel)

    for count, flag in ((1, 'single_enrichment_facility'), (3, 'build_three_enrichment_facility')):
        def unpaid_legacy_cancel(count=count, flag=flag):
            m = setup(source, facilities=0)
            c = m.country()
            c.variables.update({'treasury': 100, 'enrichment_facility_time': 730 if count == 1 else 1095,
                                'eon_enrichment_project_count': count, 'eon_enrichment_project_escrow': 25*count})
            c.flags.add(flag)
            c.native['days_mission_timeout@energy_building_enrichment_facilities'] = 729
            assert 'eon_enrichment_project_era' not in c.flags and not c.missions
            m.effect(cease_effects)
            project_closed(m)
            equal(c.variables['treasury'], 100)  # Unpaid escrow is never a refund.
            m.effect(cease_effects)
            project_closed(m)
            before = deepcopy(c.variables)
            m.effect(timeout)
            assert c.variables == before, 'Explicitly canceled legacy timer built unpaid facilities'
            equal(c.variables['enrichment_facilities'], 0)
            return [m]
        case('actual_energy5a_unpaid_legacy_'+str(count)+'_clears_without_refund_or_stale_build', unpaid_legacy_cancel)

    energy6 = [body for key, op, body in energy_events if key == 'country_event' and p.one(body, 'id') == 'energy.6']
    assert len(energy6) == 1
    acknowledgement = [body for key, op, body in energy6[0] if key == 'option' and p.one(body, 'name') == 'energy.6.a']
    assert len(acknowledgement) == 1
    ack_effects = [node for node in acknowledgement[0] if node[0] not in ('name', 'ai_chance')]
    # energy.5.a performs immediate executable cancellation. The delayed ACK
    # now contains only its unchanged hidden cleanup, without a misleading
    # display-only cancellation tooltip for a possibly restarted project.
    assert ('eon_enrichment_cancel_project', '=', 'yes') in cease_effects
    assert not any(key == 'effect_tooltip' for key, op, body in acknowledgement[0])

    def actual_display_only_effect_tooltip():
        # Bind a surviving actual source tooltip to the documented display-only
        # boundary. Its create_wargoal must not be dispatched or interpreted.
        ignore = [body for key, op, body in energy5[0] if key == 'option' and p.one(body, 'name') == 'energy.5.c']
        assert len(ignore) == 1
        tooltip = p.one(ignore[0], 'effect_tooltip')
        docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation/effects_documentation.md')
        documentation = docs.read_text(encoding='utf-8')
        section = documentation.split('## effect_tooltip\n', 1)[1].split('\n## ', 1)[0]
        assert 'Shows just tooltip of effects' in section
        m = setup(source, facilities=0)
        before = deepcopy(m.entities)
        m.effect([('effect_tooltip', '=', tooltip)])
        assert m.entities == before
        assert m.native_calls == [{'effect_tooltip': True, 'scope': 'AAA'}]
        try: m.effect(p.ast('hidden_effect = { invented_effect = yes }'))
        except AssertionError: pass
        else: raise AssertionError('Hidden execution silently skipped unknown statement')
        return [m]
    case('actual_source_effect_tooltip_is_display_only_and_hidden_effect_executes', actual_display_only_effect_tooltip)

    for previous_count, next_count in ((1, 3), (3, 1)):
        def ack_preserves_restarted_project(previous_count=previous_count, next_count=next_count):
            m = setup(source, facilities=0)
            c = m.country()
            c.variables['treasury'] = 100
            c.native['industrial_complex_total'] = 200
            project(m, previous_count)
            m.effect(cease_effects)
            project_closed(m)
            equal(c.variables['treasury'], 100)
            project(m, next_count)
            c.native['days_mission_timeout@energy_building_enrichment_facilities'] = 730 if next_count == 1 else 1095
            c.variables['new_enrichment_country'] = 2
            preserved = deepcopy(c)
            native_before = deepcopy(m.native_calls)
            # Execute the current ACK AST in its recorded country/FROM frame.
            # This does not simulate scheduling, elapsed days or event dispatch.
            m.current = m.root = 'BBB'
            m.from_ = 'AAA'
            m.effect(ack_effects)
            expected = deepcopy(preserved)
            expected.variables.pop('new_enrichment_country')
            assert c == expected, 'Delayed acknowledgement modified the restarted project'
            assert m.native_calls == native_before, 'ACK issued a native project operation'
            m.effect(ack_effects)
            assert c == expected and m.native_calls == native_before
            equal(c.variables['treasury'], 100-25*next_count)
            equal(c.variables['eon_enrichment_project_count'], next_count)
            equal(c.variables['eon_enrichment_project_escrow'], 25*next_count)
            assert 'eon_enrichment_project_paid' in c.flags and 'eon_enrichment_project_era' in c.flags
            return [m]
        case('actual_energy6a_ACK_after_cancel_'+str(previous_count)+'_preserves_restarted_'+str(next_count)+'_and_repeated_ACK', ack_preserves_restarted_project)

    def explicit_cancel_without_pending_mission():
        m = setup(source, facilities=0)
        c = m.country()
        c.variables['treasury'] = 100
        m.call('eon_enrichment_cancel_project')
        m.call('eon_enrichment_cancel_project')
        project_closed(m)
        equal(c.variables['treasury'], 100)
        assert not any('remove_mission' in row for row in m.native_calls)
        before = deepcopy(c.variables)
        m.effect(timeout)
        assert c.variables == before
        return [m]
    case('explicit_cancel_without_pending_mission_is_idempotent_and_guards_legacy_timeout', explicit_cancel_without_pending_mission)

    def legacy_mission():
        m = setup(source, facilities=0)
        m.country().variables['treasury'] = 100
        m.country().flags.add('single_enrichment_facility')
        m.effect(timeout)
        assert m.country().variables['enrichment_facilities'] == 1
        assert m.country().variables['treasury'] == 75
        return [m]
    case('existing_unpaid_legacy_single_mission_remains_supported', legacy_mission)

    def actual_weekly_hook():
        m = setup(source, flow=18, imports=18)
        m.call('nuclear_reactor_fuel_consumption')
        equal(m.country().variables['var_reactor_material_stockpile'], 2000)
        equal(m.country().variables['eon_depleted_uranium_stock_kg'], 16000)
        before = deepcopy(m.country().variables)
        m.call('nuclear_reactor_fuel_consumption')
        assert m.country().variables == before
        return [m]
    case('existing_weekly_material_callback_routes_to_single_settlement', actual_weekly_hook)

    decision = 'common/decisions/eon_uranium_decisions.txt'
    mine_decision = source.hook(decision, ['eon_uranium_category', 'eon_uranium_expand_mine'])
    def owned_enumeration_preserves_permitted_targets():
        from source_model import Entity
        assert p.one(mine_decision, 'state_target') == 'any_owned_state', 'Mine targets must not enumerate the world'
        root_filter = p.one(mine_decision, 'target_root_trigger')
        target_filter = p.one(mine_decision, 'target_trigger')
        assert ('is_owned_by', '=', 'ROOT') in p.one(target_filter, 'FROM')
        assert ('is_controlled_by', '=', 'ROOT') in p.one(target_filter, 'FROM')
        m = setup(source)
        assert m.trigger(root_filter)
        m.entities.update({
            '102': Entity('state', 102, owner='AAA', controller='BBB'),
            '103': Entity('state', 103, owner='BBB', controller='AAA'),
            '104': Entity('state', 104, owner='BBB', controller='BBB'),
            '105': Entity('state', 105, owner='AAA', controller='AAA'),
        })
        for key in ('101', '102', '103', '104'):
            m.state(key).variables['eon_uranium_reserve_kg'] = 2000000
        all_states = [key for key, item in m.entities.items() if item.kind == 'state']
        owned_states = [key for key in all_states if m.state(key).owner == m.root]
        def permitted(candidates):
            selected = []
            for key in candidates:
                m.from_ = key
                if m.trigger(target_filter): selected.append(key)
            return selected
        assert owned_states == ['101', '102', '105'] and len(owned_states) < len(all_states)
        assert permitted(all_states) == permitted(owned_states) == ['101']
        return [m]
    case('mine_owned_state_enumeration_preserves_ownership_control_and_geology_filters', owned_enumeration_preserves_permitted_targets)
    mine_begin = source.hook(decision, ['eon_uranium_category', 'eon_uranium_expand_mine', 'complete_effect'])
    mine_finish = source.hook(decision, ['eon_uranium_category', 'eon_uranium_expand_mine', 'remove_effect'])
    def actual_mine_decision():
        m = setup(source)
        m.from_ = '101'
        mine(m, reserve=20000000, capacity=5, limit=15)
        m.country().variables['treasury'] = 1
        m.effect(mine_begin)
        assert m.country().variables['treasury'] == 0.75
        assert m.state().variables['eon_uranium_capacity'] == 5
        m.effect(mine_finish)
        assert m.country().variables['treasury'] == 0.75
        assert m.state().variables['eon_uranium_capacity'] == 7.5
        return [m]
    case('actual_state_decision_reserves_and_completes_expansion', actual_mine_decision)

    for capped in (False, True):
        def annex(capped=capped):
            m = setup(source, stock=123)
            m.country().variables.update({'eon_depleted_uranium_stock_kg': 456,
                                          'var_reactor_material_stockpile': 789,
                                          'eon_nuclear_fuel_trade_successor': 2,
                                          'eon_enrichment_project_escrow': 75,
                                          'eon_enrichment_project_count': 3})
            m.country().flags.add('eon_enrichment_project_paid')
            m.state().variables.update({'eon_uranium_mine_project_owner': 1,
                                        'eon_uranium_mine_project_escrow': 0.25})
            m.state().flags.add('eon_uranium_mine_project')
            successor = m.country('BBB')
            successor.variables.update({'eon_natural_uranium_stock_kg': 10,
                                         'eon_depleted_uranium_stock_kg': 20,
                                         'var_reactor_material_stockpile': 20000000 if capped else 30,
                                         'treasury': 1000000 if capped else 100})
            m.call('eon_uranium_transfer_annexed_assets')
            equal(successor.variables['eon_natural_uranium_stock_kg'], 133)
            equal(successor.variables['eon_depleted_uranium_stock_kg'], 476)
            equal(successor.variables['var_reactor_material_stockpile'], 20000000 if capped else 819)
            equal(successor.variables['treasury'], 1000000 if capped else 175.25)
            if capped:
                equal(successor.variables['eon_nuclear_fuel_trade_fuel_refund_due'], 789)
                equal(successor.variables['eon_nuclear_fuel_trade_cash_refund_due'], 75.25)
            assert 'eon_enrichment_project_paid' not in m.country().flags
            assert 'eon_uranium_mine_project' not in m.state().flags
            for key in ('eon_natural_uranium_stock_kg', 'eon_depleted_uranium_stock_kg', 'var_reactor_material_stockpile'):
                equal(m.country().variables[key], 0)
            before = deepcopy(successor.variables)
            m.call('eon_uranium_transfer_annexed_assets')
            assert successor.variables == before
            return [m]
        case('actual_annexation_transfers_material_and_both_escrows_once'+('_capped' if capped else ''), annex)

    def unknown_fails():
        m = setup(source)
        for nodes, callback in ((p.ast('invented_effect = yes'), m.effect),
                                (p.ast('invented_trigger = yes'), m.trigger)):
            try: callback(nodes)
            except AssertionError: pass
            else: raise AssertionError('Unknown visited statement silently accepted')
        return [m]
    case('interpreter_rejects_unknown_visited_statements', unknown_fails)
    mismatches = [rel for rel, digest in source.sha256.items()
                  if hashlib.sha256((p.ROOT/rel).read_bytes()).hexdigest() != digest]
    result = {'actual_source_behavior_checks_passed': not failed and not mismatches,
              'passed_cases': passed, 'failed_cases': failed,
              'source_sha256': source.sha256, 'trace': trace,
              'native_resource_delivery_or_calendar_emulated': False,
              'source_snapshot_mismatches': mismatches,
              'new_country_first_enrichment_diplomatic_reaction_executed': False,
              'full_economy_or_finished_fuel_trade_cleanup_executed': False,
              'native_game_behavior_tested': False}
    if emit: print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    raise SystemExit(0 if run()['actual_source_behavior_checks_passed'] else 1)
