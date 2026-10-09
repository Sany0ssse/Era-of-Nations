"""Reject gameplay regressions by mutating only in-memory copies of actual AST."""
from copy import deepcopy
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_model import Source, p
from test_core_source import run


def mutate(nodes, predicate, replacement):
    changed = 0
    for index, node in list(enumerate(nodes)):
        if predicate(node):
            nodes[index] = replacement(node)
            changed += 1
        elif isinstance(node[2], list):
            changed += mutate(node[2], predicate, replacement)
    return changed


def statement(name, variable):
    return lambda node: node[0] == name and isinstance(node[2], list) and (
        (len(node[2]) == 1 and node[2][0][0] == variable) or
        any(key == 'var' and value == variable for key, op, value in node[2]))


def main():
    original = Source()
    baseline = run(original, emit=False)
    assert baseline['actual_source_behavior_checks_passed'], baseline['failed_cases']
    mutations = []

    def changed(name, helper, predicate, replacement):
        candidate = deepcopy(original)
        count = mutate(candidate.effects[helper], predicate, replacement)
        assert count, ('Mutation did not reach source', name)
        mutations.append((name, candidate))

    changed('ratio9_to8', 'eon_uranium_weekly_materials',
            statement('divide_temp_variable', 'eon_actual_fuel_kg'),
            lambda node: ('divide_temp_variable', '=', [('eon_actual_fuel_kg', '=', '8')]))
    changed('remove_legacy_kg_migration_flag', 'eon_uranium_initialize',
            lambda node: node[0] == 'set_country_flag' and node[2] == 'eon_uranium_reactor_stock_in_kg',
            lambda node: ('log', '=', 'private mutation removed legacy migration completion flag'))
    changed('wrong_legacy_kg_migration_ratio', 'eon_uranium_initialize',
            statement('multiply_variable', 'var_reactor_material_stockpile'),
            lambda node: ('multiply_variable', '=', [('var_reactor_material_stockpile', '=', '2')]))
    changed('remove_raw_consumption', 'eon_uranium_weekly_materials',
            statement('subtract_from_variable', 'eon_natural_uranium_stock_kg'),
            lambda node: ('log', '=', 'private mutation removed raw subtraction'))
    changed('remove_tails_product_separation', 'eon_uranium_weekly_materials',
            statement('subtract_from_temp_variable', 'eon_tails_kg'),
            lambda node: ('log', '=', 'private mutation removed tails separation'))
    changed('remove_weekly_guard', 'eon_uranium_weekly_materials',
            lambda node: node[0] == 'has_country_flag' and node[2] == 'eon_uranium_weekly_settled',
            lambda node: ('always', '=', 'no'))
    changed('remove_reserve_clip', 'eon_uranium_settle_state_extraction',
            statement('clamp_variable', 'eon_uranium_state_last_extracted_kg'),
            lambda node: ('log', '=', 'private mutation removed reserve clip'))
    changed('remove_shared_state_depletion_guard', 'eon_uranium_settle_state_extraction',
            lambda node: node[0] == 'has_state_flag' and node[2] == 'eon_uranium_state_weekly_settled',
            lambda node: ('always', '=', 'no'))
    changed('remove_final_rights_recipient_snapshot', 'eon_uranium_settle_state_extraction',
            statement('set_variable', 'PREV.eon_uranium_state_last_rights_recipient'),
            lambda node: ('log', '=', 'private mutation removed final rights recipient'))
    changed('remove_native_multiplier_normalizer', 'eon_uranium_refresh_mine',
            statement('divide_temp_variable', 'eon_mine_remaining_flow'),
            lambda node: ('log', '=', 'private mutation removed native multiplier normalization')
            if node[2] == [('eon_mine_remaining_flow', '=', 'eon_mine_native_multiplier')] else node)
    changed('remove_integer_floor_before_native_add_resource', 'eon_uranium_refresh_mine',
            statement('subtract_from_temp_variable', 'eon_mine_output'),
            lambda node: ('log', '=', 'private mutation removed integer floor correction'))
    changed('double_enrichment_capacity', 'eon_uranium_project_fuel',
            statement('multiply_variable', 'eon_enrichment_capacity_kg'),
            lambda node: ('multiply_variable', '=', [('eon_enrichment_capacity_kg', '=', '40000')])
            if node[2] == [('eon_enrichment_capacity_kg', '=', '20000')] else node)
    changed('remove_project_upfront_payment', 'eon_enrichment_begin_project',
            statement('subtract_from_variable', 'treasury'),
            lambda node: ('log', '=', 'private mutation removed upfront payment'))
    changed('remove_triple_native_calendar_extension', 'eon_enrichment_begin_project',
            lambda node: node[0] == 'add_days_mission_timeout',
            lambda node: ('log', '=', 'private mutation removed triple calendar extension'))
    changed('remove_domestic_flow_from_native_import_shortfall', 'eon_uranium_daily',
            lambda node: node == ('subtract_from_temp_variable', '=', [('eon_raw_import_amount', '=', 'eon_raw_current_flow')]),
            lambda node: ('log', '=', 'private mutation removed domestic import shortfall'))
    changed('remove_completion_paid_clear', 'eon_enrichment_complete_project',
            lambda node: node[0] == 'clr_country_flag' and node[2] == 'eon_enrichment_project_paid',
            lambda node: ('log', '=', 'private mutation removed completed paid flag clear'))
    changed('remove_cancel_paid_clear', 'eon_enrichment_cancel_project',
            lambda node: node[0] == 'clr_country_flag' and node[2] == 'eon_enrichment_project_paid',
            lambda node: ('log', '=', 'private mutation removed cancellation paid flag clear'))
    for field in ('enrichment_facility_time', 'eon_enrichment_project_count', 'eon_enrichment_project_escrow'):
        changed('remove_explicit_cancel_cleanup_'+field, 'eon_enrichment_cancel_project',
                lambda node, field=field: node == ('clear_variable', '=', field),
                lambda node: ('log', '=', 'private mutation removed cancellation field cleanup'))
    for flag in ('single_enrichment_facility', 'build_three_enrichment_facility'):
        changed('remove_explicit_cancel_cleanup_'+flag, 'eon_enrichment_cancel_project',
                lambda node, flag=flag: node == ('clr_country_flag', '=', flag),
                lambda node: ('log', '=', 'private mutation removed cancellation legacy flag cleanup'))
    changed('remove_explicit_cancel_legacy_stale_guard', 'eon_enrichment_cancel_project',
            lambda node: node == ('set_country_flag', '=', 'eon_enrichment_project_era'),
            lambda node: ('log', '=', 'private mutation removed explicit legacy cancellation guard'))
    world_targets = deepcopy(original)
    mine_nodes = world_targets.hook('common/decisions/eon_uranium_decisions.txt', ['eon_uranium_category', 'eon_uranium_expand_mine'])
    count = mutate(mine_nodes, lambda node: node == ('state_target', '=', 'any_owned_state'),
                   lambda node: ('state_target', '=', 'yes'))
    assert count == 1
    # hook parses fresh bytes: bind this mutation as an in-memory raw source
    # change and keep the original on-disk digest for the existing drift check.
    rel = 'common/decisions/eon_uranium_decisions.txt'
    world_targets.raw[rel] = world_targets.raw[rel].replace(b'state_target = any_owned_state', b'state_target = yes')
    mutations.append(('restore_world_scan_for_mine_targets', world_targets))
    changed('remove_paid_cancel_native_timer_removal','eon_enrichment_cancel_project',
            lambda node:node[0] == 'remove_mission',
            lambda node:('log','=','private mutation removed native timer removal'))
    no_timer_guard=deepcopy(original)
    count=mutate(no_timer_guard.triggers['eon_enrichment_project_ready'],
                 lambda node:node == ('check_variable','=',[('days_mission_timeout@energy_building_enrichment_facilities','>','0')]),
                 lambda node:('always','=','no'))
    assert count == 1
    mutations.append(('remove_legacy_positive_native_timer_guard',no_timer_guard))
    changed('double_mine_geometric_expansion', 'eon_uranium_complete_mine_project',
            statement('multiply_temp_variable', 'eon_proposed_mine_capacity'),
            lambda node: ('multiply_temp_variable', '=', [('eon_proposed_mine_capacity', '=', '3')]))
    changed('read_execution_import_target_as_previous_country_persistent_variable', 'eon_uranium_daily',
            statement('set_temp_variable', 'eon_raw_import_amount'),
            lambda node: ('set_temp_variable', '=', [('eon_raw_import_amount', '=', 'PREV.eon_raw_target')]))
    changed('bind_native_import_exporter_to_importer', 'eon_uranium_daily',
            lambda node: node[0] == 'EXPORTER_TAG',
            lambda node: ('EXPORTER_TAG', '=', '[THIS.GetTag]'))
    changed('generate_native_import_with_contextual_prev_exporter', 'eon_uranium_daily',
            lambda node: node[0] == 'exporter' and node[2] == '[EXPORTER_TAG]',
            lambda node: ('exporter', '=', 'PREV'))
    changed('remove_native_import_factory_capacity80_scale', 'eon_uranium_daily',
            lambda node: node == ('divide_temp_variable', '=', [('eon_raw_import_amount', '=', '80')]),
            lambda node: ('log', '=', 'private mutation removed native factory capacity80'))
    changed('remove_exporter_native_to_factory_capacity80_scale', 'eon_uranium_daily',
            statement('divide_temp_variable', 'eon_raw_import_exporter_cap'),
            lambda node: ('log', '=', 'private mutation removed exporter factory capacity80'))
    changed('overstate_native_import_factory_budget10fold', 'eon_uranium_daily',
            statement('set_temp_variable', 'eon_raw_import_factory_cap'),
            lambda node: ('set_temp_variable', '=', [('eon_raw_import_factory_cap', '=', '80')]))
    changed('round_demand_down_to_partial_week', 'eon_uranium_daily',
            statement('add_to_temp_variable', 'eon_raw_import_amount'),
            lambda node: ('add_to_temp_variable', '=', [('eon_raw_import_amount', '=', '0')]))

    executing_ack = deepcopy(original)
    events_rel = 'events/00_Energy_events.txt'
    executing_ack.hook(events_rel, [])
    old = b'name = energy.6.a\n'
    assert executing_ack.raw[events_rel].count(old) == 1
    executing_ack.raw[events_rel] = executing_ack.raw[events_rel].replace(
        old, old+b'\t\tFROM = { eon_enrichment_cancel_project = yes }\n')
    mutations.append(('execute_cancellation_in_delayed_ACK', executing_ack))

    impure = deepcopy(original)
    impure.effects['eon_uranium_project_fuel'] += p.ast('add_to_variable = { var_reactor_material_stockpile = nuclear_reactor_fuel_production }')
    mutations.append(('projection_credits_fuel', impure))

    depleted = deepcopy(original)
    branch = p.one(depleted.effects['eon_uranium_weekly_materials'], 'if')
    moved = [node for node in branch if statement('set_temp_variable', 'eon_uranium_delivered_kg')(node) or
             statement('multiply_temp_variable', 'eon_uranium_delivered_kg')(node)]
    assert len(moved) == 2
    branch[:] = [node for node in branch if node not in moved]
    position = next(index for index, node in enumerate(branch) if node[0] == 'every_controlled_state')
    branch[position+1:position+1] = moved
    mutations.append(('snapshot_flow_after_mine_shutdown', depleted))

    rejected = []
    for name, candidate in mutations:
        result = run(candidate, emit=False)
        assert not result['actual_source_behavior_checks_passed'], ('Regression accepted', name)
        rejected.append({'mutation': name, 'failed_cases': [case['case'] for case in result['failed_cases']]})
    print(json.dumps({'actual_source_mutations_rejected': True,
                      'baseline_cases_passed': len(baseline['passed_cases']),
                      'mutations_rejected': len(rejected), 'rejected': rejected,
                      'source_sha256': baseline['source_sha256'], 'native_game_behavior_tested': False}, indent=2))


if __name__ == '__main__':
    main()
